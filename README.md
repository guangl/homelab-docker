# homelab-docker

家庭 NAS（Synology，`192.168.10.5`）上全部 Docker 服务的 Compose 编排、配置与说明。
仓库根目录对应 NAS 上的 `/volume1/docker/homelab`，`git pull` 后即可按分类拉起服务。

## 1. 环境

| 项 | 值 |
| --- | --- |
| NAS | Synology DS925+，DSM 7.4.1，内核 5.10.55（**无 wireguard 内核模块**） |
| 主机地址 | `192.168.10.5`（本仓库内所有"本机"引用统一用这个） |
| 内网 | `192.168.10.0/24`，网关 192.168.10.1 |
| 旁路由 / 代理 | Surge `192.168.10.4`：HTTP `6152`、SOCKS5 `6153` |
| 媒体库 | `/volume1/entertainments`（仓库之外，保持绝对路径） |
| 文件所有权 | 服务统一 `PUID=1026 PGID=100`；例外：ani-rss / qbittorrent / uptime-kuma 用 root |
| 时区 | 全部 `TZ=Asia/Shanghai` |

## 2. 目录结构

```
.
├── .env                          # 本地密钥，不入库（首次部署由 .env.example 复制）
├── .env.example                  # 变量清单与说明
├── application/                  # 应用层（6100-6199）
│   ├── application.yaml
│   ├── jellyfin/                 # config/ cache/（运行时）
│   ├── ani-rss/                  # 运行时
│   ├── qbittorrent/              # config/ downloads/（运行时）
│   ├── immich/                   # library/（运行时）
│   ├── n8n/                      # data/（运行时）
│   └── trendradar/               # config/（入库） output/（运行时）
├── infrastructure/               # 基础设施
│   ├── infrastructure.yaml
│   ├── postgresql/               # initdb/（入库） data/（运行时）
│   └── redis/                    # data/（运行时）
├── maintenance/                  # 维护层（6000-6099）
│   ├── maintenance.yaml
│   ├── glance/config/            # Glance 配置（入库）
│   ├── ddns/  uptime-kuma/  peanut/config/   # 运行时
├── network/                      # 网络层（6200-6299）
│   ├── network.yaml
│   ├── wireguard/                # Dockerfile + entry.sh（入库） wg0.conf（不入库）
│   ├── smartdns/smartdns.conf    # 已停用，保留回滚
│   ├── adguardhome/              # work/ conf/（运行时）
│   └── dnsq/  tproxy/            # 部署时放入的脚本（运行时）
└── tools/                        # 工具层（6400-6499）
    ├── tools.yaml
    ├── grafana/provisioning/     # 数据源与仪表盘（入库） data/（运行时）
    └── prometheus/               # prometheus.yml（入库） data/（运行时）
```

**入库原则**：只提交需要审阅的配置（Glance、TrendRadar、PostgreSQL initdb、
WireGuard 构建文件、smartdns.conf）；运行时数据、密钥、日志由 [.gitignore](.gitignore) 排除。
所有凭据（数据库密码、AdGuard 账号、WAQI token、Telegram bot token）统一放在根目录
[`.env`](.env.example) 里，compose 用 `${VAR:?}` 插值，缺变量时直接报错而不是带默认口令启动。

## 3. 服务清单

### network（网络层，host 网络）

| 服务 | 容器名 | 镜像 | 端口 | 作用 |
| --- | --- | --- | --- | --- |
| adguardhome | adguardhome | `docker.1ms.run/adguard/adguardhome:latest` | 53/udp+tcp、6200(web) | 全屋 DNS + 广告过滤 |
| dnsq | dnsq | `python:3.11-slim-bookworm` | 6210（仅 127.0.0.1） | 国内外 DNS 分流 |
| tproxy | tproxy | `python:3.11-slim-bookworm` | 6212（仅本机） | TCP 透明转发到 Surge |
| filterhost | filterhost | `python:3.11-slim-bookworm` | 6213（仅 127.0.0.1） | 本地过滤列表静态服务 |
| wg-home | wg-home | 自建 `wg-home:latest` | 51820/udp | WireGuard 服务端（用户态） |

### infrastructure

