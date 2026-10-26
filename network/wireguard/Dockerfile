# WireGuard 服务端（用户态实现）
#
# 群晖 DSM 内核（4.4.302）没有 wireguard 内核模块，因此这里必须用 wireguard-go 用户态实现；
# 官方/社区镜像（lscr.io/linuxserver/wireguard、ghcr.io/wg-easy/wg-easy 等）都依赖内核模块，
# 在这台 NAS 上起不来，所以自建这个极小的镜像。
#
# 注意：Alpine 把 wg-quick 拆到了 wireguard-tools-wg-quick 子包里，
# 只装 wireguard-tools 会缺少 wg-quick（entry.sh 会报 wg-quick: not found）。
FROM alpine:3.22

RUN apk add --no-cache \
      wireguard-tools-wg-quick \
      wireguard-go \
      iptables \
      iproute2

# 实际启动命令由 compose 覆盖为 sh /config/entry.sh（/config 挂载本目录，便于改脚本不重建镜像）
CMD ["/bin/sh"]
