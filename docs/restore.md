# 当前拓扑恢复说明

核验日期：2026-11-03（Asia/Shanghai）。仓库按现网功能目录组织，每个目录只有一个 Compose 入口。

## 部署单元

| 文件 | 容器 | 项目名 |
| --- | --- | --- |
| `media/media.yaml` | media-emby、ani-rss、qbittorrent、media-sublarr | homelab_application |
| `photos/photos.yaml` | immich-server、immich-database、immich-redis | homelab_application |
| `network/network.yaml` | adguardhome、smartdns、network-gateway、public-sites-tunnel | homelab_network |
| `dashboard/dashboard.yaml` | glance | homelab_maintenance |
| `monitoring/monitoring.yaml` | glances、uptime-kuma | homelab_maintenance |
| `notification/notification.yaml` | apprise、phone-notification-router | homelab_maintenance |
| `automation/automation.yaml` | watchtower | homelab_maintenance |
| `media/workflow/media-arrival-status/status.yaml` | media-arrival-status（不发布宿主端口） | homelab_media_status |
| `macmini/npm.yaml` | nginx-proxy-manager | homelab_network |
| `macmini/immich-ml.yaml` | immich-machine-learning | immich-ml |

media、photos、dashboard、monitoring、notification、automation 共享 `homelab_application` / `homelab_maintenance` 项目名，执行时不要添加 `--remove-orphans`，否则可能移除同项目的其他服务。

`media/media.yaml` 中 ani-rss 与 qbittorrent 固定为现网导入的本地镜像 `sha256`，新主机无法拉取；恢复时改成对应 registry 标签并核对版本。其余服务使用可拉取的 registry digest。NAS 与 Mac mini 的同名项目位于不同 Docker 主机，不能合并到同一主机部署。

## 私有文件和数据

1. 复制根 `.env.example` 为 `.env`，设置 `600`，填入接口密钥。`IMMICH_DB_PASSWORD` 必须与恢复的 Immich 数据库一致。
2. 把 `.example` 模板复制到运行目录并填真实值（不要覆盖现网配置）：
   - `media/templates/ani-rss/config.v2.json.example` → `media/ani-rss/config.v2.json`：下载器登录、API key、通知认证头。
   - `media/templates/qbittorrent/qBittorrent.conf.example` → `media/qbittorrent/config/qBittorrent.conf`：登录信息，示例不含旧密码 hash。
   - `photos/templates/immich/postgresql.conf` → `photos/immich/postgresql.conf`。
   - `network/templates/adguardhome/conf/AdGuardHome.yaml.example` → `network/adguardhome/conf/AdGuardHome.yaml`：填 bcrypt 密码 hash，不是明文。
   - `network/templates/sing-box/config.json.example` → `network/sing-box/config.json`：恢复 WireGuard 私钥与对端公钥。
   - `network/templates/smartdns/conf/` → `network/smartdns/conf/`。
   - `notification/templates/apprise/` → `notification/apprise/`。
   - `notification/templates/phone-routing/` → `notification/phone-routing/`：`router.json` 填邮件、Bark 与 Apprise 目标。
3. `dashboard/.env.glance.example` → `dashboard/.env.glance`，设置 `600`，填 `EMBY_API_KEY`、`UNIFI_API_KEY`、`IMMICH_URL`、`IMMICH_API_KEY`。Compose 插值读根 `.env`，Glance 容器另读该文件。
4. 恢复 Emby、Sublarr、Ani-RSS、qBittorrent、Uptime Kuma、Apprise 的配置与数据库，以及 Immich 相册和 PostgreSQL 数据。数据库需一致性备份；仅有 Git 配置不会恢复账号、订阅、监控项目和媒体记录。
5. 恢复公网隧道私钥与 `known_hosts` 到 `network/cloud-relay/secrets/`（权限 `600`），云端需已配置对应账号与远程转发许可。
6. Mac mini 需要恢复 NPM 的 `data`、`letsencrypt` 与机器学习 `model-cache`。`macmini/npm-proxy-hosts.json` 是路由配置导出，不是可直接导入的 NPM 数据库备份。
7. `media/workflow/media-arrival-state/` 是到达检查与翻译的运行状态（journal、outbox、metadata-backups），不属代码；可从备份恢复或重新生成。

首次恢复目录时按各容器要求单独设置权限：应用主要使用 NAS 的 `1026:100`，qBittorrent 当前为 `0:0`，Sublarr 入口为 root，手机通知路由需要 `NET_RAW`；不要整体递归 chown。Immich 数据库保留现网非 root entrypoint、PostgreSQL 配置与 tmpfs 参数。

## Docker 网络

以下网络按 NAS 实测导出，创建前确认新主机无相同网段冲突：

```sh
docker network create --driver bridge --subnet 172.19.0.0/16 --gateway 172.19.0.1 homelab_application_default
docker network create --driver bridge homelab_maintenance_default
docker network create --driver bridge homelab_network
docker network create --driver bridge --internal --subnet 172.30.61.0/24 qb_control
# bond0 是当前 NAS 父接口，迁移时替换成新主机真实接口。
docker network create --driver macvlan --subnet 192.168.10.0/24 --ip-range 192.168.10.6/32 --gateway 192.168.10.1 -o parent=bond0 qb_direct_lan
```

只创建缺失网络，不要删除或重建运行中的网络。qBittorrent 在 `qb_direct_lan` 固定 `192.168.10.6`，在 `qb_control` 固定 `172.30.61.2`，DNS 为 `172.30.61.1`。宿主机不能直接访问自身 macvlan 容器，下载器页面经 Mac mini 的 NPM 访问。

## 定时任务

到达检查与简介翻译由 root 的 cron 驱动（NAS）：

```
*/2 * * * * root /usr/bin/python3 -B /volume1/docker/homelab/media/workflow/media-arrival-tools/media_arrival_monitor.py >> /volume1/docker/homelab/media/workflow/media-arrival-state/monitor.log 2>&1 # fms-media-arrival-monitor
```

脚本只读 Emby 元数据、只回写简介，不修改媒体文件。每日翻译上限由根 `.env` 的 `EMBY_TRANSLATION_DAILY_LIMIT` 控制（默认 100，0 为暂停）；`status.yaml` 中的同名环境变量仅作为 journal 缺值时的兜底。

## 检查和启动

在对应 Docker 主机上先检查再启动：

```sh
bash scripts/current.sh check nas
bash scripts/current.sh apply nas
# Mac mini：
bash scripts/current.sh check macmini
bash scripts/current.sh apply macmini
```

`check` 只校验 Compose、`.env` 占位符与绑定挂载路径，不会启动容器；`apply` 会拉取镜像并启动。状态出口单独启动：

```sh
docker compose -f media/workflow/media-arrival-status/status.yaml up -d
```

## 规则数据与证书

SmartDNS 的 `china-domains.txt`、Sing-box 的 `geoip-cn.srs` / `geosite-cn.srs` 与 CA 证书来自第三方规则/系统源，恢复时以模板为准，不在本仓库持续同步。
