"""utils_test.py"""

import math

import difflib
import contextlib
import os

from PIL import Image

from cbersgif.utils import search, lonlat_to_geojson, \
    feat_to_bounds, save_animated_gif, frame_hash, \
    stac_to_aws_sat_api

STAC_ENDPOINT = 'https://stac.amskepler.com/v100/search'

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

def test_stac_to_aws_sat_api():
    """stac_to_aws_sat_api_test"""

    scene = stac_to_aws_sat_api(stac_id='CBERS_4_PAN5M_20181231_'
                                '156_107_L2')
    assert scene['key'] == \
                     'CBERS4/PAN5M/156/107/CBERS_4_PAN5M_20181231_'\
                     '156_107_L2'
    assert scene['acquisition_date'] == '20181231'

def test_search():
    """search_test"""

    result = search(sensor='MUX', path=100, row=100)
    assert len(result) >= 4

    result = search(sensor='AWFI', path=100, row=99)
    assert len(result) >= 3

    result = search(sensor='PAN10M', path=100, row=100)
    assert len(result) >= 2

    result = search(sensor='PAN5M', path=100, row=100)
    assert len(result) >= 3

def test_search_with_level():
    """search_with_level_test"""

    result = search(sensor='MUX', path=100, row=100, level='L4')
    assert len(result) >= 0

    result = search(sensor='MUX', path=100, row=100, level='L2')
    assert len(result) >= 4

def test_search_stac_mode():
    """search_stac_mode_test"""

    rio_lon = -43.1729
    rio_lat = -22.9068
    result = search(sensor='MUX',
                    lon=rio_lon, lat=rio_lat,
                    mode='stac', stac_endpoint=STAC_ENDPOINT,
                    level='L2')
    assert len(result) >= 4
    assert result[0]['key'] == \
                     'CBERS4/MUX/151/126/CBERS_4_MUX_20150215_151_126_L2'
    assert result[0]['acquisition_date'] == '20150215'

def test_search_date():
    """search_date_test"""

    result = search(sensor='MUX', path=100, row=100)
    assert len(result) >= 4
    result = search(sensor='MUX', path=100, row=100,
                    start_date='2015-11-01',
                    end_date='2018-09-29')
    assert len(result) == 2
    assert result[0]['acquisition_date'] == '20180306'
    assert result[1]['acquisition_date'] == '20180427'


def test_search_remove_dupes():
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
        assert result[index]['acquisition_date'] != \
        result[index+1]['acquisition_date']


def test_lonlat_to_geojson():
    """lonlat_to_geojson_test"""

    result = lonlat_to_geojson(-43.182365, -22.970722, 1000)
    with open('tests/copacabana.json', 'w') as fp_out:
        fp_out.write(result)
    res = diff_files('tests/copacabana.json',
                     'tests/ref_copacabana.json')
    assert len(res) == 0, res

    result = lonlat_to_geojson(-43.182365, -22.970722, 10000)
    with open('tests/copacabana_10000.json', 'w') as fp_out:
        fp_out.write(result)
    res = diff_files('tests/copacabana_10000.json',
                     'tests/ref_copacabana_10000.json')
    assert len(res) == 0, res

def test_feat_to_bounds():
    """feat_to_bounds_test"""

    bounds = feat_to_bounds(lonlat_to_geojson(-43.182365,
                                              -22.970722, 10000))
    assert all(math.isclose(l_1, l_2, abs_tol=0.0002) for l_1, l_2 in zip(bounds, (-4817038.8830492785,
                      -2638478.3425390865,
                      -4797038.883049279,
                      -2618478.3425390865)))

def test_save_animated_gif():
    """save_animated_gif_test"""

    output_filename = 'tests/animated.gif'

    with contextlib.suppress(FileNotFoundError):
        os.remove(output_filename)

    pil_images = []
    for index in range(4):
        pil_img = Image.open('tests/{}.bmp'.format(index))
        pil_images.append(pil_img)

    save_animated_gif(output_filename, pil_images, 0.5)

    # Only checks if file is generated, not sure if a binary
    # diff would work on distinct machines/lib versions
    assert os.path.exists(output_filename)

def test_frame_hash():
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
    assert hash_result_1 == hash_result_2
    # Distinct hashes for distinct contents
    assert hash_result_1 != hash_result_3
    # Absolute hash value should always be the same
    assert hash_result_1 == 'bbee5d39ea2defeb39a2075e9c3875a4'
