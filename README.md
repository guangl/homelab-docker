# homelab-docker

家庭实验室当前容器配置，核验日期 **2026-11-06（Asia/Shanghai）**。通过 NAS 与 Mac mini 的 Docker 实机只读核对，当前有 **18 个自管容器：NAS 14 个、Mac mini 4 个**。NAS 另有 2 个群晖 Document Viewer 容器，由 DSM 套件管理，不纳入手工恢复编排。

| 位置 | 内容 |
| --- | --- |
| `media/`、`photos/`、`dashboard/`、`monitoring/`、`notification/`、`automation/` | 媒体、照片、看板、监控、通知、自动更新、媒体到达状态，共 7 组 |
| [`macmini/`](macmini/) | AdGuard Home / SmartDNS、NPM、Immich 机器学习，共 3 组 |
| [`docs/inventory.json`](docs/inventory.json) | 实机镜像摘要、项目名、原 Compose 路径、端口和网络 |
| 各功能的 `templates/` 及 `media/workflow/` | 公开支持文件、Sublarr 补丁及脱敏配置模板 |
| [`dashboard/glance/config/`](dashboard/glance/config/) | 当前 Glance 配置及实际引用的组件 |
| [`scripts/`](scripts/) | 当前双主机检查与恢复入口 |

NAS `192.168.10.5` 的运行根目录为 `/volume1/docker/homelab`，按 `media`、`photos`、`dashboard`、`monitoring`、`notification`、`automation` 分类；媒体根目录为 `/volume1/homes/guangluo/entertainments`。Mac mini `192.168.10.4` 使用 OrbStack，DNS 目录为 `/Users/guang/dsh-data/homelab-migrate/network`。根 `.env.example` 可调整恢复路径。

| 服务 | 入口 | 当前后端 |
| --- | --- | --- |
| Glance | https://home.guangluo.top | NAS:6001 |
| Emby | https://movie.guangluo.top | NAS:6100 |
| Ani-RSS | https://anime.guangluo.top | NAS:6101 |
| qBittorrent | https://download.guangluo.top | 192.168.10.6:8080 |
| Immich | https://photo.guangluo.top | NAS:6104 |
| Glances | https://top.guangluo.top | NAS:6002 |
| Uptime Kuma | https://monitor.guangluo.top | NAS:6003 |
| AdGuard Home | https://adguard.guangluo.top | Mac mini:6200 |
| DSM | https://nas.guangluo.top | NAS:5001（HTTPS） |
| NPM | https://nginx.guangluo.top | Mac mini:7001 |

镜像固定为 registry digest。运行 `bash scripts/current.sh plan nas` 可列出 NAS 的编排文件，Mac mini 使用 `plan macmini`。在目标主机准备数据、私有配置和网络后，使用 `check` 预检，使用 `apply` 恢复。参数和配置字段见 [恢复说明](docs/restore.md)。

配置整理未更改或重启现网容器。移除已停用的 NAS DNS / Sing-box 网关 / 公网 SSH 隧道编排、旧网关规则片段、失效 draw/read 反代导出和旧单机安装器。Glance 只保留当前入口递归引用的组件。历史配置可从 Git 查找。

真实 `.env`、密码、API key、通知目标、数据库、照片和媒体不入库。Git 配置不能代替数据备份。DNS 仍依赖 Mac mini 的 Surge SOCKS `192.168.10.4:6153`，Surge、UDM 与 DSM 属于外部系统。媒体到达状态容器仅显示宿主工作流生成的记录；状态容器本身不运行媒体处理任务。

自有配置见 [LICENSE](LICENSE)，第三方规则、证书和补丁来源见 [恢复说明](docs/restore.md)。
