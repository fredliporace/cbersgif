"""utils_test.py"""

import unittest
import difflib
import contextlib
import os

from PIL import Image

from cbersgif.utils import search, lonlat_to_geojson, \
    feat_to_bounds, save_animated_gif

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

    def search_test(self):
        """search_test"""

        result = search('MUX', 100, 100)
        self.assertTrue(len(result) >= 4)

        result = search('AWFI', 100, 99)
        self.assertTrue(len(result) >= 3)

        result = search('PAN10M', 100, 100)
        self.assertTrue(len(result) >= 2)

        result = search('PAN5M', 100, 100)
        self.assertTrue(len(result) >= 3)

    def search_test_wit_level(self):
        """search_test_with_level"""

        result = search('MUX', 100, 100, 'L4')
        self.assertTrue(len(result) >= 0)

        result = search('MUX', 100, 100, 'L2')
        self.assertTrue(len(result) >= 4)

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

if __name__ == '__main__':
    unittest.main()
