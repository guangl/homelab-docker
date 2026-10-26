# Glance 中文家庭主页

`glance.yml` 是入口配置；三个页面分别在 `home_page.yml`、`homelab_page.yml`、`development_page.yml`，具体组件在 `widget/` 目录。页面通过 `$include` 引用组件，资讯分组也引用独立的 RSS、Hacker News、Lobsters 组件。

调整布局请修改页面文件；调整组件内容请修改对应的 `widget/*.yml`。include 路径相对于引用它的文件：页面使用 `widget/xxx.yml`，`widget/news_group.yml` 使用同目录的组件文件名。

## 部署

1. 将整个 `maintenance/glance/config/` 目录同步到 NAS 的 `/volume1/docker/homelab/maintenance/glance/config/`，保留页面与 `widget/` 目录结构。
2. 从 `maintenance/.env.glance.example` 复制为 `maintenance/.env.glance`，填写 API 地址和密钥；该文件不进入 Git。`WAQI_TOKEN`、`ADGUARD_USERNAME`、`ADGUARD_PASSWORD` 使用仓库根 `.env` 中的值，不要在 `.env.glance` 重复配置。
3. 同步 `maintenance/maintenance.yaml` 和环境变量文件，在仓库根目录执行 `docker compose --env-file .env -f maintenance/maintenance.yaml up -d glance`，重新创建 Glance 以加载环境变量。
4. 访问 `http://NAS地址:6001`。后续修改 YAML 支持自动重新加载；环境变量修改需要重新创建容器。

维护层固定使用 `container_name: glance`，与容器组件中的名称一致。此处更新现有维护层服务；不再使用旧的独立 Compose 部署。若之前部署过独立实例，先停止该实例并移除它的 Glance 容器，再启动维护层服务，避免名称和 6001 端口冲突。

## 组件说明

- 搜索沿用 Kagi，可改成 `bing`；支持 `gh 关键词`、`doc 关键词`、`bili 关键词`、`wiki 关键词`。按 S 聚焦。
- 待办存储在当前浏览器，不自动跨设备同步。
- 容器列表包含停止状态；共享的 PostgreSQL / Redis 单独展示。
- 主机 CPU、内存和磁盘通过现有 Glances 入口查看，避免将容器资源当成 NAS 资源。
- monitor 从 Glance 容器检查 URL；Jellyfin 与 Immich 使用健康接口。反向代理登录、跳转等情况需要按实际情况配置 `check-url` 和 `alt-status-codes`。
- Immich 密钥需具备服务器统计权限；Jellyfin 密钥通过请求头传递。
- UniFi 保留现有 `/proxy/network/api/stat/sites` 接口。API Key 认证是否可用取决于控制器版本；没有返回站点数据时会提示检查接口和权限。
- 空气质量使用 WAQI AQI，不将污染物指数误标成浓度。
- 不使用某个 API 时可移除对应卡片；未填写密钥时该卡片可能显示错误。所有被引用的环境变量必须存在。
- GitHub 组件使用较长缓存。遇到匿名 API 速率限制时，可为 repository / releases 添加 `token: ${GITHUB_TOKEN}`，并在 `.env.glance` 添加该变量。

配置与模板已在本地校验；真实接口权限、NAS 服务连通性需在部署后验证。

官方文档：https://github.com/glanceapp/glance/blob/main/docs/configuration.md
