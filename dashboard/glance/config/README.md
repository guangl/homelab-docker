# Glance 当前配置

2026-11-06 从 NAS `dashboard/glance/config` 只读同步，仅保留 `glance.yml` 递归引用的页面与组件。新增媒体流程状态组件；DNS 组件指向 Mac mini。部署时复制本目录到 `HOMELAB_ROOT/dashboard/glance/config`。

API key 和 AdGuard 凭据由根 `.env` 注入，Emby 使用 `EMBY_API_KEY`。服务后台记录、宿主媒体工作流和通知目标需要私有备份。

「智能家居」页沿用首页的左窄、中宽、右窄布局，依次展示室内环境、设备控制和用电与供电。两侧卡片每分钟通过 HTTPS 读取 Home Assistant 数据并显示同步时间，电网日用电同时标明统计日期。用 HA 中仅限本地且属于 `Read Only` 组的账号创建长期访问令牌，在根 `.env` 中设置 `HOME_ASSISTANT_TOKEN` 并重新创建 Glance 容器。未配置令牌时卡片仍提供快捷入口。

设备控制使用浏览器中的 HA OAuth 授权与 WebSocket，权限由登录的 HA 账号决定。连接凭据保存在当前浏览器配置的站点存储中，刷新、新开标签页或重开浏览器后会自动恢复连接。点「解除连接」会清除浏览器凭据、同步断开其他 Glance 标签页并请求 HA 撤销授权。设备名单在 `assets/home-assistant/controls.js`，包含卧室与书房空调及灯具。概览使用的只读令牌与设备控制独立。

`assets/home-assistant/haws-9.9.0.umd.js` 来自 Home Assistant 项目发布的 `home-assistant-js-websocket@9.9.0` npm 包中的 `dist/haws.umd.js`，附 Apache 2.0 许可证。部署时需一起复制整个 `assets/` 目录。
