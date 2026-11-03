# 部署脚本

双主机拓扑使用 `current.sh`，功能目录与启动入口见 [FUNCTIONAL-LAYOUT.md](../FUNCTIONAL-LAYOUT.md)，先阅读 [恢复说明](../docs/restore.md)。`check` 只校验 Compose、`.env` 占位符与绑定挂载路径；`apply` 才会拉取镜像并启动。

下面的单机脚本是独立的 12 容器核心服务安装器，不代表当前完整拓扑。

# 新 Linux 主机安装

将 `install-linux-core.sh` 复制到全新 Ubuntu / Debian x86_64 或 ARM64 服务器，运行：

```sh
sudo bash install-linux-core.sh
```

默认安装目录 `/opt/homelab`，也可指定：`sudo bash install-linux-core.sh /srv/homelab`。
脚本从 Docker 官方 apt 仓库安装引擎和 Compose；已安装时复用并检查。

包含 Emby、Ani-RSS、qBittorrent、Glance、Glances、Uptime Kuma、Apprise、Nginx Proxy Manager，以及独立的 Immich 四容器项目。Immich 编排源自制作脚本时的官方 release 下载文件，首次拉取 release 镜像；此脚本适用于空白部署，不用于升级旧 Immich 数据库。

默认监听 127.0.0.1。首次访问可在自己的电脑运行：

```sh
ssh -L 6001:127.0.0.1:6001 -L 6104:127.0.0.1:6104 -L 7001:127.0.0.1:7001 用户名@服务器地址
```

然后打开 http://localhost:6001、http://localhost:6104、http://localhost:7001。
需要局域网直连时，将 `/opt/homelab/.env` 和 `/opt/homelab/immich/.env` 中 `BIND_IP` 改成服务器局域网 IP，再执行：

```sh
cd /opt/homelab
sudo docker compose up -d
cd immich
sudo docker compose up -d
```

服务端口：6001 Glance、6002 Glances、6003 Uptime Kuma、6100 Emby、6101 Ani-RSS、6102 qBittorrent、6104 Immich、7001 NPM、8000 Apprise，NPM 另有 80/443。

媒体统一存放在安装目录的 `media/`，容器内路径 `/media`。下载器与 Ani-RSS、Emby 的账号、目录和联动需要首次设置。qBittorrent 临时密码用 `sudo docker compose logs qbittorrent` 查看。服务数据使用 Docker 命名卷；Immich 相册和数据库使用 `immich/library/` 与 `immich/postgres/`。备份时需同时备份配置、卷数据和相册，数据库使用一致性备份。

重跑会保留生成的配置和密码，但会拉取浮动标签镜像，所以后续日常维护应按服务升级说明执行。任何启动失败会退出并保留数据，不自动回滚。`--wait` 能检查容器运行状态及镜像自带健康检查；它不能代替首次登录验证。

尚未包含：AdGuard Home / SmartDNS / Sing-box 网关、公网 SSH 隧道、手机通知路由、Sublarr、Watchtower，以及已有域名、证书、监控项目和照片媒体数据迁移。这些需要补齐当前实际配置；现有 Glance 页面含家庭固定地址及凭据依赖，新安装使用简化页面。脚本不会修改原 NAS 或 Mac mini。
