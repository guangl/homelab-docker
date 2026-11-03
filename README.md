# 家庭实验室配置

NAS 与 Mac mini 的 Docker Compose 配置、运行时模板和脚本。2026-11-03 对照两台主机的实际运行容器整理；目录按功能划分，每个目录只有一个同名 Compose 入口。

## 目录

| 目录 | 内容 |
| --- | --- |
| `media/` | Emby、Ani-RSS、qBittorrent、Sublarr（media.yaml）；`workflow/` 为下载后处理、到达检查脚本与状态出口 |
| `photos/` | Immich Server、数据库、Redis（photos.yaml） |
| `network/` | AdGuard Home、SmartDNS、Sing-box 网关、公网隧道（network.yaml）；`templates/` 为运行目录模板 |
| `dashboard/` | Glance（dashboard.yaml 与 glance/config 页面、组件） |
| `monitoring/` | Glances、Uptime Kuma（monitoring.yaml） |
| `notification/` | Apprise、手机通知路由（notification.yaml）；`templates/` 为路由与覆盖配置模板 |
| `automation/` | Watchtower（automation.yaml） |
| `macmini/` | Nginx Proxy Manager、Immich 机器学习与 NPM 转发表导出 |
| `scripts/` | 拓扑检查/恢复脚本，以及独立的 Linux 单机安装脚本 |
| `docs/restore.md` | 恢复步骤与私有文件清单 |

功能目录与启动入口的对应关系见 [FUNCTIONAL-LAYOUT.md](FUNCTIONAL-LAYOUT.md)。真实 `.env`、密钥和运行数据不入库。

## 主机

| 主机 | 地址 | 职责 |
| --- | --- | --- |
| NAS | 192.168.10.5 | Emby、Sublarr、Ani-RSS、qBittorrent、Immich 三容器、Glance、Glances、Uptime Kuma、Watchtower、Apprise、手机通知路由、AdGuard Home、SmartDNS、Sing-box、公网 SSH 隧道 |
| Mac mini | 192.168.10.4 | Nginx Proxy Manager、Immich 机器学习 |
| qBittorrent 独立地址 | 192.168.10.6:8080 | 下载 Web UI，域名经 Mac mini NPM 转发 |

NAS 运行根目录为 `/volume1/docker/homelab`，媒体根目录为 `/volume1/homes/guangluo/entertainments`，容器内挂载为 `/media`（Emby 只读）。

## 检查与启动

```sh
bash scripts/current.sh check nas
bash scripts/current.sh apply nas
# Mac mini 上执行：
bash scripts/current.sh check macmini
bash scripts/current.sh apply macmini
```

到达检查管线的状态出口独立于 media.yaml，需单独启动：

```sh
cd /volume1/docker/homelab
docker compose -f media/workflow/media-arrival-status/status.yaml up -d
```

## 元数据与翻译

- Ani-RSS 只负责下载与重命名，刮削（`scrape`）关闭：不再生成 NFO 与海报。
- Emby「动画」库由元数据抓取器补齐：Series / Season 用 TheMovieDb（zh-CN）+ Bangumi，Episode 用 Bangumi + TheMovieDb；Bangumi 插件 `TranslationPreference=Chinese`。没有本地 NFO 的新番依靠这条链路拿到中文番剧名、简介与季名。
- `media/workflow/media-arrival-tools/media_arrival_monitor.py` 由 cron 每 2 分钟运行，做两件事：把 Emby 中非中文的简介交给 Sublarr 容器内的 DeepSeek 后端翻译并回写；把 TMDB 只有「第 N 集」占位符或回退成文件名的分集标题，按 TMDB 中文原名（或日文原名机器翻译）回写为中文。每日上限为根 `.env` 的 `EMBY_TRANSLATION_DAILY_LIMIT`（默认 100，简介与分集标题共用），每轮最多 2 条简介 + 3 条标题，进度写入 `media/workflow/media-arrival-state/journal.json`，由状态容器暴露给 Glance 首页「元数据翻译」卡片。

## Glance

入口 [glance.yml](dashboard/glance/config/glance.yml)；页面、组件与凭据约定见 [Glance 文档](dashboard/glance/config/README.md)。只改页面时同步 `dashboard/glance/config/` 即可热重载；改环境变量需重建 Glance。凭据来自根 `.env` 与 `dashboard/.env.glance`。

## 网络

NAS 的 53 端口由 AdGuard Home 监听，SmartDNS / Sing-box 依赖 Mac mini 上 Surge 的 SOCKS `192.168.10.4:6153`。P2P、BT 与种子下载优先直连，规则与验证说明见 [P2P 直连文档](network/routing/README.md)。外部系统（Surge 订阅、UDM、云端 SSH 服务）不属于本仓库。

## 密钥与数据

真实 `.env`、API key、密码、WireGuard 与隧道私钥、通知收件地址、数据库、照片与媒体数据不进入版本库；含凭据的配置以 `.example` 提供结构。完整恢复需要自己的私有备份，清单见 [恢复说明](docs/restore.md)。公开历史中曾暴露的凭据仍应撤销或轮换。

## 许可

自有配置见 [LICENSE](LICENSE)。第三方规则数据与 CA 证书来源见恢复说明。
