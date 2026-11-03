import json
import tempfile
import unittest
from pathlib import Path
from media_notifications import Outbox, run_with_notification

class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.box = Outbox(self.tmp.name)

    def event(self):
        return self.box.enqueue('subtitle', 'completed', '/a/show.mkv', 'sha256:original', '已发布中文外挂字幕')

    def test_deduplicate_delivered_event(self):
        p = self.event()
        calls = []
        def send(payload):
            calls.append(payload)
            return {'accepted': True, 'error': None}
        self.assertTrue(self.box.deliver(p, send))
        self.assertEqual(self.event(), p)
        self.assertTrue(self.box.deliver(p, send))
        self.assertEqual(len(calls), 1)

    def test_error_does_not_mark_delivered(self):
        p = self.event()
        self.assertFalse(self.box.deliver(p, lambda _: {'accepted': True, 'error': 'SMTP_FAILED'}))
        self.assertFalse(json.loads(p.read_text())['delivered'])

    def test_network_error_keeps_pending(self):
        p = self.event()
        def fail(_): raise TimeoutError('lost acknowledgement')
        with self.assertRaises(TimeoutError): self.box.deliver(p, fail)
        self.assertFalse(json.loads(p.read_text())['delivered'])



    def test_failure_preserves_original_exception(self):
        def operation(): raise ValueError('SOURCE_CHANGED')
        with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
            run_with_notification(operation, self.box, 'subtitle', '/a.mkv', 'job1', lambda r: ('completed', 'bad'))
        events = list(Path(self.tmp.name).glob('*.json'))
        self.assertEqual(len(events), 1)
        self.assertEqual(json.loads(events[0].read_text())['state'], 'failed')

    def test_concurrent_delivery_once(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(lambda _: self.event(), range(8)))
        self.assertEqual(len(set(paths)), 1)
        calls = []
        def send(payload):
            calls.append(payload)
            return {'accepted': True, 'error': None}
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertTrue(all(pool.map(lambda _: self.box.deliver(paths[0], send), range(8))))
        self.assertEqual(len(calls), 1)
        self.event()
        self.assertTrue(json.loads(paths[0].read_text())['delivered'])


    def test_subtitle_failure_hook_no_success(self):
        import subtitle_fallback as sf
        candidate = sf.Candidate(language='en', location='embedded', subtitle_type='text', format='ass', coverage='full', episode_id='ep', source_path='/missing.mkv', source_exists=True, stream_index=2)
        with self.assertRaises(Exception):
            sf.translate_and_publish(candidate, 'ep', str(Path(self.tmp.name) / 'show.zh.srt'), lambda _: b'', object(), notification_outbox=self.box, notification_generation='source-sha')
        event = json.loads(next(Path(self.tmp.name).glob('*.json')).read_text())
        self.assertEqual(event['state'], 'failed')

    def test_invalid_event_rejected(self):
        with self.assertRaises(ValueError): self.box.enqueue('download', 'success', '/a', '', '')

    def test_no_temporary_artifacts(self):
        self.event()
        self.assertFalse(list(Path(self.tmp.name).glob('.notify-*')))

if __name__ == '__main__': unittest.main()
