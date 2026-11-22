# 当前拓扑恢复说明

基础清单核验于 2026-11-06（Asia/Shanghai）。NAS 合并后的编排核验于 2026-11-22。

| 主机 / 文件 | 容器 | 项目名 |
| --- | --- | --- |
| photos/photos.yaml | immich-server、immich-database、immich-redis | homelab_application |
| homeassistant/compose.yaml | homeassistant | homeassistant |
| media/media.yaml | ani-rss、qbittorrent、media-sublarr、media-emby | homelab_application |
| collect-metadata/compose.yaml | collect-metadata-web-1 | collect-metadata |
| dashboard/dashboard.yaml | glance | homelab_maintenance |
| monitoring/monitoring.yaml | glances、uptime-kuma | homelab_maintenance |
| notification/notification.yaml | apprise | homelab_maintenance |
| automation/automation.yaml | watchtower | homelab_maintenance |
| macmini/network.yaml | adguardhome、smartdns | homelab_network |
| macmini/npm.yaml | nginx-proxy-manager | npm |
| macmini/immich-ml.yaml | immich-machine-learning | immich-ml |
| macmini/collect-metadata.yaml | collect-metadata-db-1 | collect-metadata |

文件按功能目录归档，Mac mini 配置集中在 `macmini/`。同主机有多个文件共用项目名，禁止 `--remove-orphans`；NAS 与 Mac mini 不能合并到同一 Docker 主机。`docs/inventory.json` 保留合并前的盘点记录。恢复时以本页和当前 Compose 文件为准。NAS 的两个 Document Viewer 容器由 DSM 套件管理，恢复套件即可，不手工创建。

## 私有配置与数据

1. 复制根 `.env.example` 为 `.env`，权限设为 `600`，填写所有实际参数。原有 `.env` 不自动重写；更新时需补齐 `DNS_ROOT`、`APPRISE_USER`、`EMBY_API_KEY`、`IMMICH_API_KEY`、`UNIFI_API_KEY` 等当前字段。Glance 已统一使用根 `.env` 和 `EMBY_API_KEY`，不再使用旧 `dashboard/.env.glance`。
2. 恢复 NAS `HOMELAB_ROOT`（默认 `/volume1/docker/homelab`）及 `MEDIA_ROOT`。将 `photos/templates/immich/postgresql.conf` 复制到 `HOMELAB_ROOT/photos/immich/postgresql.conf`，将 `notification/templates/` 的内容复制到 `HOMELAB_ROOT/notification/`。`media/workflow/` 中的服务脚本与补丁、`dashboard/glance/config/` 按相对路径复制到 `HOMELAB_ROOT`。保留已有配置，不能直接覆盖现网文件。
3. NAS 私有模板去掉 `.example` 后恢复真实参数：`media/templates/ani-rss/config.v2.json.example` → `media/ani-rss/config.v2.json`、`media/templates/qbittorrent/qBittorrent.conf.example` → `media/qbittorrent/config/qBittorrent.conf`。通知目标、登录信息、API key、token 均需自己的备份；qB 登录密码 hash 不能填明文密码。
4. 从私有备份恢复 Emby、Sublarr、Ani-RSS、qBittorrent、Kuma、Apprise 的配置/数据库，以及 `photos/immich/data` 和 `photos/immich/postgres`。`DB_PASSWORD` 必须与现有数据库一致。不要对运行中的数据库目录作普通文件复制来代替一致性备份。
5. Sublarr 将 `media/workflow/sublarr-overrides/` 中的 Python 补丁逐个挂载到容器，完整清单以 `media/media.yaml` 为准。不要省略补丁挂载或未经验证替换镜像。数据库非 root entrypoint、PostgreSQL 配置及 tmpfs 也按现网保留。
6. Mac mini 恢复 `DNS_ROOT`（默认 `/Users/guang/dsh-data/homelab-migrate/network`）。把 `network/templates/` 的内容放到 `DNS_ROOT`，AdGuardHome.yaml.example、smartdns.conf.example 去掉后缀。填写 AdGuard bcrypt 密码 hash 和私有代理入口 bootstrap 域名；未使用的 bootstrap 行可删除，不能保留 `REPLACE_`。DNS 对外由 AdGuard 在 Mac mini 提供，SmartDNS 监听 `127.0.0.1:6053`。host 网络依赖当前 OrbStack 能力，迁移到其他运行时需重新核对。
7. Mac mini 恢复 `NPM_ROOT/data/nginx-proxy-manager/{data,letsencrypt}` 和 `ML_ROOT/model-cache`。`macmini/npm-proxy-hosts.json` 是当前启用路由的参考导出，已排除失效 draw/read，不是 NPM 数据库备份；没有数据库/证书备份时需重建规则和证书。
8. 恢复媒体到达定时任务和 Collect Metadata 的 `collect-metadata/media-arrival` 状态目录及令牌。Glance 通过 Docker 内网的 `collect-metadata-status:7099` 读取状态。宿主任务使用独立令牌调用共享翻译服务和 Collect Metadata 的写回接口。
9. 从私有备份恢复 Apprise 的持久化 `nas` 配置，将现有 `email` 标签指向 Telegram。Ani-RSS、Uptime Kuma、Watchtower 继续经 Apprise 的 `/notify/nas` 发送。

