# 当前拓扑恢复说明

核验日期：2026-11-03，Asia/Shanghai。此次整理只读访问了两台主机，未重启或修改运行服务。公开编排以实际运行服务为准；旧的大编排中未运行的服务没有带回。

## 部署单元

| 文件 | 容器 | 项目名 |
| --- | --- | --- |
| `deploy/nas/immich.yaml` | immich-server、immich-database、immich-redis | homelab_application |
| `deploy/nas/ani-rss.yaml` | ani-rss | homelab_application |
| `deploy/nas/qbittorrent.yaml` | qbittorrent | homelab_application |
| `deploy/nas/emby.yaml` | media-emby | media-emby |
| `deploy/nas/sublarr.yaml` | media-sublarr | media-sublarr |
| `deploy/nas/maintenance.yaml` | glance、glances、uptime-kuma、watchtower、apprise、phone-notification-router | homelab_maintenance |
| `deploy/nas/network.yaml` | smartdns、adguardhome、network-gateway | homelab_network |
| `deploy/nas/tunnel.yaml` | public-sites-tunnel | homelab-cloud-relay |
| `deploy/macmini/npm.yaml` | nginx-proxy-manager | homelab_network |
| `deploy/macmini/immich-ml.yaml` | immich-machine-learning | immich-ml |

保留原项目名。前三个文件共享项目与网络，执行时不要添加 `--remove-orphans`，否则可能移除同项目的其他服务。NAS 与 Mac mini 的同名项目位于不同 Docker 主机，不能直接将十个文件合成同一主机上的部署。

## 私有文件和数据

1. 复制根 `.env.example` 为 `.env`，设置为 `600`，填写实际密码、API 参数和数据路径。`DB_PASSWORD` 必须与恢复的 Immich 数据库一致。
2. 恢复 NAS 的 `HOMELAB_ROOT`、媒体目录，以及 Mac mini 的 `NPM_ROOT`、`ML_ROOT`。挂载都禁止自动创建路径，缺项时脚本会停止。
3. 从 `templates/runtime/` 将公开支持文件复制到 NAS `HOMELAB_ROOT` 下相同相对路径，保留已有配置；不要覆盖现网文件。将 Glance 的 `maintenance/glance/config/` 也复制到相同相对路径。
4. 为以下 `.example` 文件去掉后缀并填入真实值，放到对应运行目录：
   - `network/adguardhome/conf/AdGuardHome.yaml`：填写 bcrypt 登录密码 hash；不是明文密码，也不要以空用户配置代替。
   - `network/sing-box/config.json`：恢复 WireGuard 私钥和对端公钥；网络地址、对端路由需符合实际环境。
   - `maintenance/phone-routing/router.json`：填写邮件、Bark 目标和 Apprise 凭据。路由程序探测 `192.168.10.100`，可在迁移时修改。
   - `application/ani-rss/config.v2.json`：恢复下载器登录、API key、登录信息和通知认证头等字段；`REPLACE_` 均为占位值。
   - `application/qbittorrent/config/qBittorrent.conf`：恢复登录信息；示例不保留旧密码 hash。
5. 按 `maintenance/.env.glance.example` 创建 `HOMELAB_ROOT/maintenance/.env.glance`，设置 `600`。
6. 在 `HOMELAB_ROOT/network/cloud-relay/secrets/` 恢复隧道 `id_ed25519` 与已验证的 `known_hosts`，私钥权限 `600`。云端必须已配置对应账号与远程转发许可。
7. 恢复 Emby、Sublarr、Ani-RSS、qBittorrent、Uptime Kuma、Apprise 的配置/数据库及 Immich 相册、PostgreSQL 数据。数据库备份需要在一致性条件下恢复。仅有 Git 配置不会恢复账号、相册索引、订阅、监控项目或媒体记录。
8. Mac mini 需要恢复 NPM 的 data 与 letsencrypt 目录，以及机器学习 model-cache。`npm-proxy-hosts.json` 是从实际数据库选择导出的路由配置，**不是可直接导入的 NPM 数据库备份**；没有私有数据库备份时，需在 NPM 中据此重建转发并重新申请证书。

