# 当前拓扑恢复说明

核验日期：2026-11-06，Asia/Shanghai。两台主机均为只读访问，本次只修改本地仓库。

| 主机 / 文件 | 容器 | 项目名 |
| --- | --- | --- |
| nas/photos.yaml | immich-server、immich-database、immich-redis | homelab_application |
| nas/media.yaml | ani-rss、qbittorrent、media-sublarr、media-emby | homelab_application |
| nas/dashboard.yaml | glance | homelab_maintenance |
| nas/monitoring.yaml | glances、uptime-kuma | homelab_maintenance |
| nas/notification.yaml | apprise、phone-notification-router | homelab_maintenance |
| nas/automation.yaml | watchtower | homelab_maintenance |
| nas/media-status.yaml | media-arrival-status | homelab_media_status |
| macmini/network.yaml | adguardhome、smartdns | homelab_network |
| macmini/npm.yaml | nginx-proxy-manager | npm |
| macmini/immich-ml.yaml | immich-machine-learning | immich-ml |

文件均在 `deploy/`。同主机有多个文件共用项目名，禁止 `--remove-orphans`；NAS 与 Mac mini 不能合并到同一 Docker 主机。原实机 Compose 路径、服务名及网络见 `deploy/inventory.json`。NAS 的两个 Document Viewer 容器由 DSM 套件管理，恢复套件即可，不手工创建。

## 私有配置与数据

1. 复制根 `.env.example` 为 `.env`，权限设为 `600`，填写所有实际参数。原有 `.env` 不自动重写；更新时需补齐 `DNS_ROOT`、`APPRISE_USER`、`EMBY_API_KEY`、`IMMICH_API_KEY`、`UNIFI_API_KEY` 等当前字段。Glance 已统一使用根 `.env` 和 `EMBY_API_KEY`，不再使用旧 `maintenance/.env.glance`。
2. 恢复 NAS `HOMELAB_ROOT`（默认 `/volume1/docker/homelab`）及 `MEDIA_ROOT`。将 `templates/runtime/` 下除 `network/` 外的支持文件按相对路径放入 `HOMELAB_ROOT`，将 `maintenance/glance/config/` 放入 `HOMELAB_ROOT/dashboard/glance/config/`。保留已有配置，不能直接覆盖现网文件。
3. NAS 私有模板去掉 `.example` 后恢复真实参数：`media/ani-rss/config.v2.json`、`media/qbittorrent/config/qBittorrent.conf`、`notification/phone-routing/router.json`。通知目标、登录信息、API key、token 均需自己的备份；qB 登录密码 hash 不能填明文密码。
4. 从私有备份恢复 Emby、Sublarr、Ani-RSS、qBittorrent、Kuma、Apprise 的配置/数据库，以及 `photos/immich/data` 和 `photos/immich/postgres`。`DB_PASSWORD` 必须与现有数据库一致。不要对运行中的数据库目录作普通文件复制来代替一致性备份。
5. Sublarr 当前挂载 `media/workflow/sublarr-overrides/` 的四个 Python 补丁，已随支持文件保留，并固定当前镜像摘要。不要省略补丁挂载或未经验证替换镜像。数据库非 root entrypoint、PostgreSQL 配置及 tmpfs 也按现网保留。
6. Mac mini 恢复 `DNS_ROOT`（默认 `/Users/guang/dsh-data/homelab-migrate/network`）。把 `templates/runtime/network/` 的内容放到 `DNS_ROOT`，AdGuardHome.yaml.example、smartdns.conf.example 去掉后缀。填写 AdGuard bcrypt 密码 hash 和私有代理入口 bootstrap 域名；未使用的 bootstrap 行可删除，不能保留 `REPLACE_`。DNS 对外由 AdGuard 在 Mac mini 提供，SmartDNS 监听 `127.0.0.1:6053`。host 网络依赖当前 OrbStack 能力，迁移到其他运行时需重新核对。
7. Mac mini 恢复 `NPM_ROOT/data/nginx-proxy-manager/{data,letsencrypt}` 和 `ML_ROOT/model-cache`。`deploy/macmini/npm-proxy-hosts.json` 是当前启用路由的参考导出，已排除失效 draw/read，不是 NPM 数据库备份；没有数据库/证书备份时需重建规则和证书。
8. 媒体状态服务监听容器内部 `7099`，只读挂载 `media/workflow/media-arrival-state` 与 `media/workflow/media-arrival-status`。需恢复宿主工作流和状态记录；`server.py` 仅展示状态，不生成任务。宿主任务调度、密钥、状态历史不由此容器编排恢复。

权限按服务要求恢复。应用常用 NAS `1026:100`；qBittorrent 仍是 `0:0`，Sublarr 使用镜像默认 root，手机通知路由需要 `NET_RAW`。不要全局递归 chown。所有 bind mount 禁止自动创建路径，缺项时检查脚本会停止。

## Docker 网络

NAS 使用四个外部网络，先核对网段与父接口，仅创建缺失网络。不要删除或重建现网网络。网络参数应以目标主机实测为准：

```sh
docker network create --driver bridge --subnet 172.19.0.0/16 --gateway 172.19.0.1 homelab_application_default
docker network create --driver bridge --subnet 172.18.0.0/16 --gateway 172.18.0.1 homelab_maintenance_default
docker network create --driver bridge --internal --subnet 172.30.61.0/24 qb_control
docker network create --driver macvlan --subnet 192.168.10.0/24 --ip-range 192.168.10.6/32 --gateway 192.168.10.1 -o parent=bond0 qb_direct_lan
```

`bond0` 必须按目标网卡修改。qB 固定使用 `192.168.10.6` 和 `172.30.61.2`，DNS 已改为 `192.168.10.4`，不再依赖 NAS 上的 `172.30.61.1` DNS。宿主机默认不能访问自身 macvlan 容器，现有看板通过 Mac mini NPM 访问下载器。

## 检查与启动

```sh
# 在 NAS：
bash scripts/current.sh check nas
bash scripts/current.sh apply nas
# 在 Mac mini：
bash scripts/current.sh check macmini
bash scripts/current.sh apply macmini
```

要求 Docker Compose v2 与 Python 3。先检查全部编排、挂载路径和主要配置占位符，再拉取镜像并逐组启动，失败退出且保留数据。不含健康检查的服务只能验证运行状态，还需核对首次登录、DNS、反代、媒体、通知和工作流。NAS Compose 保留当前服务之间实际连接的网络，恢复时不要擅自补回已断开的网络。

## 外部依赖与清理范围

Sing-box 网关及公网隧道已不在两台主机容器清单中，相关部署、密钥参数、二进制规则和旧增量规则片段已从仓库移除。Surge 配置、网关分流、DSM 本体和宿主媒体工作流需另行备份。仓库清理不会删除 NAS/Mac mini 文件、容器、卷或网络。

## 规则数据与证书

SmartDNS 的 `china-domains.txt` 与 CA 证书是公开支持数据；域名快照来源与 SHA256 见同目录 `provenance.json`。第三方数据和证书适用上游许可。Sublarr 补丁由当前运行主机导出，依附第三方应用，需要随镜像版本一并验证。