权限按服务要求恢复。应用常用 NAS `1026:100`。qBittorrent 使用 `0:0`，Sublarr 使用镜像默认 root。所有 bind mount 要求预先创建路径。

### Home Assistant 和 C700

- 从私有备份恢复 `HOMELAB_ROOT/homeassistant/config`，包括设备配置、`secrets.yaml`、`.storage`、自定义集成和仪表盘素材。将 `automation/homeassistant/xiaomi_oauth_mdns` 复制到 `config/custom_components/`，在 HA 配置中设置 `xiaomi_oauth_mdns.address` 为 NAS 的家庭网 IP。
- 恢复 Immich PostgreSQL 实例内 HA 的专用数据库及用户。HA recorder 使用网桥地址 `172.30.154.2:5432`。在 PostgreSQL 的 `pg_hba.conf` 中仅为 HA 的角色与数据库允许来自网桥网关 `172.30.154.1/32` 的 SCRAM 认证。
- 从私有备份恢复 `HOMELAB_ROOT/homeassistant/go2rtc/go2rtc.yaml`，模板见 `homeassistant/templates`。将 C700 PTZ 定制二进制 `go2rtc-ptz-d0e26d1633a9` 放入同目录并保留执行权限，SHA-256 为 `2a4b5a28c0ddd290b1c92da8138f5a10f7d6a9a59aec1e7a6bae7cdf4cb5decf`。将可执行的 `automation/homeassistant/go2rtc-c700/run` 复制到 `HOMELAB_ROOT/homeassistant/integrations/go2rtc-c700/run`。go2rtc 在 HA 容器内启动，API 和 RTSP 分别使用 `19841` 和 `18557`。

### Collect Metadata

