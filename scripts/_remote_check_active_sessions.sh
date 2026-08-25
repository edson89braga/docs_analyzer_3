#!/usr/bin/env bash
# scripts/_remote_check_active_sessions.sh
#
# Lógica que roda DENTRO da VM (bash remoto). Não chame diretamente: é enviado via
# stdin pelo wrapper local `scripts/check_active_sessions.sh`, que faz o SSH.
#
# A tabela `active_sessions` vive no volume nomeado `opera_data` (/app/data dentro
# do container), não em bind mount — por isso a consulta precisa rodar via
# `docker exec`, dentro do container, e não lendo o arquivo direto da VM.

set -euo pipefail

CONTAINER="${CONTAINER:-opera-ia-frontend}"
DOCKER_CMD="${DOCKER_CMD:-docker}"

if ! $DOCKER_CMD ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    echo "Container '$CONTAINER' não está em execução ($DOCKER_CMD ps não o encontrou)." >&2
    echo "Defina CONTAINER=<nome> ou DOCKER_CMD='sudo docker' se necessário." >&2
    exit 1
fi

$DOCKER_CMD exec -i "$CONTAINER" python -m SOURCE.scripts.check_active_sessions "$@"
