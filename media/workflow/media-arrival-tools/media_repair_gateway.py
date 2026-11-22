from importlib.util import module_from_spec, spec_from_file_location
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import ProxyHandler, Request, build_opener


HOMELAB = Path(__file__).resolve().parents[3]
DOCKER = '/usr/local/bin/docker'
COLLECT_STATE = HOMELAB / 'collect-metadata' / 'media-arrival'
TRANSLATION_TOKEN = HOMELAB / 'metadata-translation' / 'episodes' / 'token'
MAINTENANCE = 'homelab_maintenance_default'


def post(container, network, port, path, token_file, payload, timeout):
    template = '{{(index .NetworkSettings.Networks "' + network + '").IPAddress}}'
    address = IPv4Address(subprocess.check_output(
        [DOCKER, 'inspect', '--format', template, container], text=True, timeout=5,
    ).strip())
    token = token_file.read_text().strip()
    request = Request(f'http://{address}:{port}/{path}', json.dumps(payload).encode(), {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
    })
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        return json.load(response)


def translate(text):
    response = post(
        'media-sublarr', 'collect-metadata_translation',
        7100, 'translate', TRANSLATION_TOKEN, {'target_language': 'zh', 'texts': [text]}, 35,
    )
    translations = response.get('translations')
    if not isinstance(translations, list) or len(translations) != 1 or not translations[0]:
        raise ValueError('OVERVIEW_TRANSLATION_FAILED')
    return translations[0]


def write_metadata(original, field, text):
    keys = ('Id', 'Path', 'Type', 'ProviderIds', 'SeriesId', 'ParentIndexNumber', 'IndexNumber', field)
    response = post(
        'collect-metadata-web-1', MAINTENANCE, 7099, 'repair', COLLECT_STATE / 'token',
        {'original': {key: original.get(key) for key in keys}, 'field': field, 'text': text}, 50,
    )
    return response['written'] is True


def publish_status(state_dir):
    module_path = HOMELAB / 'media' / 'workflow' / 'media-arrival-status' / 'server.py'
    spec = spec_from_file_location('media_arrival_summary', module_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STATE = state_dir
    snapshot = module.status()
    snapshot.pop('pending_details', None)
    snapshot.pop('budget_limit', None)
    owner = COLLECT_STATE.stat()
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=COLLECT_STATE, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(snapshot, stream, ensure_ascii=False)
            stream.flush()
            os.fchown(stream.fileno(), owner.st_uid, owner.st_gid)
            os.fchmod(stream.fileno(), 0o640)
            os.replace(temporary, COLLECT_STATE / 'status.json')
        finally:
            temporary.unlink(missing_ok=True)
