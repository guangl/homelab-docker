#!/usr/bin/env python3
"""Offline validation of the blog#52 DSM/AdGuard snapshot (no network or DSM writes)."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'docs/entrypoints-2026-11-23.json').read_text())
assert manifest['observed_at'] == '2026-11-23'
assert manifest['ingress'] == {'host': '192.168.10.5', 'scheme': 'https', 'port': 443, 'manager': 'Synology DSM reverse proxy'}
assert manifest['dns']['rewrite_a'] == '192.168.10.5'
expected = {
    'home': ('http', '192.168.10.5', 6001),
    'movie': ('http', '192.168.10.5', 6100),
    'anime': ('http', '192.168.10.5', 6101),
    'download': ('http', '172.30.61.2', 8080),
    'photo': ('http', '192.168.10.5', 6104),
    'top': ('http', '192.168.10.5', 6002),
    'monitor': ('http', '192.168.10.5', 6003),
    'adguard': ('http', '192.168.10.4', 6200),
    'nas': ('https', '192.168.10.5', 5001),
    'ha': ('http', '192.168.10.5', 8123),
    'metadata': ('http', '192.168.10.5', 18080),
}
seen = {}
for route in manifest['routes']:
    name = route['hostname']
    assert name.endswith('.guangluo.top'), name
    label = name.removesuffix('.guangluo.top')
    assert label not in seen, f'duplicate hostname: {name}'
    seen[label] = (route['backend']['scheme'], route['backend']['host'], route['backend']['port'])
    assert route['dns_a'] == '192.168.10.5', name
assert seen == expected, (seen, expected)

script = (root / 'scripts/current.sh').read_text()
assert 'homeassistant/compose.yaml' in script  # NAS default
assert 'collect-metadata/compose.yaml' in script  # NAS default
assert 'macmini/collect-metadata.yaml' in script  # Mac mini default
assert 'macmini/npm.yaml' in script  # explicit legacy-only
assert 'macmini/smartdns.yaml' in script  # Mac mini default

doc = (root / 'docs/entrypoints.md').read_text()
for label in expected:
    assert f'`{label}.guangluo.top`' in doc
assert '不是 DSM 可导入的配置文件' in doc
print('PASS: 11 DSM routes, DNS rewrite targets, HA/Metadata inclusion and snapshot limitations')
