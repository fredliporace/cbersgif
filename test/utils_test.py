"""utils_test.py"""

import unittest
import difflib
import contextlib
import os

from PIL import Image

from cbersgif.utils import search, lonlat_to_geojson, \
    feat_to_bounds, save_animated_gif, frame_hash, \
    stac_to_aws_sat_api

STAC_ENDPOINT = 'https://stac.amskepler.com/v07/stac/search'

def diff_files(filename1, filename2):
    """
    Return string with context diff, empty if files are equal
    """
    with open(filename1) as file1:
        with open(filename2) as file2:
            diff = difflib.context_diff(file1.readlines(), file2.readlines())
    res = ''
    for line in diff:
        res += line
    return res

class UtilsTest(unittest.TestCase):
    """UtilsTest"""

    def stac_to_aws_sat_api_test(self):
        """stac_to_aws_sat_api_test"""

        scene = stac_to_aws_sat_api(stac_id='CBERS_4_PAN5M_20181231_'
                                    '156_107_L2')
        self.assertEqual(scene['key'],
                         'CBERS4/PAN5M/156/107/CBERS_4_PAN5M_20181231_'
                         '156_107_L2')
        self.assertEqual(scene['acquisition_date'], '20181231')

    def search_test(self):
        """search_test"""

        result = search(sensor='MUX', path=100, row=100)
        self.assertTrue(len(result) >= 4)

        result = search(sensor='AWFI', path=100, row=99)
        self.assertTrue(len(result) >= 3)

        result = search(sensor='PAN10M', path=100, row=100)
        self.assertTrue(len(result) >= 2)

        result = search(sensor='PAN5M', path=100, row=100)
        self.assertTrue(len(result) >= 3)

    def search_with_level_test(self):
        """search_with_level_test"""

        result = search(sensor='MUX', path=100, row=100, level='L4')
        self.assertTrue(len(result) >= 0)

        result = search(sensor='MUX', path=100, row=100, level='L2')
        self.assertTrue(len(result) >= 4)

    def search_stac_mode_test(self):
        """search_stac_mode_test"""

        rio_lon = -43.1729
        rio_lat = -22.9068
        result = search(sensor='MUX',
                        lon=rio_lon, lat=rio_lat,
                        mode='stac', stac_endpoint=STAC_ENDPOINT,
                        level='L2')
        self.assertTrue(len(result) >= 4)
        self.assertEqual(result[0]['key'],
                         'CBERS4/MUX/151/126/CBERS_4_MUX_20150215_151_126_L2')
        self.assertEqual(result[0]['acquisition_date'], '20150215')

    def search_date_test(self):
        """search_date_test"""

        result = search(sensor='MUX', path=100, row=100)
        self.assertTrue(len(result) >= 4)
        result = search(sensor='MUX', path=100, row=100,
                        start_date='2015-11-01',
                        end_date='2018-09-29')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['acquisition_date'], '20180306')
        self.assertEqual(result[1]['acquisition_date'], '20180427')


    def search_remove_dupes_test(self):
        """search_remove_dupes_test"""

        lon = -53.3175
        lat = -6.40133
        result = search(sensor='AWFI',
                        lon=lon, lat=lat,
                        mode='stac', stac_endpoint=STAC_ENDPOINT,
                        start_date='2015-11-01',
                        end_date='2015-12-31',
                        level='L4')
        for index in range(0, len(result)-1):
            self.assertNotEqual(result[index]['acquisition_date'],
                                result[index+1]['acquisition_date'])


    def lonlat_to_geojson_test(self):
        """lonlat_to_geojson_test"""

        result = lonlat_to_geojson(-43.182365, -22.970722, 1000)
        with open('test/copacabana.json', 'w') as fp_out:
            fp_out.write(result)
        res = diff_files('test/copacabana.json',
                         'test/ref_copacabana.json')
        self.assertEqual(len(res), 0, res)

        result = lonlat_to_geojson(-43.182365, -22.970722, 10000)
        with open('test/copacabana_10000.json', 'w') as fp_out:
            fp_out.write(result)
        res = diff_files('test/copacabana_10000.json',
                         'test/ref_copacabana_10000.json')
        self.assertEqual(len(res), 0, res)

    def feat_to_bounds_test(self):
        """feat_to_bounds_test"""

        bounds = feat_to_bounds(lonlat_to_geojson(-43.182365,
                                                  -22.970722, 10000))
        self.assertEqual(bounds, (-4817038.8830492785,
                                  -2638478.3425390865,
                                  -4797038.883049279,
                                  -2618478.3425390865))

    def save_animated_gif_test(self):
        """save_animated_gif_test"""

        output_filename = 'test/animated.gif'

        with contextlib.suppress(FileNotFoundError):
            os.remove(output_filename)

        pil_images = []
        for index in range(4):
            pil_img = Image.open('test/{}.bmp'.format(index))
            pil_images.append(pil_img)

        save_animated_gif(output_filename, pil_images, 0.5)

        # Only checks if file is generated, not sure if a binary
        # diff would work on distinct machines/lib versions
        self.assertTrue(os.path.exists(output_filename))

    def frame_hash(self):
        """frame_hash_test"""

        example = {
            's3_key': 'CBERS4/MUX/167/114/CBERS_4_MUX_20180911_167_114_L4',
            'bands': '7,6,5'
        }
        hash_result_1 = frame_hash(example)
        example = {
            'bands': '7,6,5',
            's3_key': 'CBERS4/MUX/167/114/CBERS_4_MUX_20180911_167_114_L4'
        }
        hash_result_2 = frame_hash(example)
        example = {
            'bands': '7,6,4',
            's3_key': 'CBERS4/MUX/167/114/CBERS_4_MUX_20180911_167_114_L4'
        }
        hash_result_3 = frame_hash(example)
        # Should not depend on dict order
        self.assertEqual(hash_result_1, hash_result_2)
        # Distinct hashes for distinct contents
        self.assertNotEqual(hash_result_1, hash_result_3)
        # Absolute hash value should always be the same
        self.assertEqual(hash_result_1, 'bbee5d39ea2defeb39a2075e9c3875a4')

if __name__ == '__main__':
    unittest.main()
