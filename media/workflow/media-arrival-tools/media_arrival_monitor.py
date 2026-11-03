"""NAS post-arrival observer + Emby overview repair. Never modifies media.
Runs every two minutes under cron. Subtitle and overview processing only.
Subtitle waiting means missing acquisition automation, not successful translation.
"""
import datetime
import fcntl
import hashlib
import http.cookiejar
import json
import os
import sqlite3
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from media_notifications import Outbox, atomic_json, http_sender

RUNTIME = Path('/volume1/docker/homelab/media/workflow')
STATE = RUNTIME / 'media-arrival-state'
ANI = Path('/volume1/docker/homelab/media/ani-rss')
EMBY_CONFIG = Path('/volume1/docker/homelab/media/emby/config')
ENV_FILE = Path('/volume1/docker/homelab/.env')
DOCKER = '/usr/local/bin/docker'
FIELDS = 'Path,Overview,ProviderIds,Genres,People,Studios,Tags,ProductionLocations,OriginalTitle,SortName,PremiereDate,DateCreated,Taglines'


def chinese(text):
    # Kanji alone is not proof of Chinese; Japanese kana requires translation.
    return bool(text) and any('一' <= char <= '鿿' for char in text) and not any(
        '぀' <= char <= 'ヿ' for char in text)


DAILY_TRANSLATION_LIMIT = int(os.environ.get('EMBY_TRANSLATION_DAILY_LIMIT', '100'))


def reserve_translation(journal, day, save):
    """Durable conservative budget: count attempts before remote LLM invocation."""
    budget = journal.setdefault('translation_budget', {})
    used = int(budget.get(day, 0))
    if used >= DAILY_TRANSLATION_LIMIT:
        raise ValueError('DAILY_OVERVIEW_TRANSLATION_LIMIT')
    budget[day] = used + 1
    save(journal)


def overview_action(item, cached):
    text = item.get('Overview')
    if chinese(text):
        return 'keep', text
    if text:
        return 'translate', text
    tmdb = item.get('ProviderIds', {}).get('Tmdb')
    if item.get('Type') == 'Series' and tmdb and cached.get(tmdb):
        return 'cached', cached[tmdb]
    return 'missing', None




def subtitle_status(probe, sidecar_languages):
    languages = [s.get('tags', {}).get('language', '').lower() for s in probe['streams'] if s.get('codec_type') == 'subtitle'] + sidecar_languages
    if any(l in ('zh', 'zho', 'chi', 'zh-cn', 'zh-tw', 'chs', 'cht') for l in languages):
        return 'skipped', '已发现中文独立字幕，跳过翻译；原字幕保留。'
    return 'waiting', '未发现标记为中文的独立字幕。内嵌画面字幕仍可能存在；严格自动获取/翻译尚未接入，不报告完成。'


def request_json(url, data=None, headers=None, opener=None):
    h = dict(headers or {})
    if data is not None:
        h['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=None if data is None else json.dumps(data, ensure_ascii=False).encode(), headers=h)
    with (opener.open(req, timeout=45) if opener else urllib.request.urlopen(req, timeout=45)) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def emby_api_key():
    """Prefer the stable Emby API key from the homelab .env over a scraped user session token."""
    for name in ('EMBY_API_KEY', 'JELLYFIN_API_KEY'):
        value = os.environ.get(name, '').strip()
        if value:
            return value
    try:
        for raw in ENV_FILE.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            if key.strip() in ('EMBY_API_KEY', 'JELLYFIN_API_KEY'):
                value = value.strip().strip('\'"')
                if value:
                    return value
    except OSError:
        pass
    # Last resort: an active session token from Emby's own database.
    db = sqlite3.connect('file:' + str(EMBY_CONFIG / 'data/authentication.db') + '?mode=ro', uri=True)
    try:
        return db.execute('select AccessToken from Tokens_2 where IsActive=1 limit 1').fetchone()[0]
    finally:
        db.close()


class Emby:
    def __init__(self):
        self.token = emby_api_key()

    def api(self, path, data=None):
        return request_json('http://127.0.0.1:6100/emby' + path, data, {'X-Emby-Token': self.token})

    def items(self):
        return self.api('/Items?Recursive=true&IncludeItemTypes=Series,Episode&Fields=' + FIELDS)['Items']

    def update_overview(self, original, translated):
        item = self.api('/Items?Ids=' + original['Id'] + '&Fields=' + FIELDS)['Items'][0]
        if item.get('Overview') != original.get('Overview') or item.get('ProviderIds') != original.get('ProviderIds'):
            raise ValueError('EMBY_METADATA_CHANGED')
        before = dict(item)
        atomic_json(STATE / 'metadata-backups' / (item['Id'] + '-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S%f') + '.json'), before)
        item['Overview'] = translated
        self.api('/Items/' + item['Id'], item)
        after = self.api('/Items?Ids=' + item['Id'] + '&Fields=' + FIELDS)['Items'][0]
        if after.get('Overview') != translated or after.get('ProviderIds') != before.get('ProviderIds') or after.get('Name') != before.get('Name'):
            raise ValueError('EMBY_UPDATE_VERIFY_FAILED')


