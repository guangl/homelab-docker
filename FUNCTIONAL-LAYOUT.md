# NAS 功能目录

每个功能目录只使用一个同名 Compose 入口：

| 目录 | 配置文件 | 服务 |
| --- | --- | --- |
| media | media.yaml | Emby、Ani-RSS、qBittorrent、Sublarr |
| photos | photos.yaml | Immich Server、数据库、Redis |
| network | network.yaml | AdGuard Home、SmartDNS、网关、公网隧道 |
| dashboard | dashboard.yaml | Glance |
| monitoring | monitoring.yaml | Glances、Uptime Kuma |
| notification | notification.yaml | Apprise、手机通知路由 |
| automation | automation.yaml | Watchtower |
| macmini | macmini/npm.yaml、macmini/immich-ml.yaml | Mac mini 上的 NPM、Immich 机器学习 |

```sh
cd /volume1/docker/homelab
docker compose --env-file .env -f media/media.yaml up -d
docker compose -f media/workflow/media-arrival-status/status.yaml up -d
```

密钥统一放在根 `.env`，YAML 只使用变量引用。文件权限为 600，不提交公开仓库。

`media/workflow/` 保留正在使用的下载目录、媒体处理工作目录、到达检查脚本和状态。`media/workflow/media-arrival-status/status.yaml` 是到达检查管线的只读状态出口（`server.py` 读 `media-arrival-state/` 暴露 `/status.json` 与 `/healthz`，供 Glance 首页「元数据翻译」卡片和「服务提醒」读取；接入 `homelab_maintenance_default`，不发布宿主端口）：数据库附加配置以 `photos/templates/immich/postgresql.conf` 提供，恢复时复制到 `photos/immich/postgresql.conf`。旧部署试验、封面处理历史和临时访问配置保存在本次 backups/functional-consolidation-* 归档中。

旧 Jellyfin、RSS 静态目录、TrendRadar 已删除。application/、maintenance/、family-media-system-runtime/ 不再作为运行入口。

为兼容现有服务，部分功能文件仍共享历史 Compose 项目名，现有共享网络均显式声明 external。不要使用 --remove-orphans，避免删除其他功能文件的容器。
