#!/usr/bin/env bash
# Fresh Ubuntu/Debian deployment. Does not migrate existing data or DNS/gateway rules.
set -Eeuo pipefail
umask 077
trap 'echo "安装未完成（第 $LINENO 行）。已生成的配置和数据会保留，可修复后重试。" >&2' ERR
[[ "${1:-}" != --help ]] || { echo 'sudo bash install-linux-core.sh [绝对安装路径，默认 /opt/homelab]'; exit 0; }
[[ $(uname -s) == Linux && $EUID == 0 ]] || { echo '请在 Linux 上使用 sudo bash 运行。' >&2; exit 1; }
source /etc/os-release
case "$ID" in ubuntu|debian) ;; *) echo '目前支持 Ubuntu / Debian。'; exit 1;; esac
case "$(uname -m)" in x86_64|aarch64) ;; *) echo '需要 x86_64 或 ARM64。'; exit 1;; esac
DEST=${1:-/opt/homelab}
[[ "$DEST" == /* && "$DEST" != / ]] || { echo '请指定非根目录的绝对路径。'; exit 1; }
if [[ -e "$DEST" && ! -f "$DEST/.homelab-linux-installer" ]]; then
 echo "目标已存在且不属于本安装器，请选择空的新路径：$DEST"; exit 1
fi
apt-get update
apt-get install -y ca-certificates curl openssl
if ! command -v docker >/dev/null; then
 for pkg in docker.io podman-docker containerd runc; do
  if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
   echo "发现现有 $pkg，请先自行处理 Docker 安装冲突。"; exit 1
  fi
 done
 install -m 0755 -d /etc/apt/keyrings
 curl -fsSL "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/homelab-docker.asc
 chmod a+r /etc/apt/keyrings/homelab-docker.asc
 printf 'deb [arch=%s signed-by=/etc/apt/keyrings/homelab-docker.asc] https://download.docker.com/linux/%s %s stable\n' "$(dpkg --print-architecture)" "$ID" "$VERSION_CODENAME" > /etc/apt/sources.list.d/homelab-docker.list
 apt-get update
 apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
docker info >/dev/null
docker compose version >/dev/null
mkdir -p "$DEST"
cd "$DEST"
touch .homelab-linux-installer
if [[ ! -f compose.yaml ]]; then
cat > compose.yaml <<'COMPOSE'
{
  "name": "homelab-linux",
  "services": {
    "emby": {
      "image": "emby/embyserver:latest",
      "restart": "unless-stopped",
      "volumes": [
        "emby:/config",
        "./media:/media"
      ],
      "environment": {
        "TZ": "Asia/Shanghai",
        "UID": "${PUID}",
        "GID": "${PGID}"
      },
      "ports": [
        "${BIND_IP:-127.0.0.1}:6100:8096"
      ]
    },
    "qbittorrent": {
      "image": "lscr.io/linuxserver/qbittorrent:latest",
      "restart": "unless-stopped",
      "volumes": [
        "qbittorrent:/config",
        "./media:/media"
      ],
      "environment": {
        "TZ": "Asia/Shanghai",
        "PUID": "${PUID}",
        "PGID": "${PGID}",
        "WEBUI_PORT": "8080"
      },
      "ports": [
        "${BIND_IP:-127.0.0.1}:6102:8080"
      ]
    },
    "ani-rss": {
      "image": "wushuo894/ani-rss:latest",
      "restart": "unless-stopped",
      "volumes": [
        "ani-rss:/config",
        "./media:/media"
      ],
      "environment": {
        "TZ": "Asia/Shanghai",
        "PUID": "${PUID}",
        "PGID": "${PGID}",
        "SERVER_PORT": "9097",
        "CONFIG": "/config"
      },
      "ports": [
        "${BIND_IP:-127.0.0.1}:6101:9097"
      ]
    },
    "glance": {
      "image": "glanceapp/glance:latest",
      "restart": "unless-stopped",
      "volumes": [
        "./glance:/app/config:ro"
      ],
      "environment": {
        "TZ": "Asia/Shanghai"
      },
      "ports": [
        "${BIND_IP:-127.0.0.1}:6001:8080"
      ]
    },
    "glances": {
      "image": "nicolargo/glances:latest",
      "restart": "unless-stopped",
      "volumes": [
        "/var/run/docker.sock:/var/run/docker.sock:ro"
      ],
      "environment": {
        "TZ": "Asia/Shanghai",
        "GLANCES_OPT": "-w"
      },
      "pid": "host",
      "ports": [
        "${BIND_IP:-127.0.0.1}:6002:61208"
      ]
    },
    "uptime-kuma": {
      "image": "louislam/uptime-kuma:2",
      "restart": "unless-stopped",
      "volumes": [
        "uptime-kuma:/app/data"
      ],
      "environment": {
        "TZ": "Asia/Shanghai"
      },
      "ports": [
        "${BIND_IP:-127.0.0.1}:6003:3001"
      ]
    },
    "apprise": {
      "image": "caronc/apprise:latest",
      "restart": "unless-stopped",
      "volumes": [
        "apprise:/config"
      ],
      "environment": {
        "TZ": "Asia/Shanghai"
      },
      "ports": [
        "${BIND_IP:-127.0.0.1}:8000:8000"
      ]
    },
    "nginx-proxy-manager": {
      "image": "jc21/nginx-proxy-manager:latest",
      "restart": "unless-stopped",
      "volumes": [
        "npm:/data",
        "letsencrypt:/etc/letsencrypt"
      ],
      "environment": {
        "TZ": "Asia/Shanghai"
      },
      "ports": [
        "${BIND_IP:-127.0.0.1}:80:80",
        "${BIND_IP:-127.0.0.1}:443:443",
        "${BIND_IP:-127.0.0.1}:7001:81"
      ]
    }
  },
  "volumes": {
    "emby": {},
    "qbittorrent": {},
    "ani-rss": {},
    "uptime-kuma": {},
    "apprise": {},
    "npm": {},
    "letsencrypt": {}
  }
}
COMPOSE
fi
mkdir -p immich glance media
if [[ ! -f immich/compose.yaml ]]; then
cat > immich/compose.yaml <<'IMMICH'
#
# WARNING: To install Immich, follow our guide: https://docs.immich.app/install/docker-compose
#
# Make sure to use the docker-compose.yml of the current release:
#
# https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
#
# The compose file on main may not be compatible with the latest release.

name: immich

services:
  immich-server:
    container_name: immich_server
    image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-release}
    # extends:
    #   file: hwaccel.transcoding.yml
    #   service: cpu # set to one of [nvenc, quicksync, rkmpp, vaapi, vaapi-wsl] for accelerated transcoding
    volumes:
      # Do not edit the next line. If you want to change the media storage location on your system, edit the value of UPLOAD_LOCATION in the .env file
      - ${UPLOAD_LOCATION}:/data
      - /etc/localtime:/etc/localtime:ro
    env_file:
      - .env
    ports:
      - '${BIND_IP:-127.0.0.1}:6104:2283'
    depends_on:
      - redis
      - database
    restart: always
    healthcheck:
      disable: false

  immich-machine-learning:
    container_name: immich_machine_learning
    # For hardware acceleration, add one of -[armnn, cuda, rocm, openvino, rknn] to the image tag.
    # Example tag: ${IMMICH_VERSION:-release}-cuda
    image: ghcr.io/immich-app/immich-machine-learning:${IMMICH_VERSION:-release}
    # extends: # uncomment this section for hardware acceleration - see https://docs.immich.app/features/ml-hardware-acceleration
    #   file: hwaccel.ml.yml
    #   service: cpu # set to one of [armnn, cuda, rocm, openvino, openvino-wsl, rknn] for accelerated inference - use the `-wsl` version for WSL2 where applicable
    volumes:
      - model-cache:/cache
    env_file:
      - .env
    restart: always
    healthcheck:
      disable: false

  redis:
    container_name: immich_redis
    image: docker.io/valkey/valkey:9@sha256:c123e3715db63d06d4ad6964884037aa0d5d4d703939b9929954112889708e1d
    healthcheck:
      test: redis-cli ping | grep -q PONG || exit 1
    restart: always

  database:
    container_name: immich_postgres
    image: ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0@sha256:bcf63357191b76a916ae5eb93464d65c07511da41e3bf7a8416db519b40b1c23
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_USER: ${DB_USERNAME}
      POSTGRES_DB: ${DB_DATABASE_NAME}
      POSTGRES_INITDB_ARGS: '--data-checksums'
      # Uncomment the DB_STORAGE_TYPE: 'HDD' var if your database isn't stored on SSDs
      # DB_STORAGE_TYPE: 'HDD'
    volumes:
      # Do not edit the next line. If you want to change the database storage location on your system, edit the value of DB_DATA_LOCATION in the .env file
      - ${DB_DATA_LOCATION}:/var/lib/postgresql/data
    shm_size: 128mb
    restart: always
    healthcheck:
      disable: false

volumes:
  model-cache:

IMMICH
fi
if [[ ! -f .env ]]; then
 printf 'BIND_IP=127.0.0.1\nPUID=%s\nPGID=%s\n' "${SUDO_UID:-1000}" "${SUDO_GID:-1000}" > .env
fi
if [[ ! -f immich/.env ]]; then
 printf 'UPLOAD_LOCATION=./library\nDB_DATA_LOCATION=./postgres\nTZ=Asia/Shanghai\nIMMICH_VERSION=release\nDB_PASSWORD=%s\nDB_USERNAME=postgres\nDB_DATABASE_NAME=immich\nBIND_IP=127.0.0.1\n' "$(openssl rand -hex 24)" > immich/.env
fi
if [[ ! -f glance/glance.yml ]]; then
cat > glance/glance.yml <<'GLANCE'
pages:
  - name: Homelab
    columns:
      - size: full
        widgets:
          - type: monitor
            cache: 1m
            title: Services
            sites:
              - title: Emby
                url: http://emby:8096
              - title: Immich
                url: http://immich-server:2283
              - title: qBittorrent
                url: http://qbittorrent:8080
              - title: Uptime Kuma
                url: http://uptime-kuma:3001
GLANCE
# Immich runs in its own Compose network; omit cross-network check.
 sed -i '/              - title: Immich/,+1d' glance/glance.yml
fi
# Media must be writable by the user configured for the download service.
PUID=$(sed -n 's/^PUID=//p' .env)
PGID=$(sed -n 's/^PGID=//p' .env)
[[ "$PUID" =~ ^[0-9]+$ && "$PGID" =~ ^[0-9]+$ ]]
chown "$PUID:$PGID" media
chmod 600 .env immich/.env
docker compose config --quiet
(cd immich && docker compose config --quiet)
# Pull both projects before starting any services.
docker compose pull
(cd immich && docker compose pull)
docker compose up -d --wait --wait-timeout 300
(cd immich && docker compose up -d --wait --wait-timeout 600)
docker compose ps
(cd immich && docker compose ps)
echo "安装完成：$DEST"
echo '默认仅本机访问。通过 SSH 转发访问，或将两个 .env 的 BIND_IP 改成服务器局域网 IP 后重新 up -d。'
echo '端口：Glance 6001 / Glances 6002 / Kuma 6003 / Emby 6100 / Ani-RSS 6101 / qBittorrent 6102 / Immich 6104 / NPM 7001 / Apprise 8000'
echo '首次登录需要分别创建账号；qBittorrent 临时密码见 docker compose logs qbittorrent。'
