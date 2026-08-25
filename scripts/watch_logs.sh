#!/usr/bin/env bash
# scripts/watch_logs.sh
#
# Roda LOCALMENTE (Git Bash no Windows, ou qualquer máquina com `ssh`) e conecta na
# VM via SSH para acompanhar logs/DocsAnalyzer3_Server.log em tempo real — já
# enriquecido com session_id/user_id (ver SOURCE/logger/logger.py). Não precisa
# copiar nada para a VM: a lógica remota (`_remote_watch_logs.sh`) é enviada via
# stdin a cada execução.
#
# Configuração (variáveis de ambiente; defaults conforme
# "Instruções SSH VM PF Docker Deploy.txt"):
#   VM_HOST  (default: sti@10.11.8.25)
#   VM_PATH  (default: /home/sti/Deploy_PF)  -> onde ficam docker-compose.yml e logs/
#
# Uso:
#   ./scripts/watch_logs.sh                    # acompanha tudo, sem filtro
#   ./scripts/watch_logs.sh usuario@dominio     # filtra por e-mail/session_id/texto
#   ./scripts/watch_logs.sh -n 200 ERROR        # últimas 200 linhas antes de seguir
#
# Pede a senha da VM a cada execução (mesmo fluxo do SSH manual). Ctrl+C encerra.

set -euo pipefail

VM_HOST="${VM_HOST:-sti@10.11.8.25}"
VM_PATH="${VM_PATH:-/home/sti/Deploy_PF}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_SCRIPT="$SCRIPT_DIR/_remote_watch_logs.sh"

if [[ ! -f "$REMOTE_SCRIPT" ]]; then
    echo "Script remoto não encontrado: $REMOTE_SCRIPT" >&2
    exit 1
fi

# Escapa cada argumento recebido para reconstrução segura na string de comando remoto.
quoted_args=""
for arg in "$@"; do
    quoted_args+=" $(printf '%q' "$arg")"
done

echo "Conectando em $VM_HOST (pode pedir senha)... Ctrl+C para sair."
exec ssh -t "$VM_HOST" "cd $(printf '%q' "$VM_PATH") && bash -s --$quoted_args" < "$REMOTE_SCRIPT"
