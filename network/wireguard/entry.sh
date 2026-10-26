#!/bin/sh
# 用户态 WireGuard 启动脚本（DSM 内核没有 wireguard 模块，只能 wireguard-go）
# 挂载：/config -> 宿主机 network/wireguard/（含 wg0.conf，私钥在其中，不入库）
set -u

IFACE=wg0
CONF=/config/wg0.conf
WG_NET=10.66.66.0/24

log() { echo "[wg] $*"; }

[ -f "$CONF" ] || { log "缺少 $CONF，请先在宿主机 network/wireguard/ 下创建 wg0.conf"; exit 1; }

# 1) 开启 IPv4 转发（host 网络 + privileged 时作用于宿主机）
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
if [ "$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null)" != "1" ]; then
  log "无法开启 net.ipv4.ip_forward，请确认容器为 privileged + network_mode: host"
  exit 1
fi

# 2) 启动接口：内核模块缺失时 wg-quick 会自动回退到 wireguard-go
export WG_QUICK_USERSPACE_IMPLEMENTATION=wireguard-go
if wg show "$IFACE" >/dev/null 2>&1; then
  log "$IFACE 已存在（容器重启时宿主机接口可能仍在），跳过 wg-quick up"
else
  wg-quick up "$CONF" || { log "wg-quick up 失败"; exit 1; }
fi

# 3) NAT：按默认路由出口网卡做 MASQUERADE（群晖可能是 bond0 / ovs_eth0 / eth0）
WAN_IF=$(ip route show default 2>/dev/null | awk '{print $5; exit}')
if [ -n "$WAN_IF" ] && ! iptables -t nat -C POSTROUTING -s "$WG_NET" -o "$WAN_IF" -j MASQUERADE 2>/dev/null; then
  iptables -t nat -A POSTROUTING -s "$WG_NET" -o "$WAN_IF" -j MASQUERADE
fi

# 4) 转发放行（wg-quick 一般已加，这里保证幂等）
iptables -C FORWARD -i "$IFACE" -j ACCEPT 2>/dev/null || iptables -A FORWARD -i "$IFACE" -j ACCEPT
iptables -C FORWARD -o "$IFACE" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null ||
  iptables -A FORWARD -o "$IFACE" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

log "WireGuard 已就绪（$IFACE，出口 $WAN_IF）"

# 5) 守护：用户态进程异常退出后接口会消失，自动重建
while :; do
  sleep 60
  if ! wg show "$IFACE" >/dev/null 2>&1; then
    log "$IFACE 丢失，尝试重新启动"
    wg-quick up "$CONF" >/dev/null 2>&1 || log "重启失败，等待下一轮"
  fi
done