| 服务 | 容器名 | 镜像 | 端口 | 作用 |
| --- | --- | --- | --- | --- |
| postgres | postgres | `ghcr.io/immich-app/postgres:17-vectorchord0.4.3-pgvectors0.3.0` | 65432→5432 | Immich 数据库（向量扩展） |
| redis | redis | `redis:latest` | 6379 | Immich 缓存，AOF 持久化 |

### maintenance

| 服务 | 容器名 | 镜像 | 端口 | 作用 |
| --- | --- | --- | --- | --- |
| glance | glance | `glanceapp/glance` | 6001→8080 | 首页面板（聚合 RSS/容器/DNS 等） |
| glances | glances | `nicolargo/glances:latest` | 6002→61208 | 资源监控 |
| ddns | ddns-go | `jeessy/ddns-go` | 6003→9876 | 动态域名 |
| uptime-kuma | uptime-kuma | `louislam/uptime-kuma:nightly2` | 6004→3001 | 可用性监控 |
| peanut | peanut | `brandawg93/peanut:latest` | 6005→8080 | 展示页 |
| watchtower | watchtower | `containrrr/watchtower:latest` | — | 每日 04:00 自动更新镜像，Telegram 通知 |

### application

| 服务 | 容器名 | 镜像 | 端口 | 作用 |
| --- | --- | --- | --- | --- |
| jellyfin | jellyfin | `jellyfin/jellyfin:latest` | 6100→8096 | 影音 |
| ani-rss | ani-rss | `wushuo894/ani-rss:latest` | 6101→9097 | 追番订阅，联动 qBittorrent；内存上限 1GiB |
| qbittorrent | qbittorrent | `ghcr.io/hotio/qbittorrent` | 6102→8080 | 下载 |
| excalidraw | excalidraw | `excalidraw/excalidraw:latest` | 6103→80 | 白板 |
| immich-server | immich-server | `ghcr.io/immich-app/immich-server:release` | 6104→2283 | 相册 |
| immich-machine-learning | — | `ghcr.io/immich-app/immich-machine-learning:release` | — | 相册 AI（模型缓存在命名卷） |
| drawdb | drawdb | `ghcr.io/drawdb-io/drawdb:latest` | 6105→80 | 数据库设计 |
| trendradar | trendradar | `wantcat/trendradar:latest` | 6106→3333 | 热榜聚合（每小时），Telegram 凭据来自 `.env` |
| n8n | n8n | `n8nio/n8n:latest` | 6107→5678 | 自动化工作流：Webhook、定时任务、把下载/通知/备份/相册串成流程 |

### tools（工具层）

| 服务 | 容器名 | 镜像 | 端口 | 作用 |
| --- | --- | --- | --- | --- |
| umami | umami | `ghcr.io/umami-software/umami:postgresql-latest` | 6400→3000 | 网站访问统计（给 blog 用） |
| grafana | grafana | `grafana/grafana-oss:latest` | 6402→3000 | 监控仪表盘（已预置 Node Exporter Full） |
| prometheus | prometheus | `prom/prometheus:latest` | — | 指标存储 |
| node-exporter | node-exporter | `prom/node-exporter:latest` | — | NAS 主机指标（CPU/内存/磁盘/网络） |

> 反向代理（`*.guangluo.top` → 各端口）由 NAS 上的 DSM 反向代理 / NPM 负责，不在本仓库。

## 4. 网络链路

```
DNS：客户端 → adguardhome:53 → dnsq:6210 → 国内 223.5.5.5
                                       └→ 国外 经 SOCKS 192.168.10.4:6153 → 1.1.1.1

代理：UDM 策略路由 → wg-home:51820 → tproxy:6212 → Surge SOCKS 192.168.10.4:6153
      （NAS 自身不走隧道；Glance 拉 RSS 用 HTTP_PROXY=192.168.10.4:6152）
```

- AdGuard Home 的 `http.address` 必须与 **6200** 一致，否则 Glance 的 `dns-stats` 面板取不到数据。
- 内网域名（`adguard/anime/ddns/photo/... .guangluo.top`）解析到 `192.168.10.5`。
- `smartdns` 已停用但保留配置用于回滚，当前 DNS 链路不经过它。

