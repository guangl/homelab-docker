# P2P 与种子下载直连

2026-11-03：P2P / BT / 种子下载使用 DIRECT，优先于境内外通用分流；Glance 不设置应用级 HTTP_PROXY / HTTPS_PROXY / NO_PROXY。

## NAS

- qBittorrent 的应用代理类型为 `None`，peer / BT / RSS / miscellaneous 代理均关闭；Ani-RSS 的应用代理为关闭。
- qB 使用独立地址 `192.168.10.6`，另有内部地址 `172.30.61.2`。网关首部增加这两个来源地址直连，避免仅依赖协议识别。
- `network/sing-box/p2p-direct-rules.json` 是插入现有 Sing-box `route.rules` 最前面的规则数组，**不是完整配置**。它包含当前种子的 Tracker 主机、常见种子源，以及 tracker/torrent 域名关键词直连。
- 保留网关原有 sniff → bittorrent 直连和 UDP 直连规则。修改前备份完整运行配置，执行 `sing-box check -c /etc/sing-box/config.json` 后重启 `network-gateway`。
- 实际配置在 NAS `/volume1/docker/homelab/network/sing-box/config.json`，含 WireGuard 私钥等运行字段，不入库。

## Mac mini

- `network/surge/p2p-direct.list` 是 Surge 规则片段，插入当前 `HomeSplit-Unified.conf` 的 `[Rule]` 最前面。
- 规则覆盖 qB 来源地址、常见 BT / 下载进程、当前 Tracker 主机与常见种子源。规则已通过 Surge 校验并重载；实际 profile 含节点凭据，不入库。
- 当前 Profile 位于 `~/Library/Application Support/Surge/Profiles/HomeSplit-Unified.conf`。备份位于 `~/Projects/homelab_npm/backups/p2p-direct-20261103/`，权限 600。

## 验证与边界

核对了 qB API 的代理开关、Ani-RSS 的代理开关、Sing-box 规则校验和 Surge 实际加载规则的先后顺序。当前 Tracker 清单从 qB 已有任务读取，只保存主机名，不保存 hash、完整 announce URL 或私有 passkey。

固定进程与来源地址规则使对应下载客户端的加密连接也走直连。其他设备上无法识别来源或协议、且使用未知域名的 HTTPS 流量无法仅凭“下载种子”这个用途自动识别；新增独立下载客户端/地址时应补充进程或来源地址规则。直连失败时保持失败，不回退代理。

来源：[Sing-box 路由规则](https://sing-box.sagernet.org/configuration/route/rule/)、[Surge 规则系统](https://manual.nssurge.com/rules/overview.html)。
