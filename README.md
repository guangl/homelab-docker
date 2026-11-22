# homelab-docker

家庭实验室容器配置分布在 NAS 和 Mac mini。基础清单核验于 **2026-11-06（Asia/Shanghai）**，Home Assistant、C700 go2rtc 和 Collect Metadata 的编排核验于 **2026-11-22**。群晖 Document Viewer 由 DSM 套件管理。

| 位置 | 内容 |
| --- | --- |
| `media/`、`photos/`、`dashboard/`、`monitoring/`、`notification/`、`automation/` | 媒体、照片、看板、监控、通知、自动更新 |
| [`homeassistant/`](homeassistant/) | Home Assistant、Xiaomi OAuth mDNS、历史数据库连接、C700 go2rtc |
| [`collect-metadata/`](collect-metadata/) | Collect Metadata Web、私有媒体刮削与媒体到达状态。共享翻译随 Sublarr 运行。 |
| [`macmini/`](macmini/) | AdGuard Home / SmartDNS、NPM、Immich 机器学习、Collect Metadata PostgreSQL |
| [`docs/inventory.json`](docs/inventory.json) | 合并前的实机盘点，包括镜像、项目、端口和网络 |
| 各功能的 `templates/` 及 `media/workflow/` | 公开支持文件、Sublarr 补丁及脱敏配置模板 |
| [`dashboard/glance/config/`](dashboard/glance/config/) | 当前 Glance 配置及实际引用的组件 |
| [`scripts/`](scripts/) | 当前双主机检查与恢复入口 |

NAS `192.168.10.5` 的运行根目录为 `/volume1/docker/homelab`。HA 配置在 `homeassistant/config`，摄像头配置在 `homeassistant/go2rtc`。媒体根目录为 `/volume1/homes/guangluo/entertainments`。Mac mini `192.168.10.4` 使用 OrbStack，DNS 和 Collect Metadata 数据库编排位于 `/Users/guang/dsh-data/homelab-migrate`。根 `.env.example` 可调整恢复路径。

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

镜像按 digest 或部署版本指定。运行 `bash scripts/current.sh plan nas` 可列出 NAS 的编排文件，Mac mini 使用 `plan macmini`。在目标主机准备数据、私有配置和网络后，使用 `check` 预检，使用 `apply` 恢复。参数和配置字段见 [恢复说明](docs/restore.md)。

NAS 顶层原有的 `homeassistant` 和 `go2rtc-c700` 配置目录已迁入 homelab。历史部署配置可从 Git 查找。

真实 `.env`、密码、API key、通知目标、数据库、照片和媒体不入库。Git 配置不能代替数据备份。DNS 仍依赖 Mac mini 的 Surge SOCKS `192.168.10.4:6153`，Surge、UDM 与 DSM 属于外部系统。媒体到达状态由 Collect Metadata 展示，媒体到达定时任务依然在宿主机运行。

自有配置见 [LICENSE](LICENSE)，第三方规则、证书和补丁来源见 [恢复说明](docs/restore.md)。
