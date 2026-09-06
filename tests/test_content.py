import unittest

from pipeline.content import load_articles,load_site_config


class EditorialContent(unittest.TestCase):
    def test_expected_editorial_collection_is_publishable(self):
        articles=load_articles()
        self.assertEqual(len(articles),10)
        self.assertEqual(sum(a['type']=='analysis' for a in articles),4)
        self.assertEqual(sum(a['type']=='guide' for a in articles),6)
        self.assertTrue(all(a['status']=='published' for a in articles))

    def test_advertising_stays_off_without_real_publisher_id(self):
        site=load_site_config()
        self.assertEqual(site['ads']['mode'],'off')
        self.assertIsNone(site['ads']['publisher_id'])
        self.assertEqual(site['canonical_origin'],'https://qobservatory.com')


if __name__=='__main__':unittest.main()
