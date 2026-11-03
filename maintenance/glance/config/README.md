# Glance 家庭主页

2026-11-03 对照 NAS（192.168.10.5）的 Docker 清单、Mac mini（192.168.10.4）的 Docker 清单和 NPM 转发配置更新。

`glance.yml` 引用首页、家庭服务、开发与摄影页面，并保留 NAS 现有的自动明暗主题，组件在 `widget/`。页面引用 `widget/xxx.yml`，组件之间引用同目录文件名。

## 当前服务

- NAS 容器状态通过本机 Docker socket 读取，显式展示 17 个现有容器，含停止状态。Emby 容器名是 `media-emby`；Immich 使用 `immich-database` 和 `immich-redis`。
- Mac mini 承担 Nginx Proxy Manager 和 Immich 机器学习，通过 HTTP 可用性检查展示，不把 NAS 的 Docker socket 当成 Mac mini 的容器清单。
- 首页服务提醒仅展示失败项；家庭服务页列出全部检查。检查优先使用内网地址（qB 例外），点击入口使用 HTTPS 域名。检查通过代表后端可达，不代表公网证书、DNS 和反代链路全部正常。
- Emby 使用 `/emby/System/Info/Public`，Immich 使用 `/api/server/ping`；机器学习使用 Mac mini 的 `:3003/ping`。qB 后端为 `192.168.10.6:8080`；NAS bridge 容器无法直连其独立网络，因此检查与入口均通过 `https://download.guangluo.top` 的 Mac mini 反代。
- 不再展示 Jellyfin、Excalidraw、TrendRadar、DrawDB、DDNS、PeaNUT、旧 DNS/隧道服务。NPM 中残留的反代条目不代表对应应用仍在运行。
- NAS CPU、内存和磁盘通过 Glances 查看，避免把 Glance 容器自身的资源误标为 NAS 资源。

Glance 不设置 HTTP_PROXY、HTTPS_PROXY 或 NO_PROXY；境内外请求由现有 SmartDNS / ip2region 分流链路判断。

## 环境变量

根 `.env` 提供 `WAQI_TOKEN`、`ADGUARD_USERNAME`、`ADGUARD_PASSWORD`。`maintenance/.env.glance` 提供 `IMMICH_API_KEY`、`JELLYFIN_API_KEY`、`UNIFI_API_KEY`，模板见 `maintenance/.env.glance.example`。

影音卡片现为 Emby；为兼容现有容器保留 `JELLYFIN_API_KEY` 变量名，但其值必须是 Emby 的 API key。Immich key 需要服务器统计权限。密钥只通过请求头传递，不写进 URL 或 Git。API 地址直接使用已核对的内网地址，不再要求旧 `JELLYFIN_URL`、`IMMICH_URL`、`UNIFI_URL`、`ADGUARD_URL` 变量。

UniFi 使用 UDM 本地 API key 与 HTTPS；因其证书为自签名，仅该组件设置 `allow-insecure: true`。

核验时 Emby、Immich 统计与 UniFi 接口均返回 200。密钥仅更新 NAS 的 `.env.glance`，未写入仓库。服务可用性检查独立于统计密钥。

## 更新现有 Glance

1. 先备份 NAS 的 `/volume1/docker/homelab/maintenance/glance/config/`。
2. 将此目录完整同步到 NAS 相同位置，保留 `widget/` 层级。只修改 YAML 时支持热重载；不要覆盖真实 `.env.glance`。
3. 使用实际容器校验：`docker exec glance /app/glance -config /app/config/glance.yml config:validate`。
4. 访问 `http://192.168.10.5:6001/home` 和 `/homelab`，检查日志及卡片。改环境变量后才需要重新创建容器；已有 NAS 编排优先，不要整组启动仓库历史服务。

根维护编排中的 Glance 服务可单独使用：`docker compose --env-file .env -f maintenance/maintenance.yaml up -d --no-deps glance`。执行前需准备 `.env.glance` 及根 `.env`；该命令不用于重建其他现有服务。

资讯与 GitHub 组件有缓存，匿名 GitHub API 可能受限；真实 API 权限应在 NAS 上检查。运行配置、数据、密钥不进 Git。

## 桌面外观（2026-11-03）

首页以桌面为主：顶部横向服务入口，下方三栏分别承载时间与环境、日常书签与资讯、日历与资料库统计，服务提醒位于中栏。书签使用逐行分类的横向链接，不再使用原生多列书签布局。中文使用系统字体，浅色为暖白与墨绿、深色为石墨与浅绿，保留系统明暗切换。宽屏显示六个服务入口，较窄窗口自动减列。

样式集中在 `glance.yml` 的 `document.head`；`widget/intro.yml` 和 `widget/shortcuts.yml` 为静态 HTML，不额外加载第三方字体或图标脚本。UniFi 卡片的模板请求需要在 `newRequest` 管道中设置 `withAllowInsecure true`；顶层 `allow-insecure` 不会自动传递给模板内的独立请求。设备状态、在线说明和有线/无线数量均来自控制器返回数据。

首页已移除 Claude 与待办组件；开发资讯不再追踪停止维护的 dameng-cli、sqllog2db，改为技术社区内容与开发工具更新的双栏布局。

资讯分工：首页只展示少数派，Hacker News 与 Lobsters 仅在开发资讯页展示，避免跨页面重复。
