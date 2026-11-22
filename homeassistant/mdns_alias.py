"""Publish Xiaomi's required local OAuth hostname without changing NAS DNS."""
import os
import signal
import socket
import threading

from zeroconf import IPVersion, ServiceInfo, Zeroconf

address = os.environ.get("HA_HOST_IP", "192.168.10.5")
stop = threading.Event()
for sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(sig, lambda *_: stop.set())

service = ServiceInfo(
    "_http._tcp.local.",
    "Home Assistant Xiaomi OAuth._http._tcp.local.",
    addresses=[socket.inet_aton(address)],
    port=8123,
    properties={"path": "/"},
    server="homeassistant.local.",
)
zeroconf = Zeroconf(interfaces=[address], ip_version=IPVersion.V4Only)
try:
    zeroconf.register_service(service, allow_name_change=False)
    print(f"Published homeassistant.local -> {address}", flush=True)
    stop.wait()
finally:
    zeroconf.unregister_service(service)
    zeroconf.close()
