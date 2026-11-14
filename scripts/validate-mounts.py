#!/usr/bin/env python3
"""Check a resolved Compose file without printing private configuration values."""
import argparse
import json
from pathlib import Path
import sys


DIRECTORY_CONFIGS = {
    '/etc/smartdns': 'smartdns.conf',
    '/opt/adguardhome/conf': 'AdGuardHome.yaml',
    '/app/config': 'glance.yml',
    '/app': 'server.py',
}
CONTAINER_CONFIGS = {
    'phone-notification-router': 'router.json',
    'ani-rss': 'config.v2.json',
    'qbittorrent': 'qBittorrent.conf',
}
CONFIG_SUFFIXES = {'.json', '.yaml', '.yml', '.conf'}


def has_placeholder(value):
    if isinstance(value, str):
        return 'REPLACE_' in value
    if isinstance(value, dict):
        return any(has_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(has_placeholder(item) for item in value)
    return False


def check_file(path, errors):
    if not path.is_file():
        errors.add(f'缺少配置文件：{path}')
        return
    try:
        with path.open(errors='replace') as config:
            if any('REPLACE_' in line for line in config):
                errors.add(f'配置仍有占位符：{path}')
    except OSError:
        errors.add(f'无法读取配置文件：{path}')


def validate(config):
    errors = set()
    for name, service in config['services'].items():
        for key, value in service.get('environment', {}).items():
            if has_placeholder(value):
                errors.add(f'环境变量仍有占位符：{name}.{key}')
        for volume in service.get('volumes', []):
            if volume.get('type') != 'bind':
                continue
            source = Path(volume['source'])
            target = volume['target']
            if has_placeholder(volume['source']):
                errors.add(f'挂载路径仍有占位符：{name} → {target}')
                continue
            if not source.exists():
                errors.add(f'缺少挂载路径：{source}')
                continue
            config_name = DIRECTORY_CONFIGS.get(target)
            if target == '/config':
                config_name = CONTAINER_CONFIGS.get(service.get('container_name'))
            if config_name:
                check_file(source / config_name, errors)
            elif source.suffix in CONFIG_SUFFIXES and not source.is_dir():
                check_file(source, errors)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print-networks', action='store_true')
    args = parser.parse_args()
    try:
        config = json.load(sys.stdin)
        errors = validate(config)
        networks = {
            network.get('name', key)
            for key, network in config.get('networks', {}).items()
            if network.get('external')
        }
    except (KeyError, ValueError, TypeError, AttributeError, OSError):
        sys.exit('无法读取或校验 Docker Compose 解析后的配置。')
    if errors:
        sys.exit('\n'.join(sorted(errors)))
    if args.print_networks:
        for network in sorted(networks):
            print(network)


if __name__ == '__main__':
    main()
