# homelab-docker

当前家庭实验室的部署配置。**2026-11-03 已通过 NAS 与 Mac mini 实机只读核对全部 19 个运行容器**，使用实际 Compose、容器参数、镜像摘要和挂载配置整理。不是旧分层编排的整组启动入口。

## 当前配置在哪

| 目录 | 内容 |
| --- | --- |
| [`deploy/nas/`](deploy/nas/) | NAS 的 17 个容器，8 个实际部署单元 |
| [`deploy/macmini/`](deploy/macmini/) | NPM、Immich 机器学习及 NPM 转发表 |
| [`deploy/inventory.json`](deploy/inventory.json) | 核验时的服务、端口、网络、原 Compose 路径 |
| [`templates/runtime/`](templates/runtime/) | 当前 DNS、网关规则、通知路由、数据库配置及脱敏模板 |
| [`maintenance/glance/config/`](maintenance/glance/config/) | 当前 Glance 页面与组件 |
| [`network/routing/`](network/routing/) | P2P 直连约定与验证说明 |
| [`scripts/`](scripts/) | 当前拓扑检查/恢复脚本和独立的 Linux 核心服务安装脚本 |

原 `tools/`、`infrastructure/`、旧 Jellyfin / TrendRadar / WireGuard 等停用编排已从当前目录移除，需要时查 Git 历史。原应用层文件混有已过期的 Emby、字幕、下载器配置，本次只保留实际正在使用的部署定义。

## 当前部署

| 主机 | 地址 | 运行服务 |
| --- | --- | --- |
| NAS | 192.168.10.5 | Emby、Sublarr、Ani-RSS、qBittorrent、Immich 三容器、Glance、Glances、Kuma、Watchtower、Apprise、手机通知路由、AdGuard Home、SmartDNS、Sing-box、公网 SSH 隧道 |
| Mac mini | 192.168.10.4 | Nginx Proxy Manager、Immich 机器学习 |
| qBittorrent 独立网络地址 | 192.168.10.6:8080 | 下载 Web UI；额外使用内部 `qb_control` 网络 |

NAS 运行根目录为 `/volume1/docker/homelab`，媒体根目录为 `/volume1/homes/guangluo/entertainments`。公开 Compose 通过根 `.env` 中的 `HOMELAB_ROOT`、`MEDIA_ROOT` 参数指定这些路径，避免将编排所在目录误当数据目录。镜像固定为核验时容器实际使用的可拉取 registry digest，避免导出只有原 NAS 才能找到的本地 `sha256:` 镜像 ID。

## 安装与恢复

**按现有双主机拓扑完整恢复：**见 [恢复说明](docs/restore.md)。先恢复数据、网络与私有参数，再运行：

```sh
bash scripts/current.sh check nas
bash scripts/current.sh apply nas
# 在 Mac mini 上执行：
bash scripts/current.sh check macmini
bash scripts/current.sh apply macmini
```

这些命令会使用当前部署定义。当前 NAS/Mac mini 的容器和文件没有在此次上传中被修改；不要在原运行环境直接换用新路径重新启动全部项目。

**在新 Ubuntu / Debian 上安装可移植核心服务：**见 [脚本说明](scripts/README.md)。`install-linux-core.sh` 是单机 12 容器的简化部署，不是当前 19 容器拓扑的完整重建，也不迁移现有数据或家庭网络链路。

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

NPM 转发表还保留 `draw` 和 `read` 两条旧入口，后端对应服务已停用，已在导出 JSON 中标记 `backend_running: false`；不据此安装旧应用。NPM 的原始数据库、账号与证书不公开，转发表保留规则参数用于恢复参考。

## 密钥、数据与外部依赖

仓库包含完整的当前容器部署定义和可公开配置；真实 `.env`、API key、密码、WireGuard 私钥、SSH 隧道私钥、通知收件地址、数据库、照片与媒体数据不上传。含凭据的配置用 `.example` 提供结构，完整恢复仍需要自己的私有备份，具体清单见 [恢复说明](docs/restore.md)。

Glance 沿用 `JELLYFIN_API_KEY` 变量名兼容 Emby，不代表使用 Jellyfin。SmartDNS / Sing-box 依赖 Mac mini 的 Surge SOCKS `192.168.10.4:6153`；Surge 订阅凭据、UDM/WireGuard 对端配置和云端 SSH 服务属于外部系统，不是本仓库容器。公网隧道仍转发一个已停用后端的端口，导出保留原配置并在恢复说明中注明。

运行数据和查询日志不属于 Git 备份。历史中曾暴露的凭据仍需撤销或轮换。

## License

自有配置见 [LICENSE](LICENSE)。第三方域名/规则数据与 CA 证书的来源见 [恢复说明](docs/restore.md#规则数据与证书)。