第一次在新主机恢复目录时，应按各容器要求设置权限。应用主要使用 NAS 的 `1026:100`，但 qBittorrent 当前使用 `0:0`、Sublarr 容器入口为 root、手机通知路由需要 `NET_RAW`；不要对全部配置和数据执行统一递归 chown。Immich 数据库保留现网非 root entrypoint、PostgreSQL 配置与 tmpfs 参数。

## Docker 网络

以下网络根据 NAS 实测导出，创建前先确认新主机无相同网段冲突：

```sh
docker network create --driver bridge --subnet 172.19.0.0/16 --gateway 172.19.0.1 homelab_application_default
docker network create --driver bridge --internal --subnet 172.30.61.0/24 qb_control
# bond0 是当前 NAS 父接口，迁移时替换成新主机真实接口。
docker network create --driver macvlan --subnet 192.168.10.0/24 --ip-range 192.168.10.6/32 --gateway 192.168.10.1 -o parent=bond0 qb_direct_lan
```

仅创建缺失网络，不要删除或重建原主机正在使用的网络。qBittorrent 在 `qb_direct_lan` 固定使用 `192.168.10.6`，在 `qb_control` 固定使用 `172.30.61.2`，DNS 为 `172.30.61.1`；Ani-RSS 和 Kuma 连接内部控制网络。NAS 的 53 端口由 AdGuard 监听，需要保证内部 bridge 上可以访问。宿主机默认不能直接访问自身 macvlan 容器，现有页面通过 Mac mini 的 NPM 访问下载器。

## 检查和启动

在对应 Docker 主机上运行，先检查全部配置和挂载路径，再启动：

```sh
bash scripts/current.sh check nas
bash scripts/current.sh apply nas
# Mac mini：
bash scripts/current.sh check macmini
bash scripts/current.sh apply macmini
```

脚本要求 Docker Compose v2 与 Python 3，先检查全部文件，再拉取全部镜像，然后按顺序启动并等待健康状态。失败时保留数据并退出，不删除卷、不自动回滚。没有健康检查的容器只验证运行状态。需要进一步确认服务首次登录、DNS、媒体目录、通知、反代和 WireGuard 对端连接。

原 NAS 的 Compose 文件存放路径见 `deploy/inventory.json`。本仓库将公开入口统一到 `deploy/`，并将数据挂载参数化。对现网切换入口前，应备份配置、核对 Compose 项目标记和卷；本次上传未执行这种切换。

## 已核实的遗留项

- NPM 的 `dns` 仍写着 `192.168.5.1`。导出按实际容器配置保留，当前家庭主网是 `192.168.10.0/24`；迁移前需要选择实际可用的 DNS。
- NPM 的 `draw`、`read` 转发后端已停用，没有把旧应用重新加回部署。
- 公网隧道仍含 `127.0.0.1:16106 -> 192.168.10.5:6106`，对应应用已停用；另一个转发为 Glance 6001。恢复时确认是否需要保留旧转发。
- SmartDNS 仍保留部分旧域名的局域网解析记录，属于实机配置，不代表后端在运行。
- Surge SOCKS、UDM WireGuard 对端、DSM 本身与云端隧道端点不由这些 Compose 文件安装。Surge 需在 Mac mini 提供 `192.168.10.4:6153`，否则境外解析与默认代理出口不可用。

## 规则数据与证书

`templates/runtime/network/smartdns/conf/china-domains.txt` 是当前 NAS 实际加载的域名快照，来源说明及 SHA256 在同目录 `provenance.json`。CA 文件为公开证书链，不含私钥。

Sing-box 规则二进制来自运行中的 `geoip-cn.srs` 与 `geosite-cn.srs`，其更新地址保留在配置模板中，来源项目为 [SagerNet/sing-geoip](https://github.com/SagerNet/sing-geoip) 与 [SagerNet/sing-geosite](https://github.com/SagerNet/sing-geosite)。第三方数据和证书适用各自上游许可，不视为本仓库原创内容。
