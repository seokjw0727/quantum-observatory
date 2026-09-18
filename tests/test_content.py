import unittest

from pipeline.content import load_articles,load_site_config


class EditorialContent(unittest.TestCase):
    def test_expected_editorial_collection_is_publishable(self):
        articles=load_articles()
        paper_readings=[a for a in articles if a.get('paper')]
        self.assertEqual(len(paper_readings),3)
        self.assertTrue(all(a.get('paper_ids') and any(s.get('source_indexes') for s in a['sections']) for a in paper_readings))
        self.assertIn('sorting-papers-without-ranking-quality',{a['slug'] for a in articles})
        self.assertTrue(all(a['status']=='published' for a in articles))

    def test_advertising_verification_uses_reviewed_publisher_record(self):
        site=load_site_config()
        self.assertEqual(site['ads']['mode'],'verification')
        self.assertEqual(site['ads']['publisher_id'],'pub-8724183999332964')
        self.assertEqual(site['ads']['ads_txt'],'google.com, pub-8724183999332964, DIRECT, f08c47fec0942fa0')
        self.assertEqual(site['search_console_verification_file'],'googlee349e1ba1c0c0b38.html')
        self.assertEqual(site['canonical_origin'],'https://qobservatory.com')


if __name__=='__main__':unittest.main()