### AdGuard 过滤与登录

`AdGuardHome.yaml` 是运行时文件（`network/adguardhome/` 已 gitignore），登录账号在它的
`users:` 段里存 bcrypt hash，改完要 `docker restart adguardhome`；仓库里的 `.env` 只给
Glance 的 `dns-stats` 面板用，两处账号密码必须一致。

过滤规则在 AdGuard「过滤器 → DNS 黑名单」里管理，中文环境建议至少加这几条：

| 列表 | 地址 | 说明 |
| --- | --- | --- |
| AdGuard DNS filter | `https://adguardteam.github.io/AdGuardSDNSFilter/Filters/filter.txt` | 官方基础列表 |
| anti-AD | `https://anti-ad.net/adguard.txt` | 中文 App / 网站命中率高 |
| EasyList China | `https://easylist-downloads.adblockplus.org/easylistchina.txt` | 国内网页广告 |
| OISD small（可选） | `https://small.oisd.nl/domainswild` | 补充追踪器，误杀较少 |

验证是否真的在拦：

```bash
dig +short @192.168.10.5 doubleclick.net   # 应返回 0.0.0.0
```

列表都加了但拦截量仍偏低，通常是客户端绕过了 AdGuard：Chrome/Edge 的「安全 DNS」、
iOS 的 iCloud 私密中继、部分 App 内置 DoH 都会跳过系统 DNS。需要在 UDM 的 DHCP 里把
DNS 强制下发为 `192.168.10.5`，必要时再封掉 DoH 出网。

## 5. 部署

```bash
cd /volume1/docker/homelab
docker compose --env-file .env -f network/network.yaml up -d
docker compose --env-file .env -f infrastructure/infrastructure.yaml up -d
docker compose --env-file .env -f maintenance/maintenance.yaml up -d
docker compose --env-file .env -f application/application.yaml up -d
docker compose --env-file .env -f tools/tools.yaml up -d
```

`--env-file .env` 不能省：compose 默认只在 compose 文件所在目录找 `.env`，而本仓库
所有变量集中在仓库根。漏掉时命令会明确报 `required variable ... is missing a value`。

- `wg-home` 首次 `up -d` 会按 `build: ./wireguard` 自动构建；镜像已存在时不会重建，
  改过 Dockerfile 需要 `docker compose --env-file .env -f network/network.yaml up -d --build wg-home`。
  （`entry.sh` 是挂载进容器的，改脚本只需 `restart wg-home`。）
- 群晖 Container Manager 若用「项目」方式管理，项目路径要指向新的 compose 文件。

### 首次部署准备

先把变量模板复制成真实配置并收紧权限：

```bash
cp .env.example .env && chmod 600 .env && editor .env
```

| 变量 | 用途 |
| --- | --- |
| `POSTGRES_PASSWORD` | postgres 与 immich-server 共用的数据库密码，两边必须一致 |
| `ADGUARD_USERNAME` / `ADGUARD_PASSWORD` | Glance `dns-stats` 面板登录 AdGuard Home 用 |
| `WAQI_TOKEN` | Glance 空气质量面板的 aqicn token |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | watchtower 容器更新通知、TrendRadar 热榜推送 |
| `UMAMI_APP_SECRET` | umami 会话签名，`openssl rand -hex 32` 生成 |
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | grafana 管理员（首次启动建号） |

运行时目录不在版本库里，全新克隆需先创建（Docker 自动创建会归 root，可能影响
非 root 服务的写入）：

```bash
mkdir -p application/{jellyfin/{config,cache},ani-rss,qbittorrent/{config,downloads},immich/library,trendradar/output} \
         maintenance/{ddns,uptime-kuma,peanut/config} \
         infrastructure/{postgresql/data,redis/data} \
         network/{adguardhome/{work,conf},dnsq,tproxy} \
         tools/{grafana/{data,provisioning/dashboards},prometheus/data}
chown -R 1026:100 application maintenance/glance maintenance/peanut infrastructure network/adguardhome tools
chown -R 472:472 tools/grafana/data            # grafana 镜像内 uid 472
chown -R 65534:65534 tools/prometheus/data     # prometheus 镜像内 nobody
```

