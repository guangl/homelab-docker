# 当前网络与下载路径

2026-11-06 实机核验：AdGuard Home 与 SmartDNS 在 Mac mini `192.168.10.4` 的 OrbStack 上运行；NAS 已无 DNS、Sing-box 网关和公网隧道容器。

qBittorrent 使用 macvlan `192.168.10.6`、内部控制地址 `172.30.61.2`，DNS 指向 `192.168.10.4`。Ani-RSS 通过 `qb_control` 访问下载器。SmartDNS 的国内解析直连，境外 DoH 经过 Mac mini Surge SOCKS `192.168.10.4:6153`；代理入口 bootstrap 域名必须从自己的私有配置恢复。

原 Sing-box 与 Surge 的 P2P 增量片段已移除，避免误用于现在的拓扑。Surge 本体和网关分流不由 Docker 编排恢复；本次只核对容器配置，没有重新验证所有 BT 流量的实际出口。部署入口见 [恢复说明](../../docs/restore.md)。
