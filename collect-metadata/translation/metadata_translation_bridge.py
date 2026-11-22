#!/usr/bin/env python3
"""Optional Collect Metadata HTTP adapter for Sublarr's existing DeepSeek backend."""
import datetime
import hmac
import html
import json
import os
import re
import sqlite3
import threading
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def plain_text(text):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', text)).split())


def is_chinese(text):
    # Emby descriptions may append a Japanese source below the existing Chinese text.
    text = plain_text(text).split('[简介原文]', 1)[0]
    han = len(re.findall(r'[\u3400-\u9fff\uf900-\ufaff]', text))
    kana_or_hangul = len(re.findall(r'[\u3040-\u30ff\u1100-\u11ff\uac00-\ud7af]', text))
    other_letters = sum(char.isalpha() for char in text) - han - kana_or_hangul
    return han > 0 and han * 2 >= other_letters and kana_or_hangul * 3 <= han


class Bridge:
    def __init__(self, backend, budget_path, daily_limit, shape_errors=()):
        self.backend = backend
        self.budget_path = budget_path
        self.daily_limit = daily_limit
        self.shape_errors = shape_errors
        self.lock = threading.Lock()
        with closing(sqlite3.connect(budget_path)) as db:
            db.execute('CREATE TABLE IF NOT EXISTS budget(day TEXT PRIMARY KEY, used INTEGER NOT NULL)')
            db.commit()

    def reserve(self, count):
        day = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        with closing(sqlite3.connect(self.budget_path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT used FROM budget WHERE day = ?', (day,)).fetchone()
            if (row[0] if row else 0) + count > self.daily_limit:
                return False
            db.execute('INSERT INTO budget VALUES (?, ?) ON CONFLICT(day) DO UPDATE SET used = used + excluded.used', (day, count))
            return True

    def translate_batch(self, texts, target, deadline):
        # Sublarr is line-oriented. A synopsis is one unit even when it has paragraphs.
        try:
            result = self.backend.translate_batch(texts, 'auto', target)
            if result.success and len(result.translated_lines) == len(texts):
                return [line.strip() if isinstance(line, str) and line.strip() else None
                        for line in result.translated_lines]
        except self.shape_errors:
            pass

        # An unaligned response cannot be attached to any item. Split it so one bad
        # synopsis does not discard the rest, and charge each retry to the daily quota.
        if len(texts) == 1:
            return [None]
        midpoint = len(texts) // 2
        translations = []
        for part in (texts[:midpoint], texts[midpoint:]):
            if time.monotonic() < deadline and self.reserve(len(part)):
                translations.extend(self.translate_batch(part, target, deadline))
            else:
                translations.extend([None] * len(part))
        return translations

    def translate(self, data):
        target = data.get('target_language') if isinstance(data, dict) else None
        texts = data.get('texts') if isinstance(data, dict) else None
        if (not isinstance(target, str) or not re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z0-9]{2,4}){0,2}', target)
                or not isinstance(texts, list) or not 1 <= len(texts) <= 24
                or not all(isinstance(text, str) and 0 < len(text.strip()) <= 4000 for text in texts)):
            return 400, {'error': 'Invalid translation request'}
        pending = [(index, plain_text(text)) for index, text in enumerate(texts)
                   if target != 'zh-CN' or not is_chinese(text)]
        pending = [(index, text) for index, text in pending if text]
        translations = [None] * len(texts)
        if not pending:
            return 200, {'translations': translations}
        if not self.lock.acquire(blocking=False):
            return 503, {'error': 'Translator busy'}
        try:
            if not self.reserve(len(pending)):
                return 429, {'error': 'Daily translation budget exhausted'}
            # The NAS workflow uses Sublarr's `zh` target for Simplified Chinese.
            result = self.translate_batch([text for _, text in pending], 'zh' if target == 'zh-CN' else target,
                                          time.monotonic() + 12)
            for (index, _), translated in zip(pending, result):
                translations[index] = translated
            return 200, {'translations': translations}
        except Exception:
            # Do not log the provider's response, media text, or credentials.
            return 502, {'error': 'Translation failed'}
        finally:
            self.lock.release()


def handler(bridge, token, app):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def reply(self, status, data):
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass  # Collect Metadata may have timed out and preserved the original.

        def do_POST(self):
            if self.path != '/translate':
                return self.reply(404, {'error': 'Not found'})
            supplied = self.headers.get('Authorization', '').encode('utf-8')
            if not hmac.compare_digest(supplied, token):
                return self.reply(401, {'error': 'Unauthorized'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 100_000:
                    return self.reply(413, {'error': 'Invalid body size'})
                data = json.loads(self.rfile.read(size))
            except (ValueError, OSError):
                return self.reply(400, {'error': 'Invalid JSON'})
            with app.app_context():
                status, result = bridge.translate(data)
            return self.reply(status, result)

    return Handler


def main():
    from db.models.translation import TranslationEvent
    from extensions import db
    from flask import Flask
    from sqlalchemy import URL
    from translation.concurrency import get_concurrency
    from translation.deepseek import DeepSeekBackend
    from translation.llm_base import LineCountMismatchError, LineMisalignmentError

    token = os.environ['METADATA_TRANSLATION_TOKEN'].strip()
    if not token:
        raise SystemExit('Set METADATA_TRANSLATION_TOKEN')
    db_path = os.getenv('SUBLARR_DB', '/config/sublarr.db')
    with closing(sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)) as config_db:
        row = config_db.execute("SELECT value FROM config_entries WHERE key='backend.deepseek.api_key'").fetchone()
    if not row or not row[0]:
        raise SystemExit('Configure the DeepSeek backend in Sublarr')
    get_concurrency().register('deepseek', 1)
    budget_path = os.path.abspath(os.getenv('METADATA_TRANSLATION_BUDGET_DB', '/config/collect-metadata-translation.db'))
    bridge = Bridge(DeepSeekBackend(api_key=row[0], model='deepseek-chat'), budget_path,
                    max(0, int(os.getenv('METADATA_TRANSLATION_DAILY_LIMIT', '100'))),
                    (LineCountMismatchError, LineMisalignmentError))
    # Sublarr's backend records usage through Flask-SQLAlchemy, even outside its web app.
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = URL.create('sqlite', database=budget_path)
    db.init_app(app)
    with app.app_context():
        TranslationEvent.__table__.create(db.engine, checkfirst=True)
    bind = os.getenv('METADATA_TRANSLATION_BIND', '127.0.0.1')
    port = int(os.getenv('METADATA_TRANSLATION_PORT', '7100'))
    with ThreadingHTTPServer((bind, port), handler(bridge, f'Bearer {token}'.encode('utf-8'), app)) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