> Uptime Kuma 以 root 运行，数据目录不要一起改属主。

### 各服务入口（首次使用）

| 服务 | 地址 | 首次操作 |
| --- | --- | --- |
| Immich 相册 | `http://192.168.10.5:6104` | 打开页面注册第一个账号，自动成为管理员；手机装 Immich App 后填同一地址即可自动备份 |
| Jellyfin | `https://movie.guangluo.top` | 用 DSM 反向代理的域名，首次进后台加媒体库 `/entertainments` |
| Glance 面板 | `https://home.guangluo.top`（内网 `http://192.168.10.5:6001`） | 无需登录，配置改完会自动热重载 |
| AdGuard Home | `http://192.168.10.5:6200` | 账号密码见 `.env` 的 `ADGUARD_USERNAME` / `ADGUARD_PASSWORD` |
| Umami 统计 | `http://192.168.10.5:6400` | 默认账号 `admin` / `umami`，登录后先改密码；在「网站」里新建站点拿埋点脚本 |
| Grafana 监控 | `http://192.168.10.5:6402` | 账号 `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`；已预置「家庭监控 / Node Exporter Full」看 NAS 指标 |

> Immich 的相册数据在 `application/immich/library`；如果想让现有 `/volume1/photos` 里的照片直接纳入，
> 在 Immich 后台「外部库」里加 `/volume1/photos`（compose 已把 `/volume1/entertainments` 挂进容器，
> 需要时把该路径也加进 `application.yaml` 的 volumes）。

## 6. 为什么 WireGuard 要自己打镜像

群晖 DSM 内核（5.10.55）**没有 wireguard 内核模块**，只能跑用户态实现：

- 现成镜像（`lscr.io/linuxserver/wireguard`、`ghcr.io/wg-easy/wg-easy` 等）都依赖内核模块，
  在这台 NAS 上起不来；
- `network/wireguard/Dockerfile` 因此只装 `alpine:3.22` + `wireguard-tools-wg-quick` +
  `wireguard-go` + `iptables`（Alpine 把 `wg-quick` 拆成了独立子包，只装
  `wireguard-tools` 会得到 `wg-quick: not found`）；
- `entry.sh` 负责：开 `net.ipv4.ip_forward`、`wg-quick up`、按默认路由出口网卡做 MASQUERADE、
  放行 FORWARD、每 60s 检查接口并在丢失后自动重建；
- 用户态吞吐低于内核模块（家用足够）。换到有内核模块的机器时可直接改用
  `linuxserver/wireguard`，删掉这里的自建镜像即可。

`wg0.conf`（含私钥、peer）放在 `network/wireguard/wg0.conf`，不入库。

## 7. 日常运维

```bash
docker compose --env-file .env -f application/application.yaml ps        # 状态
docker compose --env-file .env -f application/application.yaml logs -f   # 日志
docker compose --env-file .env -f application/application.yaml pull && ... up -d   # 手动更新
```

- 自动更新：watchtower 每天 04:00 清理并更新所有容器，结果推送到 Telegram。
- 需要备份的目录（其余是可重建的缓存）：
  - `application/jellyfin/config`、`application/immich/library`、`application/trendradar/config`
  - `maintenance/{glance/config,uptime-kuma,ddns,peanut/config}`
  - `infrastructure/postgresql/{data,initdb}`（或定期 `pg_dumpall`）
  - `network/{adguardhome,wireguard/wg0.conf}`
  - `tools/grafana/data`（Grafana 的看板/账号/偏好）

## 8. 排查

