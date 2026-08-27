# FILE: SOURCE/scripts/check_active_sessions.py
"""Consulta de sessões na tabela `active_sessions` do SQLite local (ver
`SOURCE/services/local_db_manager.py` e `NOTES_monitoramento.md`): quem está online
agora, quem acessou nos últimos N dias, quando desconectou e por quanto tempo.

Pensado para rodar dentro do container em produção, via `docker exec`:

    docker exec -it opera-ia-frontend python -m SOURCE.scripts.check_active_sessions
    docker exec -it opera-ia-frontend python -m SOURCE.scripts.check_active_sessions --days 30
    docker exec -it opera-ia-frontend python -m SOURCE.scripts.check_active_sessions --summary

Ou, do Windows local, via `scripts/check_active_sessions.sh` (que faz o SSH sozinho).
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta

from SOURCE.services.local_db_manager import DB_FILE, now_brasilia

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

SESSION_COLUMN_WIDTHS = {
    "session_id": 22,
    "user_email": 30,
    "connected_at": 20,
    "disconnected_at": 20,
    "duration": 14,
}

SUMMARY_COLUMN_WIDTHS = {
    "user_email": 30,
    "sessions": 10,
    "total_duration": 16,
    "last_seen": 20,
}


def _parse_dt(value: str | None) -> datetime | None:
    """Converte um timestamp gravado pela app (`%Y-%m-%d %H:%M:%S`, Brasília) em datetime."""
    if not value:
        return None
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except ValueError:
        return None


def _format_duration(seconds: float) -> str:
    """Formata uma duração em segundos como texto compacto (ex.: '2h 15min', '3d 4h')."""
    total = int(seconds)
    if total < 0:
        total = 0
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}min")
    return " ".join(parts)


def _fetch_rows(
    conn: sqlite3.Connection,
    *,
    active_only: bool,
    all_history: bool,
    days: int,
    user_filter: str | None,
    limit: int,
) -> list[sqlite3.Row]:
    """Busca as linhas de `active_sessions` conforme o recorte pedido (ativas agora,
    tudo, ou últimos `days` dias), com filtro opcional por usuário."""
    where = []
    params: list[object] = []

    if active_only:
        where.append("disconnected_at IS NULL")
    elif not all_history:
        cutoff = (now_brasilia() - timedelta(days=days)).strftime(DATETIME_FORMAT)
        where.append("connected_at >= ?")
        params.append(cutoff)

    if user_filter:
        where.append("user_email LIKE ?")
        params.append(f"%{user_filter}%")

    query = "SELECT session_id, user_email, connected_at, disconnected_at FROM active_sessions"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY connected_at DESC LIMIT ?"
    params.append(limit)

    return conn.execute(query, params).fetchall()


def _print_sessions_table(rows: list[sqlite3.Row]) -> None:
    """Imprime uma linha por sessão, com a duração calculada em Python."""
    # .replace(tzinfo=None): _parse_dt() devolve datetimes naive (as strings salvas não
    # carregam fuso) — subtrair aware (now_brasilia()) de naive levanta TypeError. Não
    # muda o valor, só remove o tzinfo para comparar com o mesmo referencial.
    now = now_brasilia().replace(tzinfo=None)
    header = "".join(col.ljust(width) for col, width in SESSION_COLUMN_WIDTHS.items())
    print(header)
    print("-" * len(header))
    for row in rows:
        connected = _parse_dt(row["connected_at"])
        disconnected = _parse_dt(row["disconnected_at"])
        if connected is None:
            duration_text = "-"
        else:
            end = disconnected or now
            duration_text = _format_duration((end - connected).total_seconds())
            if disconnected is None:
                duration_text += " (em curso)"

        values = {
            "session_id": row["session_id"],
            "user_email": row["user_email"] or "-",
            "connected_at": row["connected_at"] or "-",
            "disconnected_at": row["disconnected_at"] or "-",
            "duration": duration_text,
        }
        print("".join(str(values[col]).ljust(width) for col, width in SESSION_COLUMN_WIDTHS.items()))


def _print_summary_table(rows: list[sqlite3.Row]) -> None:
    """Agrega as linhas por usuário: nº de sessões, tempo total conectado e último acesso."""
    # .replace(tzinfo=None): _parse_dt() devolve datetimes naive (as strings salvas não
    # carregam fuso) — subtrair aware (now_brasilia()) de naive levanta TypeError. Não
    # muda o valor, só remove o tzinfo para comparar com o mesmo referencial.
    now = now_brasilia().replace(tzinfo=None)
    by_user: dict[str, dict[str, object]] = {}
    for row in rows:
        email = row["user_email"] or "(sem usuário associado)"
        connected = _parse_dt(row["connected_at"])
        disconnected = _parse_dt(row["disconnected_at"])
        duration = (disconnected or now) - connected if connected else timedelta(0)

        entry = by_user.setdefault(email, {"sessions": 0, "total_seconds": 0.0, "last_seen": None})
        entry["sessions"] += 1
        entry["total_seconds"] += duration.total_seconds()
        if connected and (entry["last_seen"] is None or connected > entry["last_seen"]):
            entry["last_seen"] = connected

    header = "".join(col.ljust(width) for col, width in SUMMARY_COLUMN_WIDTHS.items())
    print(header)
    print("-" * len(header))
    for email, entry in sorted(by_user.items(), key=lambda kv: kv[1]["last_seen"] or datetime.min, reverse=True):
        values = {
            "user_email": email,
            "sessions": entry["sessions"],
            "total_duration": _format_duration(entry["total_seconds"]),
            "last_seen": entry["last_seen"].strftime(DATETIME_FORMAT) if entry["last_seen"] else "-",
        }
        print("".join(str(values[col]).ljust(width) for col, width in SUMMARY_COLUMN_WIDTHS.items()))


def main() -> None:
    """Consulta `active_sessions` e imprime a tabela de sessões ou o resumo por usuário."""
    parser = argparse.ArgumentParser(
        description="Consulta sessões do ÓPERA (quem acessou, quando, por quanto tempo)."
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--active", action="store_true",
        help="Só sessões ativas agora (disconnected_at nulo)."
    )
    scope.add_argument(
        "--all", action="store_true",
        help="Todo o histórico, sem janela de dias."
    )
    scope.add_argument(
        "--days", type=int, default=None, metavar="N",
        help="Sessões iniciadas nos últimos N dias (padrão: 7, quando nenhuma outra opção de escopo é usada)."
    )
    parser.add_argument("--user", metavar="TEXTO", help="Filtra por e-mail (substring, case-insensitive para ASCII).")
    parser.add_argument("--limit", type=int, default=200, help="Máximo de linhas exibidas (padrão: 200).")
    parser.add_argument(
        "--summary", action="store_true",
        help="Mostra um resumo por usuário (nº de sessões, tempo total conectado, último acesso) em vez de linha por sessão."
    )
    args = parser.parse_args()

    days = args.days if args.days is not None else 7

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        rows = _fetch_rows(
            conn,
            active_only=args.active,
            all_history=args.all,
            days=days,
            user_filter=args.user,
            limit=args.limit,
        )
    finally:
        conn.close()

    if not rows:
        print("Nenhuma sessão encontrada para o recorte pedido.")
        return

    if args.active:
        escopo = "sessão(ões) ativa(s) agora"
    elif args.all:
        escopo = "registro(s), todo o histórico"
    else:
        escopo = f"registro(s) nos últimos {days} dia(s)"
    if args.user:
        escopo += f" (filtro de usuário: '{args.user}')"

    print(f"{len(rows)} {escopo}:\n")
    if args.summary:
        _print_summary_table(rows)
    else:
        _print_sessions_table(rows)


if __name__ == "__main__":
    main()
