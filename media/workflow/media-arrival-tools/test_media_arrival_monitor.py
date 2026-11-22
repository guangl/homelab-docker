from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import media_arrival_monitor as m
import tmdb_credentials

class MonitorTests(unittest.TestCase):
    def probe(self, codec='h264', size=325984037, duration=1419.99):
        return {'streams':[{'codec_type':'video','codec_name':codec}, {'codec_type':'video','codec_name':'mjpeg','disposition':{'attached_pic':1}}], 'format':{'size':str(size),'duration':str(duration)}}
    def test_chinese_existing(self):
        p=self.probe();p['streams'].append({'codec_type':'subtitle','tags':{'language':'chi'}})
        self.assertEqual(m.subtitle_status(p,[])[0],'skipped')
    def test_unknown_subtitle_not_completed(self):
        self.assertEqual(m.subtitle_status(self.probe(),[])[0],'waiting')
    def test_sidecar_chinese(self):
        self.assertEqual(m.subtitle_status(self.probe(),['zh'])[0],'skipped')
    def test_chinese_overview_preserved(self):
        self.assertEqual(m.overview_action({'Overview':'中文简介'}, {})[0],'keep')
    def test_english_overview_translates(self):
        self.assertEqual(m.overview_action({'Overview':'English synopsis'}, {})[0],'translate')
    def test_cached_requires_matching_provider(self):
        self.assertEqual(m.overview_action({'Type':'Series','ProviderIds':{'Tmdb':'313346'}},{'313346':'中文'})[0],'cached')
        self.assertEqual(m.overview_action({'Type':'Series','ProviderIds':{'Tmdb':'other'}},{'313346':'中文'})[0],'missing')
    def test_japanese_kanji_not_treated_as_chinese(self):
        self.assertEqual(m.overview_action({'Overview':'魔法の世界を守ります'}, {})[0], 'translate')
    def test_daily_usage_is_saved_without_a_limit(self):
        j = {}; saved = []
        for _ in range(105):
            m.reserve_translation(j, '2026-11-03', lambda v: saved.append(v['translation_budget']['2026-11-03']))
        self.assertEqual(saved, list(range(1, 106)))
        m.reserve_translation(j, '2026-11-04', lambda v: None)
        self.assertEqual(j['translation_budget']['2026-11-04'], 1)
    def test_empty_never_invents_synopsis(self):
        self.assertEqual(m.overview_action({'Type':'Episode','Overview':None},{})[0],'missing')

    def test_tmdb_uses_private_v3_key(self):
        with TemporaryDirectory() as directory:
            secret = Path(directory) / 'tmdb'
            secret.write_text('a' * 32 + '\n')
            def requester(url, headers):
                self.assertEqual(parse_qs(urlsplit(url).query), {'language': ['ja'], 'api_key': ['a' * 32]})
                self.assertNotIn('Authorization', headers)
                return {'name': 'test'}

            with patch.object(tmdb_credentials, 'SECRET_FILE', secret):
                self.assertEqual(tmdb_credentials.tmdb_request('tv/1399', 'ja', requester), {'name': 'test'})

    def test_tmdb_read_token_stays_out_of_query(self):
        url, headers = tmdb_credentials.request_parts('tv/1399', 'ja', 'test.payload.signature')
        self.assertEqual(parse_qs(urlsplit(url).query), {'language': ['ja']})
        self.assertEqual(headers['Authorization'], 'Bearer test.payload.signature')

if __name__=='__main__':unittest.main()