| 现象 | 排查 |
| --- | --- |
| `wg-quick: not found` | 镜像重建时用了旧 Dockerfile；确认装了 `wireguard-tools-wg-quick` 后 `up -d --build` |
| VPN 连上但上不了网 | `docker logs wg-home` 看出口网卡是否为 `bond0/ovs_eth0/eth0`；`ip route show default` 确认默认路由 |
| 端口被占用 | `ss -tlnp` 配合 grep 查端口，注意 DSM 自带服务（53 常被 DNS Server 占用） |
| Glance 容器面板空白 | 需要 `/var/run/docker.sock`；Glance 面板配置在 `maintenance/glance/config/` |
| Glance DNS 面板无数据 | AdGuard `http.address` 必须是 6200，且 `.env` 的 `ADGUARD_USERNAME`/`ADGUARD_PASSWORD` 与 AdGuard 实际账号一致 |
| Immich 起不来 | 先起 infrastructure；确认 `DB_HOSTNAME=192.168.10.5`、`DB_PORT=65432`、`immichdb` 已由 initdb 创建 |
| 容器写入权限报错 | 运行时目录属主是否为 `1026:100`（root 服务除外） |
| compose 报 `required variable ... is missing a value` | 命令漏了 `--env-file .env`，或根目录 `.env` 缺该项（对照 `.env.example`） |
| Grafana 长时间 000 / `GF_PATHS_DATA is not writable` | 首启迁移较慢（3-5 分钟属正常）；`tools/grafana/data` 属主必须是 `472:472` |
| Prometheus 报 `/prometheus/queries.active: permission denied` | `tools/prometheus/data` 属主改成 `65534:65534` |

## 9. 密钥管理

ANI-RSS 的内存上限为 `1024M`。原 `256M` 限制曾触发容器内存不足，导致 Java 被系统杀死并反复重启；部署时保留此限制以避免复发。

公开仓库前必须同时检查当前配置和全部 Git 历史。`.gitignore` 只阻止后续误提交，不能清除历史凭据。历史中出现过的真实凭据应先撤销或轮换，并清理相关历史；运行时 `.env`、API key、WireGuard 配置和反向隧道私钥始终保存在仓库外。

凭据不再写进 compose 或配置文件，统一由仓库根 `.env` 提供（`.gitignore` 已排除，
`.env.example` 只放占位符）。compose 里用 `${VAR:?提示}` 引用，变量缺失即报错退出，
不会带着默认口令起来。

| 变量 | 消费方 |
| --- | --- |
| `POSTGRES_PASSWORD` | `infrastructure.yaml` 的 postgres、`application.yaml` 的 immich-server |
| `ADGUARD_USERNAME` / `ADGUARD_PASSWORD` | `maintenance.yaml` → Glance，`widget/dns_stats.yml` 用 `${}` 引用 |
| `WAQI_TOKEN` | `maintenance.yaml` → Glance，`widget/air_quality.yml` |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | `maintenance.yaml` 的 watchtower、`application.yaml` 的 trendradar |

Glance 与 TrendRadar 都原生支持环境变量（Glance 在配置里展开 `${VAR}`，TrendRadar
环境变量优先级高于 `config.yaml` 的同名项），所以配置文件中只留空值/引用。

**历史遗留**（旧提交里仍是明文，删掉文件不等于删掉历史）：

- Telegram bot token 曾明文进过仓库 → 到 @BotFather `/revoke` 重新生成，写进 `.env`。
- `POSTGRES_PASSWORD` 曾使用弱口令 → 改 `.env` 后还需改库内口令：
  `docker exec -it postgres psql -U postgres -c "ALTER USER postgres PASSWORD '新密码';"`，
  然后重建 immich-server。
- AdGuard 的登录密码同时存在 `network/adguardhome/conf/AdGuardHome.yaml`（运行时文件，
  未入库），改 `.env` 时两处要同步。

## 10. 与旧布局的差异

| 旧位置 | 新位置 |
| --- | --- |
| `compose/{network,infrastructure,maintenance,application}.yaml` | `<分类>/<分类>.yaml` |
| `compose/wireguard/` | `network/wireguard/` |
| `glance/` | `maintenance/glance/config/` |
| `postgresql/init.d/` | `infrastructure/postgresql/initdb/` |
| `trendradar/` | `application/trendradar/config/` |
| `smartdns/` | `network/smartdns/` |

同时修正：主机地址 `192.168.15.x` → `192.168.10.5`；Glance DNS 统计 `7000` → `6200`；
移除失效的 `dnstcp` 与重复的 AdGuard 面板；挂载全部改为相对 compose 文件的
`./<service>/...`（解析后与旧绝对路径一致，**无需迁移数据**）。

## 11. License

见 [LICENSE](LICENSE)。
