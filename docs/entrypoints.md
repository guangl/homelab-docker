# 2026-11-23 DSM / DNS 当前入口恢复快照

来源：[已合并的 blog#52](https://github.com/guangl/blog/pull/52)，其中记录了从 DSM Nginx 配置核对、在家庭主网验证的 **11 个 HTTPS 域名入口**。机房拓扑与原生服务的状态按当日记录，不是本仓库当前重新读取现机的结果。

对应的机器可读清单：[`entrypoints-2026-11-23.json`](./entrypoints-2026-11-23.json)。**该 JSON 是恢复核对用的静态参考，不是 DSM 可导入的配置文件，也不是证书、Nginx 配置或 AdGuard YAML 的备份**；缺少真实的域名证书、DSM 路由选项、WebSocket 和转发请求头等运行参数，不能直接部署。

## 域名和后端（来源 blog#52）

| HTTPS 域名 | DSM 反代后端 | DNS A 重写 |
| --- | --- | --- |
| `home.guangluo.top` | `http://192.168.10.5:6001` | `192.168.10.5` |
| `movie.guangluo.top` | `http://192.168.10.5:6100` | `192.168.10.5` |
| `anime.guangluo.top` | `http://192.168.10.5:6101` | `192.168.10.5` |
| `download.guangluo.top` | `http://172.30.61.2:8080` | `192.168.10.5` |
| `photo.guangluo.top` | `http://192.168.10.5:6104` | `192.168.10.5` |
| `top.guangluo.top` | `http://192.168.10.5:6002` | `192.168.10.5` |
| `monitor.guangluo.top` | `http://192.168.10.5:6003` | `192.168.10.5` |
| `adguard.guangluo.top` | `http://192.168.10.4:6200` | `192.168.10.5` |
| `nas.guangluo.top` | `https://192.168.10.5:5001` | `192.168.10.5` |
| `ha.guangluo.top` | `http://192.168.10.5:8123` | `192.168.10.5` |
| `metadata.guangluo.top` | `http://192.168.10.5:18080` | `192.168.10.5` |

- HTTPS 入口由 NAS `192.168.10.5:443` 的 **DSM 反向代理**管理，不在 `macmini/npm.yaml`；历史 NPM 数据/证书不适用于恢复当前入口。
- 上表域名由 Mac mini 的**原生 AdGuard Home** 重写到 NAS `192.168.10.5`。主网 DHCP 也可能提供 UDM `192.168.10.1` 作为备选 DNS，但 11 月 23 日核查 UDM 对 `photo`、`download`、`ha` 返回 NXDOMAIN，不能把 UDM 解析结果视作全部入口已覆盖。SmartDNS 的旧 `dsm.guangluo.top` 记录证书不匹配，DSM 应通过 `nas.guangluo.top` 访问。
- `ha.guangluo.top` 连接 NAS 的 Home Assistant `:8123`（原生 DSM 反代 → HTTP 后端）。`homeassistant/compose.yaml` 已纳入 `current.sh` 的 **NAS 默认恢复列表**，不是 Mac mini 服务；私有 `/config`、`.storage`、`secrets.yaml`、`go2rtc`、C700 定制组件与 recorder 数据库需另行恢复。HA 使用反代时，`trusted_proxies` 和 `use_x_forwarded_for` 应按实际 DSM 连接源地址核对，不能仅凭这份快照猜测或开放整个内网段。
- `metadata.guangluo.top` 连接 NAS 的 Collect Metadata Web `:18080`。`collect-metadata/compose.yaml` 已纳入 **NAS 默认恢复列表**；对应 PostgreSQL `macmini/collect-metadata.yaml` 已纳入 **Mac mini 默认恢复列表**，使用 `192.168.10.4:15433` 的数据库端口和客户端 TLS。恢复时必须先准备 PostgreSQL 卷、数据库密码及双向 TLS 证书，不可只恢复 Web 容器。
- `adguard.guangluo.top` 的后端是 Mac mini `:6200` **原生** AdGuard 的管理界面，不能用旧 Docker `adguardhome` 代替。
- `download.guangluo.top` 的 DSM 后端是 qBittorrent Docker 控制网 `172.30.61.2:8080`；从其它主机直接连接该私有地址不代表可达。

## 恢复责任边界（默认脚本不会自动做）

1. **Mac mini 原生**：从真实备份恢复 AdGuard Home 可执行文件、launchd plist、现用 YAML、重写与过滤规则；保持其 53 端口、6200 管理端口、SmartDNS `127.0.0.1:6053` 上游连通。不能直接复用旧容器的私有目录而跳过格式/路径验证。
2. **NAS DSM**：从 DSM 配置备份或现机导出恢复上述 11 条反代规则、HTTPS 域名证书、关联绑定、WebSocket/自定义标头等设置。路由/证书恢复成功前，不应主动启用旧 NPM。
3. **NAS Home Assistant**：按 `docs/restore.md` 恢复 `/config`、HA recorder 的 PostgreSQL 数据及证书/认证、C700/go2rtc 组件。核实 `:8123` 和 DSM 反代对其来源 IP 的信任配置。
4. **NAS+Mac mini Collect Metadata**：先验证 `15433` PostgreSQL 数据卷和 TLS、再核对 NAS `:18080` Web 及其私有状态/翻译令牌。本文没有实际执行任何数据库恢复。
5. **验证方式**：先在对应主机运行 `bash scripts/current.sh plan nas`、`plan macmini`；确认选择范围后再按 `docs/restore.md` 的私有数据清单做只读核对。上表 11 个域名的 2026-11-23 测试状态不是未来恢复的自动验收。
