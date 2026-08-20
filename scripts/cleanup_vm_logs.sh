#!/usr/bin/env bash
# scripts/cleanup_vm_logs.sh
#
# Limpa o diretório de logs locais na VM de produção (./logs, bind mount
# usado tanto pelo host quanto pelo container opera-ia-frontend em /app/logs
# — é o MESMO diretório físico, então limpar no host já limpa no container,
# sem precisar de docker exec).
#
# ATENÇÃO: só execute isto DEPOIS de confirmar visualmente que
# scripts/fetch_vm_logs.sh trouxe todos os logs para admin_data/vm_logs/
# neste repositório local.
#
# Por segurança, este script NÃO apaga (rm -rf) direto: ele MOVE o conteúdo
# atual de ./logs para um diretório de backup com timestamp
# (./logs_backup_YYYYmmdd_HHMMSS) dentro do mesmo diretório de deploy da VM,
# e recria ./logs vazio. Depois de conferir que tudo está normal (app
# reiniciado, logs novos sendo gerados), você decide manualmente se quer
# apagar o diretório de backup na VM (rm -rf) ou mantê-lo por mais alguns dias.
#
# Uso:
#   1. Preencha as variáveis VM_USER / VM_HOST / VM_REMOTE_DEPLOY_DIR abaixo
#      (mesmos valores usados em fetch_vm_logs.sh).
#   2. Rode primeiro em modo dry-run (padrão) para conferir o que seria feito:
#        bash scripts/cleanup_vm_logs.sh
#   3. Rode de fato com a flag --yes:
#        bash scripts/cleanup_vm_logs.sh --yes

set -euo pipefail

# ============================== CONFIGURAÇÃO ==============================
VM_USER="PREENCHER_USUARIO"          # ex: sti
VM_HOST="PREENCHER_IP_OU_HOST"       # ex: 10.11.8.25
VM_REMOTE_DEPLOY_DIR="PREENCHER_CAMINHO"   # ex: /home/sti/Deploy_PF
# ============================================================================

CONFIRM="${1:-}"
VM_REMOTE_LOGS_DIR="${VM_REMOTE_DEPLOY_DIR}/logs"
BACKUP_DIR_NAME="logs_backup_$(date +%Y%m%d_%H%M%S)"

if [[ "$VM_USER" == "PREENCHER_USUARIO" || "$VM_HOST" == "PREENCHER_IP_OU_HOST" || "$VM_REMOTE_DEPLOY_DIR" == "PREENCHER_CAMINHO" ]]; then
    echo "ERRO: preencha VM_USER, VM_HOST e VM_REMOTE_DEPLOY_DIR no topo deste script antes de executar." >&2
    exit 1
fi

echo "Diretório remoto alvo: ${VM_USER}@${VM_HOST}:${VM_REMOTE_LOGS_DIR}"
echo ""
echo "Conteúdo atual (contagem de arquivos):"
ssh "${VM_USER}@${VM_HOST}" "find '${VM_REMOTE_LOGS_DIR}' -type f | wc -l"

if [[ "$CONFIRM" != "--yes" ]]; then
    echo ""
    echo "MODO DRY-RUN (nada foi alterado)."
    echo "Antes de prosseguir, confirme visualmente que admin_data/vm_logs/ (local)"
    echo "contém todos os arquivos listados acima."
    echo ""
    echo "Para executar de fato, rode: bash scripts/cleanup_vm_logs.sh --yes"
    exit 0
fi

echo ""
echo "Movendo conteúdo de ./logs para ./${BACKUP_DIR_NAME} e recriando ./logs vazio..."
ssh "${VM_USER}@${VM_HOST}" bash -s <<EOF
set -euo pipefail
cd "${VM_REMOTE_DEPLOY_DIR}"
mkdir -p "${BACKUP_DIR_NAME}"
# Move todo o conteúdo (inclusive .gitkeep se existir) preservando o diretório logs/ vazio
shopt -s dotglob nullglob
mv logs/* "${BACKUP_DIR_NAME}/" 2>/dev/null || true
shopt -u dotglob nullglob
echo "Feito. Backup em: ${VM_REMOTE_DEPLOY_DIR}/${BACKUP_DIR_NAME}"
echo "Arquivos restantes em logs/: \$(find logs -type f | wc -l)"
EOF

echo ""
echo "Limpeza concluída. O container opera-ia-frontend enxerga o mesmo ./logs"
echo "(bind mount), então nenhum reinício de container é necessário."
echo ""
echo "O backup ficou em ${VM_REMOTE_DEPLOY_DIR}/${BACKUP_DIR_NAME} na VM."
echo "Depois de validar que tudo está normal, apague-o manualmente se quiser:"
echo "  ssh ${VM_USER}@${VM_HOST} \"rm -rf '${VM_REMOTE_DEPLOY_DIR}/${BACKUP_DIR_NAME}'\""
