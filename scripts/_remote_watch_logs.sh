#!/usr/bin/env bash
# scripts/_remote_watch_logs.sh
#
# Lógica que roda DENTRO da VM (bash remoto). Não chame este arquivo diretamente:
# ele é enviado via stdin pelo wrapper local `scripts/watch_logs.sh`, que faz o SSH.
# Mantido como arquivo separado só para não misturar a lógica de conexão com a de
# leitura do log.

set -euo pipefail

LOG_FILE="${LOG_FILE:-logs/DocsAnalyzer3_Server.log}"
LINES=50
FILTER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -n) LINES="$2"; shift 2 ;;
        -f) LOG_FILE="$2"; shift 2 ;;
        *) FILTER="$1"; shift ;;
    esac
done

if [[ ! -f "$LOG_FILE" ]]; then
    echo "Arquivo de log não encontrado na VM: $LOG_FILE (cwd: $(pwd))" >&2
    exit 1
fi

colorize() {
    # fflush() após cada linha: sem isso o awk bufferiza a saída em bloco quando não
    # está conectado a um terminal (é o caso aqui, no meio de um pipe), atrasando a
    # exibição em minutos em vez de segundos — o oposto do que "tempo real" pede.
    awk '
        /\| ERROR / || /\| CRITICAL /  { print "\033[1;31m" $0 "\033[0m"; fflush(); next }
        /\| WARNING /                  { print "\033[1;33m" $0 "\033[0m"; fflush(); next }
        /\| DEBUG /                    { print "\033[2m" $0 "\033[0m"; fflush(); next }
        { print; fflush() }
    '
}

if [[ -n "$FILTER" ]]; then
    echo "Filtrando por: '$FILTER' (case-insensitive) — arquivo: $LOG_FILE" >&2
    tail -n "$LINES" -F "$LOG_FILE" | grep --line-buffered -i "$FILTER" | colorize
else
    echo "Acompanhando: $LOG_FILE (sem filtro)" >&2
    tail -n "$LINES" -F "$LOG_FILE" | colorize
fi
