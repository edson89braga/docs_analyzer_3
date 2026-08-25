#!/usr/bin/env bash
# scripts/check_active_sessions.sh
#
# Roda LOCALMENTE (Git Bash no Windows, ou qualquer máquina com `ssh`) e conecta na
# VM via SSH para consultar a tabela `active_sessions` (SQLite dentro do container),
# mostrando quem está online agora. Não precisa copiar nada para a VM.
#
# Configuração (variáveis de ambiente; defaults conforme
# "Instruções SSH VM PF Docker Deploy.txt"):
#   VM_HOST     (default: sti@10.11.8.25)
#   VM_PATH     (default: /home/sti/Deploy_PF)
#   CONTAINER   (default: opera-ia-frontend)      -> repassado ao script remoto
#   DOCKER_CMD  (default: docker; use 'sudo docker' se necessário)
#
# Uso:
#   ./scripts/check_active_sessions.sh          # só sessões ativas agora
#   ./scripts/check_active_sessions.sh --all    # inclui histórico de sessões encerradas

set -euo pipefail

VM_HOST="${VM_HOST:-sti@10.11.8.25}"
VM_PATH="${VM_PATH:-/home/sti/Deploy_PF}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_SCRIPT="$SCRIPT_DIR/_remote_check_active_sessions.sh"

if [[ ! -f "$REMOTE_SCRIPT" ]]; then
    echo "Script remoto não encontrado: $REMOTE_SCRIPT" >&2
    exit 1
fi

quoted_args=""
for arg in "$@"; do
    quoted_args+=" $(printf '%q' "$arg")"
done

# CONTAINER/DOCKER_CMD são lidos pelo script remoto via variável de ambiente;
# exportamos na própria string de comando SSH para não depender de configuração
# prévia na VM.
env_prefix=""
[[ -n "${CONTAINER:-}" ]] && env_prefix+="CONTAINER=$(printf '%q' "$CONTAINER") "
[[ -n "${DOCKER_CMD:-}" ]] && env_prefix+="DOCKER_CMD=$(printf '%q' "$DOCKER_CMD") "

ssh "$VM_HOST" "cd $(printf '%q' "$VM_PATH") && ${env_prefix}bash -s --$quoted_args" < "$REMOTE_SCRIPT"
