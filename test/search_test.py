"""search_test.py"""

import unittest
from cbersgif.search import StacSearch
from cbersgif.utils import lonlat_to_geojson, feat_to_bounds

STAC_ENDPOINT = 'https://4jp7f1hqlj.execute-api.us-east-1.amazonaws.com/'\
                'prod/stac/search'

class SearchTest(unittest.TestCase):
    """SearchTest"""

    def test_if_online(self):
        """test_if_online"""

        ss1 = StacSearch(STAC_ENDPOINT)
        self.assertTrue(ss1.is_online())

    def test_search(self):
        """test_search"""

        ss1 = StacSearch(STAC_ENDPOINT)

        rio_lon = -43.1729
        rio_lat = -22.9068
        bbox = [rio_lon, rio_lat, rio_lon, rio_lat]

        # Search Point
        ids = ss1.search(instrument='AWFI',
                         start_date='2014-01-01',
                         end_date='2015-01-30',
                         level="L2",
                         bbox=bbox,
                         limit=300)
        #print(ids)
        self.assertEqual(len(ids), 12)

if __name__ == '__main__':
    unittest.main()
