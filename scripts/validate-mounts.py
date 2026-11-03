#!/usr/bin/env python3
"""Validate resolved Compose bind mounts without displaying private file contents."""
import json
import pathlib
import sys

config = json.load(sys.stdin)
errors = []
for service in config['services'].values():
    for volume in service.get('volumes', []):
        if volume.get('type') != 'bind':
            continue
        source = pathlib.Path(volume['source'])
        if not source.exists():
            errors.append(f'缺少挂载路径：{source}')
        elif source.is_file() and source.suffix in {'.json', '.yaml', '.yml', '.conf'}:
            if 'REPLACE_' in source.read_text(errors='replace'):
                errors.append(f'配置仍有占位符：{source}')
# Services that mount config directories also require their main config files.
required = {
    '/etc/sing-box': 'config.json',
    '/etc/smartdns': 'smartdns.conf',
    '/opt/adguardhome/conf': 'AdGuardHome.yaml',
    '/run/ssh': 'id_ed25519',
    '/app/config': 'glance.yml',
}
for service in config['services'].values():
    for volume in service.get('volumes', []):
        if volume.get('type') != 'bind':
            continue
        name = required.get(volume['target'])
        if volume['target'] == '/config':
            name = {
                'phone-notification-router': 'router.json',
                'ani-rss': 'config.v2.json',
                'qbittorrent': 'qBittorrent.conf',
            }.get(service.get('container_name'))
        if name:
            source = pathlib.Path(volume['source']) / name
            if not source.is_file():
                errors.append(f'缺少配置文件：{source}')
            elif 'REPLACE_' in source.read_text(errors='replace'):
                errors.append(f'配置仍有占位符：{source}')
        if volume['target'] == '/run/ssh':
            known = pathlib.Path(volume['source']) / 'known_hosts'
            if not known.is_file():
                errors.append(f'缺少已验证的 SSH 主机公钥文件：{known}')
if errors:
    sys.exit('\n'.join(sorted(set(errors))))
