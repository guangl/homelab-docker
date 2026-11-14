#!/usr/bin/env bash
# Plan, validate, or restore the Compose services for one Docker host.
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

usage() {
  cat <<'USAGE'
用法：bash scripts/current.sh plan|check|apply [nas|macmini]

  plan   列出目标主机的 Compose 文件和处理顺序，无需 Docker 或 .env
  check  校验编排、挂载、私有配置及外部网络
  apply  检查通过后拉取镜像，逐组启动并显示状态

主机默认是 nas。check 和 apply 请在目标 Docker 主机执行，恢复步骤见 docs/restore.md。
USAGE
}

fail() {
  printf '错误：%s\n' "$*" >&2
  exit 1
}

ACTION=${1:-help}
HOST=${2:-nas}
[[ $# -le 2 ]] || fail '参数过多，请运行 --help。'

case "$ACTION" in
  help|--help|-h) usage; exit 0 ;;
  plan|check|apply) ;;
  *) fail "未知动作 $ACTION，请运行 --help。" ;;
esac

case "$HOST" in
  nas)
    FILES=(
      photos/photos.yaml
      media/media.yaml
      notification/notification.yaml
      monitoring/monitoring.yaml
      automation/automation.yaml
      media/workflow/media-arrival-status/status.yaml
      dashboard/dashboard.yaml
    )
    ;;
  macmini)
    FILES=(
      macmini/network.yaml
      macmini/npm.yaml
      macmini/immich-ml.yaml
    )
    ;;
  *) fail '主机必须是 nas 或 macmini。' ;;
esac

if [[ "$ACTION" == plan ]]; then
  printf '目标主机：%s\nCompose 文件（按处理顺序）：\n' "$HOST"
  printf '  %s\n' "${FILES[@]}"
  exit 0
fi

ENV_FILE="$ROOT/.env"
[[ -r "$ENV_FILE" ]] || fail '请复制根目录的 .env.example 为 .env 并填写本机参数。'
command -v python3 >/dev/null || fail '需要 Python 3 校验 Compose 配置。'
command -v docker >/dev/null || fail '需要 Docker CLI 检查外部网络。'

supports_compose() {
  local config_help up_help
  config_help=$("$@" config --help) || return 1
  up_help=$("$@" up --help) || return 1
  [[ "$config_help" == *--format* && "$up_help" == *--wait-timeout* ]]
}

if supports_compose docker compose 2>/dev/null; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null &&
     supports_compose docker-compose 2>/dev/null; then
  COMPOSE=(docker-compose)
else
  fail '需要支持 config --format 和 up --wait-timeout 的 Docker Compose。'
fi

# Bind sources are checked on this machine, so the Docker daemon must use a local socket.
if [[ -n "${DOCKER_HOST:-}" && -z "${DOCKER_CONTEXT:-}" ]]; then
  docker_endpoint=$DOCKER_HOST
else
  docker_endpoint=$(docker context inspect --format '{{.Endpoints.docker.Host}}') ||
    fail '无法读取当前 Docker 连接。'
fi
[[ "$docker_endpoint" == unix:///* ]] ||
  fail '当前 Docker 连接未使用本地 Unix 套接字。请在目标主机执行。'

compose() {
  local file=$1
  shift
  # Keep the project names in Compose and preserve services managed by sibling files.
  COMPOSE_PROJECT_NAME='' COMPOSE_REMOVE_ORPHANS=false \
    "${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$ROOT/$file" "$@"
}

check_config() {
  local file networks all_networks='' network
  for file in "${FILES[@]}"; do
    printf '检查 %s\n' "$file"
    # Parse through Compose itself to resolve interpolation without sourcing .env.
    networks=$(compose "$file" config --format json |
      python3 "$ROOT/scripts/validate-mounts.py" --print-networks) ||
      fail "编排或挂载检查失败：$file"
    all_networks+=$'\n'"$networks"
  done

  while IFS= read -r network; do
    [[ -n "$network" ]] || continue
    docker network inspect "$network" >/dev/null ||
      fail "外部网络不可用：$network。请核对 docs/restore.md。"
  done < <(printf '%s\n' "$all_networks" | LC_ALL=C sort -u)
}

check_config
printf '目标主机 %s 的编排、挂载、私有配置和外部网络检查通过。\n' "$HOST"
[[ "$ACTION" == apply ]] || exit 0

# Finish all pulls before starting any group. Keep existing project siblings and volumes.
for file in "${FILES[@]}"; do
  compose "$file" pull || fail "镜像拉取失败：$file"
done
for file in "${FILES[@]}"; do
  compose "$file" up -d --wait --wait-timeout 600 || fail "启动或健康检查失败：$file"
done
for file in "${FILES[@]}"; do
  compose "$file" ps
done
