import unittest
import media_arrival_monitor as m

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
    def test_daily_budget_reserved_before_remote_call(self):
        j = {}; saved = []
        for _ in range(10):
            m.reserve_translation(j, '2026-11-03', lambda v: saved.append(v['translation_budget']['2026-11-03']))
        self.assertEqual(saved, list(range(1, 11)))
        with self.assertRaisesRegex(ValueError, 'DAILY_OVERVIEW_TRANSLATION_LIMIT'):
            m.reserve_translation(j, '2026-11-03', lambda v: self.fail('must not save'))
        m.reserve_translation(j, '2026-11-04', lambda v: None)
        self.assertEqual(j['translation_budget']['2026-11-04'], 1)
    def test_empty_never_invents_synopsis(self):
        self.assertEqual(m.overview_action({'Type':'Episode','Overview':None},{})[0],'missing')

if __name__=='__main__':unittest.main()
