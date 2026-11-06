# Glance 当前配置

2026-11-06 从 NAS `dashboard/glance/config` 只读同步，仅保留 `glance.yml` 递归引用的页面与组件。新增媒体流程状态组件；DNS 组件指向 Mac mini。部署时复制本目录到 `HOMELAB_ROOT/dashboard/glance/config`。

API key 和 AdGuard 凭据由根 `.env` 注入，Emby 使用 `EMBY_API_KEY`。服务后台记录、宿主媒体工作流和通知目标需要私有备份。