def translate(text):
    # A native backend invocation, not app startup/migrations or scheduler.
    code = '''import sqlite3,json,logging
logging.disable(logging.CRITICAL)
from translation.deepseek import DeepSeekBackend
from translation.concurrency import get_concurrency
c=sqlite3.connect('file:/config/sublarr.db?mode=ro',uri=True)
k=c.execute("select value from config_entries where key='backend.deepseek.api_key'").fetchone()[0]
c.close()
get_concurrency().register('deepseek',1)
r=DeepSeekBackend(api_key=k,model='deepseek-chat').translate_batch(TEXT,'auto','zh')
assert r.success and len(r.translated_lines)==1
print(json.dumps(r.translated_lines,ensure_ascii=False))
'''.replace('TEXT', repr([text]))
    r = subprocess.run([DOCKER, 'exec', 'media-sublarr', 'python3', '-B', '-c', code], capture_output=True, text=True, timeout=180)
    if r.returncode:
        raise RuntimeError('OVERVIEW_TRANSLATION_FAILED')
    result = json.loads(r.stdout)[0]
    if not chinese(result):
        raise ValueError('NON_CHINESE_TRANSLATION')
    return result


def torrents(config):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = 'http://172.30.61.2:8080'
    data = urllib.parse.urlencode({'username': config['downloadToolUsername'], 'password': config['downloadToolPassword']}).encode()
    with op.open(urllib.request.Request(base + '/api/v2/auth/login', data=data), timeout=30):
        pass  # HTTP204 means already authenticated on trusted subnet.
    return request_json(base + '/api/v2/torrents/info', opener=op)


def probe_file(path):
    relative = Path(path).relative_to('/entertainments/Media/番剧')
    if '..' in relative.parts:
        raise ValueError('UNSAFE_PATH')
    local = Path('/volume1/homes/guangluo/entertainments/Media/番剧') / relative
    s = local.stat()
    media_path = '/media/Media/番剧/' + relative.as_posix()
    r = subprocess.run([DOCKER, 'exec', 'media-sublarr', 'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', media_path], capture_output=True, text=True, timeout=90)
    if r.returncode:
        raise ValueError('MEDIA_PROBE_FAILED')
    if local.stat().st_size != s.st_size or local.stat().st_mtime_ns != s.st_mtime_ns:
        raise ValueError('MEDIA_CHANGED')
    languages = []
    sidecar_versions = []
    for p in local.parent.iterdir():
        if p.name.startswith(local.stem + '.') and p.suffix.lower() in ('.srt', '.ass', '.ssa', '.vtt'):
            languages.extend(p.name[len(local.stem) + 1:].lower().split('.')[:-1])
            ps = p.stat()
            sidecar_versions.append((p.name, ps.st_size, ps.st_mtime_ns))
    version = hashlib.sha256(json.dumps(sorted(sidecar_versions)).encode()).hexdigest()
    return json.loads(r.stdout), languages, '{}:{}:{}'.format(s.st_size, s.st_mtime_ns, version)


