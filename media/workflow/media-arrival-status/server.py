import datetime
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE = Path('/state')
STALE_SECONDS = 600
PORT = 7099
BUDGET_LIMIT = int(os.environ.get('EMBY_TRANSLATION_DAILY_LIMIT', '100'))


def load(name, default):
    try:
        return json.loads((STATE / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def human_age(seconds):
    if seconds < 90:
        return str(int(seconds)) + ' 秒前'
    if seconds < 5400:
        return str(int(seconds // 60)) + ' 分钟前'
    if seconds < 172800:
        return format(seconds / 3600, '.1f') + ' 小时前'
    return format(seconds / 86400, '.1f') + ' 天前'


def status():
    last = load('last-run.json', {})
    journal = load('journal.json', {})
    now = datetime.datetime.now()
    stamp = last.get('time')
    age = None
    if stamp:
        try:
            age = max(0.0, (now - datetime.datetime.fromisoformat(stamp)).total_seconds())
        except ValueError:
            age = None
    errors = last.get('errors') or []
    if age is None:
        state, label = 'unknown', '没有运行记录'
    elif age > STALE_SECONDS:
        state, label = 'stale', '已停滞'
    elif errors:
        state, label = 'warn', '有告警'
    else:
        state, label = 'ok', '正常'
    budget = (journal.get('translation_budget') or {}).get(now.strftime('%Y-%m-%d'), 0)
    return {
        'state': state,
        'state_label': label,
        'time': stamp,
        'age_seconds': None if age is None else round(age),
        'age_text': '从未运行' if age is None else human_age(age),
        'stale_after_seconds': STALE_SECONDS,
        'last_repaired': last.get('overview_repaired', 0),
        'last_errors': len(errors),
        'error_text': '; '.join(str(e.get('stage')) + ' ' + str(e.get('error')) for e in errors),
        'repaired_total': len(journal.get('metadata') or []),
        'budget_today': budget,
        'budget_limit': BUDGET_LIMIT,
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        raw = payload.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        data = status()
        if path in ('/', '/status.json'):
            self._send(200, json.dumps(data, ensure_ascii=False))
        elif path == '/healthz':
            ok = data['state'] in ('ok', 'warn')
            self._send(200 if ok else 503, json.dumps({'ok': ok, 'state': data['state'], 'age_text': data['age_text']}, ensure_ascii=False))
        else:
            self._send(404, json.dumps({'error': 'not found'}))

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
