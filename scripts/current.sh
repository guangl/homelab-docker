#!/usr/bin/env bash
# Check or restore current topology; never implicitly modify existing live hosts.
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ACTION=${1:-help}
HOST=${2:-nas}
if [[ "$ACTION" == help || "$ACTION" == --help ]]; then
 echo '用法：bash scripts/current.sh check|apply nas|macmini'
 echo '先填写根 .env、准备恢复目录与私有配置；详见 docs/restore.md。'
 exit 0
fi
[[ "$ACTION" == check || "$ACTION" == apply ]] || { echo '未知动作'; exit 1; }
case "$HOST" in
 nas) FILES=(photos media notification monitoring automation media-status dashboard);;
 macmini) FILES=(network npm immich-ml);;
 *) echo 'host 必须是 nas 或 macmini'; exit 1;;
esac
[[ -f "$ROOT/.env" ]] || { echo '请复制 .env.example 为 .env 并填写参数。'; exit 1; }
# Parse values through Docker Compose itself; do not source untrusted .env as shell code.
if grep -Eq '^[A-Za-z_][A-Za-z0-9_]*=.*REPLACE_' "$ROOT/.env"; then
 echo '根 .env 仍有 REPLACE_ 占位符，请先填写。'; exit 1
fi
if docker compose version >/dev/null 2>&1; then
 COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null && docker-compose version --short | grep -Eq '^v?2\.'; then
 COMPOSE=(docker-compose)
else
 echo '需要 Docker Compose v2（docker compose 或 docker-compose）。'; exit 1
fi
compose() { "${COMPOSE[@]}" --env-file "$ROOT/.env" -f "$ROOT/deploy/$HOST/$1.yaml" "${@:2}"; }
for file in "${FILES[@]}"; do compose "$file" config --quiet; done
# Verify every local bind source and private template before any up/pull operation.
# --format json is parsed using standard Python, avoiding a separate YAML dependency.
command -v python3 >/dev/null || { echo '需要 python3 校验挂载目录。'; exit 1; }
for file in "${FILES[@]}"; do
 compose "$file" config --format json | python3 "$ROOT/scripts/validate-mounts.py"
done
if [[ "$ACTION" == check ]]; then echo '全部编排、挂载路径及私有配置检查通过。'; exit 0; fi
# Required external networks must already be explicitly restored (see docs/restore.md).
if [[ "$HOST" == nas ]]; then
 for net in qb_control qb_direct_lan homelab_application_default homelab_maintenance_default; do docker network inspect "$net" >/dev/null; done
fi
for file in "${FILES[@]}"; do compose "$file" pull; done
for file in "${FILES[@]}"; do compose "$file" up -d --wait --wait-timeout 600; done
for file in "${FILES[@]}"; do compose "$file" ps; done
