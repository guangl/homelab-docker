# 部署脚本

`current.sh` 对应 2026-11-06 核验的双主机 18 个自管容器。先按 [恢复说明](../docs/restore.md) 恢复数据、网络与根 `.env`。

```sh
# 分别在对应 Docker 主机执行：
bash scripts/current.sh check nas
bash scripts/current.sh apply nas
bash scripts/current.sh check macmini
bash scripts/current.sh apply macmini
```

`check` 解析全部编排并检查本机挂载和占位符，不启动容器。`apply` 完成检查后拉取镜像、逐组启动并等待运行/健康状态；不删除卷，不使用 `--remove-orphans`，失败退出。需要 Docker Compose v2 和 Python 3。

NAS 的 7 个文件共用原有项目及网络。Mac mini 的 DNS 使用 OrbStack 的 host 网络能力，普通 Docker Desktop 不可直接等同替换。旧单机 12 容器安装器已移除，避免安装与现网不一致的拓扑。
