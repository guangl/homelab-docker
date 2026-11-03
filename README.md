# homelab-docker

家庭实验室配置仓库。2026-11-03 已对照 NAS 与 Mac mini 的实际容器、Nginx Proxy Manager 转发配置更新 Glance。

## 当前部署

| 主机 | 地址 | 职责 |
| --- | --- | --- |
| NAS | 192.168.10.5 | DSM、影音、相册、DNS、网络网关、通知与监控 |
| Mac mini | 192.168.10.4 | Surge、Nginx Proxy Manager、Immich 机器学习 |
| qBittorrent 独立网络地址 | 192.168.10.6:8080 | 下载 Web UI，域名由 Mac mini NPM 转发 |

NAS 当前运行 17 个容器：`media-emby`、`ani-rss`、`qbittorrent`、`immich-server`、`immich-database`、`immich-redis`、`media-sublarr`、`glance`、`glances`、`uptime-kuma`、`watchtower`、`adguardhome`、`smartdns`、`network-gateway`、`public-sites-tunnel`、`apprise`、`phone-notification-router`。

Mac mini 当前运行 `nginx-proxy-manager` 与 `immich-machine-learning`，机器学习服务监听 3003，NPM 管理监听 7001、反代监听 80/443。Glance 通过 NAS 本机 socket 展示 NAS 容器，通过 HTTP 检查展示 Mac mini 服务。

## 服务入口

| 服务 | 入口 | 后端 |
| --- | --- | --- |
| Glance | https://home.guangluo.top | NAS:6001 |
| Emby | https://movie.guangluo.top | NAS:6100 |
| Ani-RSS | https://anime.guangluo.top | NAS:6101 |
| qBittorrent | https://download.guangluo.top | 192.168.10.6:8080 |
| Immich | https://photo.guangluo.top | NAS:6104 |
| Glances | https://top.guangluo.top | NAS:6002 |
| Uptime Kuma | https://monitor.guangluo.top | NAS:6003 |
| AdGuard Home | https://adguard.guangluo.top | NAS:6200 |
| DSM | https://nas.guangluo.top | NAS:5001（HTTPS） |
| NPM | https://nginx.guangluo.top | Mac mini:7001 |

上述反代由 Mac mini NPM 管理。NPM 仍有旧 `draw`、`read` 条目，但 NAS 已无对应运行容器；Glance 不再展示这些入口。当前 DNS 容器为 AdGuard Home 与 SmartDNS，网关容器为 Sing-box，公网隧道由 AutoSSH 运行；旧 dnsq/tproxy/wg-home 配置不代表当前链路。

## Glance 配置与部署

入口：[`maintenance/glance/config/glance.yml`](maintenance/glance/config/glance.yml)。页面、组件、凭据约定和更新步骤见 [Glance 文档](maintenance/glance/config/README.md)。

只同步 `maintenance/glance/config/` 可热重载现有 Glance。修改环境变量时才重新创建 Glance；根 `.env` 和 `maintenance/.env.glance` 均不提交。保留现有 Emby key 的兼容变量名 `JELLYFIN_API_KEY`，不代表后端仍为 Jellyfin。

## 分流约定

Glance 不设置显式代理，境内外请求由现有 SmartDNS / ip2region 分流链路判断。P2P、BT 和种子下载优先直连，规则与验证说明见 [P2P 直连文档](network/routing/README.md)。

## 仓库与运行环境的边界

仓库的 `application/`、`infrastructure/`、`network/`、`tools/` 以及维护层其他服务段包含历史编排，尚未完整同步当前 NAS 的独立 Compose 项目。**不要按旧文档整组启动这些文件**：可能复活旧服务、冲突现有容器或端口。此次更新范围为 Glance 及其文档，不迁移其他运行服务。

NAS 运行根目录为 `/volume1/docker/homelab`。部署前先备份现有配置，按目标服务的实际 Compose 文件操作。运行时数据库、照片、媒体库、日志和密钥不属于 Git 备份；不要覆盖或清理这些目录。

## 密钥与历史

真实 `.env`、API key、WireGuard 配置、隧道私钥和运行数据不进入版本库；模板仅保留占位符。公开历史曾经过清理，后续提交以当前 GitHub main 为基础，不把旧本地历史合并回来。历史中曾暴露的凭据仍应撤销或轮换。

## License

见 [LICENSE](LICENSE)。
