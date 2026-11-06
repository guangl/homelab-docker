# 当前功能目录

2026-11-06 核验：NAS 14 个自管容器，Mac mini 4 个；另有两个 DSM 管理的 Document Viewer 容器。

| 主机 | 配置入口 |
| --- | --- |
| NAS | `photos/photos.yaml`、`media/media.yaml`、`dashboard/dashboard.yaml`、`monitoring/monitoring.yaml`、`notification/notification.yaml`、`automation/automation.yaml` |
| NAS 媒体状态 | `media/workflow/media-arrival-status/status.yaml` |
| Mac mini | `macmini/network.yaml`、`macmini/npm.yaml`、`macmini/immich-ml.yaml` |

DNS 已迁往 Mac mini；NAS 的 Sing-box 与公网隧道已停用。不要恢复旧 NAS network.yaml。

`media/workflow/` 是在用的媒体脚本、Sublarr 补丁及状态出口；main 中已有的分集标题翻译及 Emby 抓取逻辑保留。私有数据和宿主 cron 需另行恢复。

公开配置模板位于各功能的 `templates/`，实机清单见 `docs/inventory.json`。密钥由根 `.env` 提供。具体复制位置见 `docs/restore.md`。

多个功能文件保留共享 Compose 项目名和外部网络，禁止使用 `--remove-orphans`。