def run():
    STATE.mkdir(parents=True, exist_ok=True)
    os.chmod(str(STATE), 0o700)
    with (STATE / 'monitor.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        config = json.loads((ANI / 'config.v2.json').read_text())
        journal_path = STATE / 'journal.json'
        journal = json.loads(journal_path.read_text()) if journal_path.exists() else {'torrents': {}, 'metadata': {}}
        outbox = Outbox(STATE / 'outbox')
        notifications = next(n for n in config['notificationConfigList'] if n.get('notificationType') == 'WEB_HOOK' and n.get('enable'))
        headers = {k.strip(): v.strip() for k, v in (line.split(':', 1) for line in notifications['webHookHeader'].splitlines() if line.strip())}
        sender = http_sender('http://127.0.0.1:8000/notify/nas', headers)
        errors = []
        completed = 0
        # Only recent completions at install, then future completions. No historical spam.
        cutoff = 1793634000  # 2026-11-02 23:40 +08:00
        for torrent in torrents(config):
            if torrent.get('progress') != 1 or torrent.get('completion_on', 0) < cutoff:
                continue
            path = torrent.get('content_path', '')
            if not path.startswith('/entertainments/Media/番剧/'):
                continue
            key = torrent['hash'] + ':' + str(torrent['completion_on'])
            if journal['torrents'].get(key) == 'missing':
                continue
            try:
                probe, sidecars, generation = probe_file(path)
                fingerprint = key + ':' + generation
                if journal['torrents'].get(key) == fingerprint:
                    continue
                for stage, result in [('subtitle', subtitle_status(probe, sidecars))]:
                    state, detail = result
                    outbox.enqueue(stage, state, path, fingerprint, detail + '（自动到达检查）')
                journal['torrents'][key] = fingerprint
                completed += 1
            except FileNotFoundError:
                # Ani-RSS renames files after qbittorrent stored content_path; nothing left to observe.
                journal['torrents'][key] = 'missing'
            except Exception as exc:
                errors.append({'stage': 'arrival', 'id': torrent['hash'], 'error': type(exc).__name__})
        emby = Emby()
        subscriptions = json.loads((ANI / 'ani.v2.json').read_text())
        cached = {str(a['tmdb']['id']): a['tmdb']['overview'] for a in subscriptions if a.get('tmdb') and chinese(a['tmdb'].get('overview'))}
        repaired = 0
        attempted = 0
        journal.setdefault('retry_after', {})
        import time
        for item in emby.items():
            if not item.get('Path', '').startswith('/media/番剧/') or attempted >= 2 or journal['retry_after'].get(item['Id'], 0) > time.time():
                continue
            action, source = overview_action(item, cached)
            if action in ('keep', 'missing'):
                continue
            digest = hashlib.sha256((source + json.dumps(item.get('ProviderIds', {}), sort_keys=True)).encode()).hexdigest()
            cached_translation = journal['metadata'].get(digest)
            attempted += 1
            try:
                if cached_translation:
                    text = cached_translation
                elif action == 'translate':
                    reserve_translation(journal, datetime.date.today().isoformat(),
                                        lambda value: atomic_json(journal_path, value))
                    text = translate(source)
                else:
                    text = source
                if not chinese(text):
                    raise ValueError('OVERVIEW_TRANSLATION_NOT_CHINESE')
                # Retain translation before update so retries do not incur another LLM charge.
                journal['metadata'][digest] = text
                atomic_json(journal_path, journal)
                emby.update_overview(item, text)
                repaired += 1
            except Exception as exc:
                journal['retry_after'][item['Id']] = time.time() + 3600
                errors.append({'stage': 'metadata', 'id': item['Id'], 'error': type(exc).__name__})
        atomic_json(journal_path, journal)
        delivered = 0
        for path in outbox.root.glob('*.json'):
            try:
                event = json.loads(path.read_text())
                if not event['delivered'] and outbox.deliver(path, sender):
                    delivered += 1
            except Exception as exc:
                errors.append({'stage': 'notification', 'id': path.stem, 'error': type(exc).__name__})
        summary = {'time': datetime.datetime.now().isoformat(), 'arrival_checked': completed, 'overview_repaired': repaired, 'notifications_delivered': delivered, 'errors': errors}
        atomic_json(STATE / 'last-run.json', summary)
        print(json.dumps(summary, ensure_ascii=False))

if __name__ == '__main__':
    run()
