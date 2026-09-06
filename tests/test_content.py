import unittest

from pipeline.content import load_articles,load_site_config


class EditorialContent(unittest.TestCase):
    def test_expected_editorial_collection_is_publishable(self):
        articles=load_articles()
        self.assertEqual(len(articles),10)
        self.assertEqual(sum(a['type']=='analysis' for a in articles),4)
        self.assertEqual(sum(a['type']=='guide' for a in articles),6)
        self.assertTrue(all(a['status']=='published' for a in articles))

    def test_advertising_verification_uses_reviewed_publisher_record(self):
        site=load_site_config()
        self.assertEqual(site['ads']['mode'],'verification')
        self.assertEqual(site['ads']['publisher_id'],'pub-8724183999332964')
        self.assertEqual(site['ads']['ads_txt'],'google.com, pub-8724183999332964, DIRECT, f08c47fec0942fa0')
        self.assertEqual(site['canonical_origin'],'https://qobservatory.com')


if __name__=='__main__':unittest.main()
