# FILE: SOURCE/scripts/check_active_sessions.py
"""Consulta pontual de "quem está usando a aplicação agora", lendo a tabela
`active_sessions` do SQLite local (ver `SOURCE/services/local_db_manager.py` e
`NOTES_monitoramento.md`).

Pensado para rodar dentro do container em produção, via `docker exec`:

    docker exec -it opera-ia-frontend python -m SOURCE.scripts.check_active_sessions
    docker exec -it opera-ia-frontend python -m SOURCE.scripts.check_active_sessions --all

Ou, na VM, usando o wrapper `scripts/check_active_sessions.sh` (fora do container).
"""
from __future__ import annotations

import argparse
import sqlite3

from SOURCE.services.local_db_manager import DB_FILE

COLUMN_WIDTHS = {
    "session_id": 22,
    "user_email": 35,
    "connected_at": 20,
    "disconnected_at": 20,
}


def _print_table(rows: list[sqlite3.Row]) -> None:
    """Imprime as linhas em formato de tabela alinhada no terminal."""
    header = "".join(col.ljust(width) for col, width in COLUMN_WIDTHS.items())
    print(header)
    print("-" * len(header))
    for row in rows:
        line = "".join(
            str(row[col] if row[col] is not None else "-").ljust(width)
            for col, width in COLUMN_WIDTHS.items()
        )
        print(line)


def main() -> None:
    """Lê `active_sessions` e imprime as sessões ativas (ou todas, com `--all`)."""
    parser = argparse.ArgumentParser(
        description="Lista sessões ativas (ou recentes) do ÓPERA a partir do SQLite local."
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Inclui também sessões já encerradas (histórico), não só as ativas agora."
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Número máximo de linhas exibidas (padrão: 50)."
    )
    args = parser.parse_args()

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        if args.all:
            query = "SELECT * FROM active_sessions ORDER BY connected_at DESC LIMIT ?"
        else:
            query = (
                "SELECT * FROM active_sessions WHERE disconnected_at IS NULL "
                "ORDER BY connected_at DESC LIMIT ?"
            )
        rows = conn.execute(query, (args.limit,)).fetchall()
    finally:
        conn.close()

    if not rows:
        print("Nenhuma sessão ativa no momento." if not args.all else "Nenhuma sessão registrada.")
        return

    escopo = "registro(s), incluindo encerradas" if args.all else "sessão(ões) ativa(s) agora"
    print(f"{len(rows)} {escopo}:\n")
    _print_table(rows)


if __name__ == "__main__":
    main()
