# 当前功能目录

基础编排核验于 2026-11-06，HA、C700 go2rtc 和 Collect Metadata 编排核验于 2026-11-22。

| 主机 | 配置入口 |
| --- | --- |
| NAS | `photos/photos.yaml`、`media/media.yaml`、`dashboard/dashboard.yaml`、`monitoring/monitoring.yaml`、`notification/notification.yaml`、`automation/automation.yaml` |
| NAS 家庭自动化 | `homeassistant/compose.yaml` |
| NAS 元数据 | `collect-metadata/compose.yaml`、`media/emby/private-metadata/compose.yaml` |
| NAS 媒体状态 | `media/workflow/media-arrival-status/status.yaml` |
| Mac mini | `macmini/network.yaml`、`macmini/npm.yaml`、`macmini/immich-ml.yaml`、`macmini/collect-metadata.yaml` |

DNS 已迁往 Mac mini；NAS 的 Sing-box 与公网隧道已停用。不要恢复旧 NAS network.yaml。

`media/workflow/` 是在用的媒体脚本、Sublarr 补丁及状态出口；main 中已有的分集标题翻译及 Emby 抓取逻辑保留。私有数据和宿主 cron 需另行恢复。

实机清单见 `docs/inventory.json`。密钥来自各服务的私有环境文件或私有配置。模板与运行目录的对应关系见 `docs/restore.md`。

多个功能文件保留共享 Compose 项目名和外部网络，禁止使用 `--remove-orphans`。
