#!/usr/bin/env bash
# scripts/fetch_vm_logs.sh
#
# Baixa via SSH/rsync todos os logs locais (./logs, bind mount do container
# opera-ia-frontend) da VM de produção para este repositório local, em
# admin_data/vm_logs/.
#
# Contexto: descontinuação do uso do Firebase Storage para persistência de
# logs (ver NOTES_persistencia_dados.md). Os logs locais da VM passam a ser
# a única cópia de logs "de servidor" e precisam ser trazidos para cá antes
# de qualquer limpeza remota (ver scripts/cleanup_vm_logs.sh).
#
# Uso:
#   1. Preencha as variáveis VM_USER / VM_HOST / VM_REMOTE_DEPLOY_DIR abaixo.
#   2. Execute a partir da raiz do repositório: bash scripts/fetch_vm_logs.sh
#
# Requer: rsync no cliente local (Git Bash/WSL) e no servidor remoto.
# Se rsync não estiver disponível na VM, o script cai automaticamente para scp -r.

set -euo pipefail

# ============================== CONFIGURAÇÃO ==============================
VM_USER="sti"          # ex: sti
VM_HOST="10.11.8.25"       # ex: 10.11.8.25
# Diretório no HOST da VM onde está o docker-compose.yml de produção
# (o mesmo diretório citado em "Instruções SSH VM PF Docker Deploy.txt")
VM_REMOTE_DEPLOY_DIR="/home/sti/Deploy_PF"   # ex: /home/sti/Deploy_PF
# ============================================================================

VM_REMOTE_LOGS_DIR="${VM_REMOTE_DEPLOY_DIR}/logs"
LOCAL_DEST_DIR="admin_data/vm_logs"

if [[ "$VM_USER" == "PREENCHER_USUARIO" || "$VM_HOST" == "PREENCHER_IP_OU_HOST" || "$VM_REMOTE_DEPLOY_DIR" == "PREENCHER_CAMINHO" ]]; then
    echo "ERRO: preencha VM_USER, VM_HOST e VM_REMOTE_DEPLOY_DIR no topo deste script antes de executar." >&2
    exit 1
fi

# Confere se este script está sendo rodado a partir da raiz do repositório
if [[ ! -f "docker-compose.yml" ]]; then
    echo "ERRO: execute este script a partir da raiz do repositório (onde está docker-compose.yml)." >&2
    exit 1
fi

mkdir -p "$LOCAL_DEST_DIR"

echo "Verificando se rsync está disponível localmente e na VM..."
if command -v rsync >/dev/null 2>&1 && \
    ssh "${VM_USER}@${VM_HOST}" "command -v rsync" >/dev/null 2>&1; then
    echo "Usando rsync (incremental, preserva timestamps)."
    rsync -avz --progress \
        "${VM_USER}@${VM_HOST}:${VM_REMOTE_LOGS_DIR}/" \
        "${LOCAL_DEST_DIR}/"
else
    echo "rsync não encontrado localmente ou na VM. Usando scp -r (baixa tudo novamente a cada execução)."
    scp -r "${VM_USER}@${VM_HOST}:${VM_REMOTE_LOGS_DIR}" "${LOCAL_DEST_DIR}_tmp"
    # Dependendo de o destino temporário já existir, scp pode criar _tmp/logs
    # ou copiar os arquivos diretamente para _tmp.
    mkdir -p "$LOCAL_DEST_DIR"
    if [[ -d "${LOCAL_DEST_DIR}_tmp/logs" ]]; then
        SCP_SOURCE="${LOCAL_DEST_DIR}_tmp/logs"
    else
        SCP_SOURCE="${LOCAL_DEST_DIR}_tmp"
    fi
    cp -rn "${SCP_SOURCE}/." "$LOCAL_DEST_DIR/"
    rm -rf "${LOCAL_DEST_DIR}_tmp"
fi

echo ""
echo "Download concluído. Arquivos salvos em: $LOCAL_DEST_DIR"
echo "Total de arquivos: $(find "$LOCAL_DEST_DIR" -type f | wc -l)"
echo ""
echo "Confira o conteúdo antes de rodar scripts/cleanup_vm_logs.sh na VM."
