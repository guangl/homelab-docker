"""Durable stage outcome outbox; no automatic scheduler or credentials embedded.
Delivery is at-least-once: an HTTP acknowledgement lost after send can duplicate a
message. Notification errors never rerun or undo successful media publication.
"""
import hashlib
import fcntl
from contextlib import contextmanager
import json
import os
import tempfile
import urllib.request
from pathlib import Path

LABELS = {'subtitle': '字幕'}
STATES = {'completed': '完成', 'skipped': '跳过', 'waiting': '等待', 'failed': '失败'}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.notify-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, str(path))
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Outbox:
    def __init__(self, root):
        self.root = Path(root)

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / '.outbox.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def enqueue(self, stage, state, source, generation, detail):
        with self.locked():
            return self._enqueue(stage, state, source, generation, detail)

    def _enqueue(self, stage, state, source, generation, detail):
        if stage not in LABELS or state not in STATES or not generation:
            raise ValueError('INVALID_STAGE_EVENT')
        identity = json.dumps([stage, state, source, generation], ensure_ascii=False)
        key = hashlib.sha256(identity.encode()).hexdigest()
        path = self.root / (key + '.json')
        if path.exists():
            return path
        title = '[NAS][{}][{}] {}'.format(LABELS[stage], STATES[state], Path(source).stem)
        atomic_json(path, {'id': key, 'stage': stage, 'state': state,
                           'source': source, 'generation': generation,
                           'payload': {'title': title, 'body': detail,
                                       'tag': 'email', 'type': 'failure' if state == 'failed' else 'info'},
                           'delivered': False})
        return path

    def deliver(self, path, sender):
        with self.locked():
            return self._deliver(path, sender)

    def _deliver(self, path, sender):
        event = json.loads(Path(path).read_text())
        if event['delivered']:
            return True
        # A HTTP200 with provider error is NOT a successful delivery.
        response = sender(event['payload'])
        if response.get('error') or not response.get('accepted'):
            return False
        event['delivered'] = True
        atomic_json(path, event)
        return True


def http_sender(url, headers):
    def send(payload):
        request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(),
                                         headers=dict(headers, **{'Content-Type': 'application/json'}))
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read())
            return {'accepted': response.status == 200, 'error': body.get('error')}
    return send




def run_with_notification(operation, outbox, stage, source, generation, classify):
    try:
        result = operation()
    except Exception as exc:
        try:
            outbox.enqueue(stage, 'failed', source, generation, type(exc).__name__)
        except Exception:
            pass
        raise
    try:
        state, detail = classify(result)
        outbox.enqueue(stage, state, source, generation, detail)
    except Exception as exc:
        # Record failure separately, not as media job failure after commit.
        import warnings
        warnings.warn('NOTIFICATION_QUEUE_FAILED:' + type(exc).__name__)
    return result
