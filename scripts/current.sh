#!/usr/bin/env bash
# 检查或恢复现有双主机拓扑；不会隐式修改正在运行的主机。
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
 nas) FILES=(media/media.yaml photos/photos.yaml network/network.yaml dashboard/dashboard.yaml monitoring/monitoring.yaml notification/notification.yaml automation/automation.yaml);;
 macmini) FILES=(macmini/npm.yaml macmini/immich-ml.yaml);;
 *) echo 'host 必须是 nas 或 macmini'; exit 1;;
esac

[[ -f "$ROOT/.env" ]] || { echo '请复制 .env.example 为 .env 并填写参数。'; exit 1; }
# 通过 Compose 自身解析 .env，不 source 不可信的变量文件。
if grep -Eq '^[A-Za-z_][A-Za-z0-9_]*=.*REPLACE_' "$ROOT/.env"; then
 echo '根 .env 仍有 REPLACE_ 占位符，请先填写。'; exit 1
fi

compose() { docker compose --env-file "$ROOT/.env" -f "$ROOT/$1" "${@:2}"; }

for file in "${FILES[@]}"; do compose "$file" config --quiet; done

# 检查所有本地绑定挂载与私有模板，避免 up 时才发现缺目录。
command -v python3 >/dev/null || { echo '需要 python3 校验挂载目录。'; exit 1; }
for file in "${FILES[@]}"; do
 compose "$file" config --format json | python3 "$ROOT/scripts/validate-mounts.py"
done

if [[ "$ACTION" == check ]]; then echo '全部编排、挂载路径及私有配置检查通过。'; exit 0; fi

# 共享网络必须已显式恢复（见 docs/restore.md）。
if [[ "$HOST" == nas ]]; then
 for net in homelab_application_default homelab_maintenance_default homelab_network qb_control qb_direct_lan; do
  docker network inspect "$net" >/dev/null
 done
fi

for file in "${FILES[@]}"; do compose "$file" pull; done
for file in "${FILES[@]}"; do compose "$file" up -d --wait --wait-timeout 600; done
for file in "${FILES[@]}"; do compose "$file" ps; done