- 先在 Mac mini 恢复外部卷 `collect-metadata_postgres_data`，其中包含 PostgreSQL 数据、访问规则和服务端 TLS 配置。从 `macmini/templates/collect-metadata/db.env.example` 生成 `MACMINI_HOMELAB_ROOT/collect-metadata/db.env`，填写现有数据库密码并设为 `600`。运行中的数据库继续使用原 Docker 卷，编排位于 `MACMINI_HOMELAB_ROOT/collect-metadata/compose.yaml`。
- 从私有备份恢复 NAS `HOMELAB_ROOT/collect-metadata/.releases/20261122-automatic-scrape/` 下的 `pg-tls`、`config`、`output` 和 `events`。恢复 Collect Metadata 的私有 `.env`、`translation/bridge.env` 及 `translation/state`。参照 `collect-metadata/translation/bridge.env.example` 更新翻译地址并保留令牌。
- Collect Metadata Web 镜像包含私有媒体 worker。恢复 `HOMELAB_ROOT/media/emby/private-metadata/` 下的 `emby-key`、`translation-model`、`portraits/portraits.py` 及 `synopsis-translation/{token,state}`。
- 共享翻译服务由 Sublarr 启动，使用现有 Sublarr PostgreSQL 配置。将 [Collect Metadata 源码](https://github.com/guangl/collect-metadata) 中的 `tools/metadata_translation_bridge.py` 和 `tools/sublarr_runtime.py` 复制到 `HOMELAB_ROOT/metadata-translation/sublarr-runtime/`，从私有备份恢复相邻的 `episodes/{token,state}`。Collect Metadata、私有媒体和番剧任务各用独立令牌，无每日翻译额度。翻译端口 `7100` 仅通过 Docker 网络访问。
- 恢复前加载 Compose 指定的 NAS 本地镜像 `homelab/collect-metadata:private-worker-20261122` 和 `homelab/sublarr:1.18.3-pg18-client`。Collect Metadata 仓库内含组合镜像的构建定义。
- Sublarr 的 `search-one-query.py`、`wanted-search-process.py`、`mediaserver-jellyfin.py` 和 `scheduler-core.py` 从当前部署备份恢复到 `HOMELAB_ROOT/media/workflow/sublarr-overrides/`。

## 根环境配置

| 参数 | 用途 |
| --- | --- |
| `HOMELAB_ROOT` | NAS 上的应用数据与宿主脚本根目录。各 NAS 服务从此处挂载私有配置、数据库和支持文件。 |
| `MEDIA_ROOT` | NAS 上的媒体根目录。媒体服务共享这个目录，Immich 另从其中挂载 `Photos`。 |
| `HA_HOST_IP` | HA 健康检查和 Xiaomi OAuth mDNS 公布的 NAS 地址。 |
| `METADATA_NAS_IP` | Collect Metadata Web 在 NAS 上发布端口的地址。 |
| `SUBLARR_DATABASE_URL` | Sublarr 的现有 PostgreSQL 连接地址，含凭据，保存在 NAS 私有 `.env`。 |
| `METADATA_DB_HOST` | Collect Metadata Web 连接 PostgreSQL 的地址，应与 TLS 服务端证书匹配。 |
| `MACMINI_HOMELAB_ROOT` | Mac mini 的 homelab 数据根目录，Collect Metadata PostgreSQL 从该目录读取私有环境文件。 |
| `DNS_ROOT` | Mac mini 上存放 AdGuard Home 和 SmartDNS 配置及工作数据的目录。 |
| `NPM_ROOT` | Mac mini 上的 Nginx Proxy Manager 根目录，编排从其下挂载代理数据和证书。 |
| `ML_ROOT` | Mac mini 上的 Immich 机器学习根目录，其下的 `model-cache` 保存下载的模型。 |
| `DB_PASSWORD` | Immich 连接 PostgreSQL 所用的密码。恢复已有数据库时填原密码。 |
| `IMMICH_MACHINE_LEARNING_URL` | NAS 上的 Immich 访问机器学习服务的地址，默认指向 Mac mini 的 3003 端口。 |
| `IMMICH_API_KEY` | Glance 读取 Immich 统计数据使用的密钥。 |
| `EMBY_API_KEY` | Glance 读取 Emby 统计数据使用的密钥，宿主媒体脚本也会读取它。 |
| `UNIFI_API_KEY` | Glance 查询 UniFi 的密钥。 |
| `ADGUARD_USERNAME` | Glance 查询 AdGuard Home 统计所用的登录用户名。 |
| `ADGUARD_PASSWORD` | 同一账号的登录密码，与 AdGuard 配置文件里保存的 bcrypt hash 对应。 |
| `WAQI_TOKEN` | Glance 的空气质量组件调用 WAQI 接口的令牌。 |
| `APPRISE_USER` | Apprise 对外接口的认证用户名。 |
| `APPRISE_PASSWORD` | Apprise 对外接口的认证密码。 |
| `WATCHTOWER_NOTIFICATION_URL` | Watchtower 报告的 Shoutrrr 发送地址，通常包含通知凭据。 |

`${变量:-默认值}` 表示变量缺失或为空时使用默认值。`${变量:?提示}` 要求变量存在且非空。路径应填写目标主机上的绝对路径。密钥与密码填在目标主机的私有 `.env` 中。

番剧定时任务从 NAS 的 `secrets/media-arrival-tmdb` 读取 TMDB 凭据。通过 `ssh -t nas 'sudo -n python3 /volume1/docker/homelab/media/workflow/media-arrival-tools/tmdb_credentials.py'` 无回显输入 API Key 或 Read Access Token。工具验证 TMDB 可用性后以 `600` 权限更新私有文件。

## Compose 配置字段

| 字段 | 含义 |
| --- | --- |
| `name`、`services`、`container_name` | 分别是 Compose 项目名、服务清单及显式指定的 Docker 容器名。 |
| `image` | 容器镜像。带 `@sha256:` 的引用固定到指定镜像摘要。 |
| `command`、`entrypoint`、`environment` | 分别控制启动命令参数、入口程序和容器内环境变量。 |
| `ports`、`network_mode: host` | `宿主端口:容器端口` 将容器端口发布到宿主机。Host 模式直接使用宿主网络。 |
| `volumes` | 挂载列表。Bind 挂载的 `source` 是宿主路径，`target` 是容器路径，`read_only` 限制写入，`create_host_path: false` 要求源路径预先存在。 |
| `tmpfs` | 临时内存文件系统，容器停止后其中的数据会丢失。 |
| `depends_on`、`healthcheck` | 前者定义启动依赖。设置 `service_healthy` 时等待依赖的健康检查通过。 |
| `restart`、`logging` | 分别控制容器重启策略和日志驱动。日志的 `max-size`、`max-file` 控制轮转大小和保留数量。 |
| `user`、`cap_add` | 指定容器进程的用户和组，以及额外授予的 Linux 能力。 |
| `mem_limit`、`deploy.resources.limits.memory` | 容器可用内存的上限。 |
| `networks`、`external: true` | 服务接入的 Docker 网络。标为外部的网络需要提前建立，`name` 指定 Docker 中实际查找的名称。 |

## Docker 网络

NAS 使用以下外部网络，先核对网段与父接口，仅创建缺失网络。不要删除或重建现网网络。网络参数应以目标主机实测为准：

```sh
docker network create --driver bridge --subnet 172.19.0.0/16 --gateway 172.19.0.1 homelab_application_default
docker network create --driver bridge --subnet 172.18.0.0/16 --gateway 172.18.0.1 homelab_maintenance_default
docker network create --driver bridge --internal --subnet 172.30.61.0/24 qb_control
docker network create --driver bridge --internal --subnet 172.30.154.0/29 --gateway 172.30.154.1 homeassistant_recorder
docker network create --driver bridge --subnet 172.29.0.0/16 --gateway 172.29.0.1 collect-metadata_translation
docker network create --driver bridge --subnet 192.168.64.0/20 --gateway 192.168.64.1 private-metadata_synopsis
docker network create --driver macvlan --subnet 192.168.10.0/24 --ip-range 192.168.10.6/32 --gateway 192.168.10.1 -o parent=bond0 qb_direct_lan
```

`bond0` 必须按目标网卡修改。qB 固定使用 `192.168.10.6` 和 `172.30.61.2`，DNS 已改为 `192.168.10.4`，不再依赖 NAS 上的 `172.30.61.1` DNS。宿主机默认不能访问自身 macvlan 容器，现有看板通过 Mac mini NPM 访问下载器。

Mac mini 的 NPM 和 Immich 机器学习分别使用 `npm_default` 与 `immich-ml_default` 外部网络。按原备份参数恢复这两个网络。脚本按解析后的 Compose 配置收集各主机所需的外部网络。

## 检查与启动

```sh
# 在 NAS：
bash scripts/current.sh plan nas
bash scripts/current.sh check nas
bash scripts/current.sh apply nas
# 在 Mac mini：
bash scripts/current.sh plan macmini
bash scripts/current.sh check macmini
bash scripts/current.sh apply macmini
```

- `plan` 按执行顺序列出编排文件，可离线运行。省略主机参数时默认使用 `nas`。
- `check` 需要 Docker、本地 Unix 套接字、支持 `config --format json` 和 `up --wait-timeout` 的 Docker Compose，以及 Python 3。它解析编排，检查挂载路径、主要配置文件、占位符、外部网络和卷，以及 `pull_policy: never` 指定的本机镜像。
- `apply` 通过相同预检后拉取所需镜像，再逐组启动，每组最多等待 600 秒，最后显示容器状态。启动某组失败时脚本停止，已启动的组继续运行。

不含健康检查的服务只能验证运行状态，还需核对首次登录、DNS、反代、媒体、通知和工作流。NAS Compose 保留当前服务之间实际连接的网络，恢复时不要擅自补回已断开的网络。

## 外部依赖与清理范围

Sing-box 网关及公网隧道已不在两台主机容器清单中，相关部署、密钥参数、二进制规则和旧增量规则片段已从仓库移除。Surge 配置、网关分流、DSM 本体和宿主媒体工作流需另行备份。仓库清理不会删除 NAS/Mac mini 文件、容器、卷或网络。

## 规则数据与证书

SmartDNS 的 `china-domains.txt` 与 CA 证书是公开支持数据；域名快照来源与 SHA256 见同目录 `provenance.json`。第三方数据和证书适用上游许可。Sublarr 补丁由当前运行主机导出，依附第三方应用，需要随镜像版本一并验证。
