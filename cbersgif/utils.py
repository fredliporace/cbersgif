"""
cbersgif utils module
"""
# -*- coding: utf-8 -*-

from functools import partial
import json
import tempfile
import hashlib
import pickle
import os

from aws_sat_api.search import cbers

import pyproj

from shapely.ops import transform
from shapely.geometry import mapping, shape, Point

import numpy as np

import imageio

import rasterio as rio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

CACHE_DIR = '/tmp/cbersgifcache/'

def search(sensor, path, row, level=None, 
           start_date='1900-01-01', end_date='9999-12-31'):
    '''
    Returns available images for sensor, path, row

    :param sensor str: Sensor ID, in ('MUX','AWFI','PAN5M','PAN10M')
    :param path int: Path number
    :param row int: Row number
    :param level str: Levels to be used, for instance, 'L2' or 'L4'.
    :param start_date str: Start date in YYYY-MM-DD format
    :param end_date str: End date in YYYY-MM-DD format
    :return: Scenes
    :rtype: list
    '''

    matches = cbers(path, row, sensor)

    s_date = start_date.replace('-', '')
    e_date = end_date.replace('-', '')
    matches[:] = [value for value in matches if \
                  value['acquisition_date'] >= s_date and
                  value['acquisition_date'] <= e_date]

    if level:
        matches[:] = [value for value in matches if \
                      value['processing_level'] == level]

    return matches

def lonlat_to_geojson(lon, lat, buff_size=None):
    '''
    Create GeoJSON feature collection from a Lat Lon center
    coordinate and an optional square buffer

    :param float lon: Longitude (WGS84, angular)
    :param float lat: Latitude (WGS84, angular)
    :param float buff_size: Buffer size in meters
    :return: GeoJSON feature collection
    '''

    geom = Point(lon, lat)

    if buff_size:
        to_web_mercator = partial(
            pyproj.transform,
            pyproj.Proj(init='epsg:4326'),
            pyproj.Proj(init='epsg:3857'))

        to_wgs84 = partial(
            pyproj.transform,
            pyproj.Proj(init='epsg:3857'),
            pyproj.Proj(init='epsg:4326'))

        point_wm = transform(to_web_mercator, geom)
        geom = point_wm.buffer(buff_size, cap_style=3)
        geom = transform(to_wgs84, geom)

    return json.dumps(mapping(geom))

def feat_to_bounds(geom, crs='epsg:3857'):
    '''
    Return bounds from a Feature Collection

    :param geom: GeoJSON Feature Collection
    :param str crs: EPSG for bounds
    :return: Bounds as list, (minx, miny, maxx, maxy)
    '''
    geom = shape(json.loads(geom))

    project = partial(
        pyproj.transform,
        pyproj.Proj(init='epsg:4326'),
        pyproj.Proj(init=crs))

    geom = transform(project, geom)

    return geom.bounds

def linear_rescale(image, in_range, out_range):
    '''
    Linear rescaling

    :param image: np array
    :param in_range list: two items, begin and end input range
    :param out_range list: two items, begin and end output range
    '''

    imin, imax = in_range
    omin, omax = out_range
    image = np.clip(image, imin, imax) - imin
    image = image / float(imax - imin)

    return image * (omax - omin) + omin

def frame_hash(input_dict):
    '''
    Builds a hash for given dictionary

    :param input_dict dict: Input for hash function, all items are considered
    :return: computed hash
    '''

    serial = pickle.dumps(sorted(input_dict.items()))
    return hashlib.md5(serial).hexdigest()

def save_animated_gif(filename, pil_images, duration):
    '''
    Save PIL images passed in pil_images as an animated
    GIF to filename

    :param filename str: output filename
    :param pil_images list: PIL Images
    :param duration float: duration for each frame in seconds
    '''

    # Currently requires saving each image as a temporary
    # file. Check better way to convert from PIL to imageio
    # format.
    # It is also possible to use PIL to write the animated GIF
    # directly, but the result was not good (dithering)? Check
    # if this may be solved by a configuration parameter. This
    # would remove the imageio dependency:
    #    pil_images[0].save('test/pil_out.gif', save_all=True,
    #                       append_images=pil_images[1:],
    #                       duration=1000,
    #                       loop=0, version='GIF89a',
    #                       dither=None)

    imageio_images = list()
    for image in pil_images:
        with tempfile.NamedTemporaryFile() as bmp_file:
            image.save(bmp_file, "BMP")
            #bmp_file.seek(0)
            imageio_images.append(imageio.imread(bmp_file.name))
    kargs = {'duration':duration}
    imageio.mimsave(filename, imageio_images, **kargs)

def get_frame_matrix(s3_key, band, scene, aoi_bounds, width, height,
                     cache=True):
    '''
    Build a image frame

    :param s3_key str: S3 prefix for scene, up to directory
    :param band list: band number
    :param scene dict: scene data as returned from CBERS search
    :param aoi_bounds list: (minx, miny, maxx, maxy)
    :param width int: image output width in pixels
    :param height int: image output height in pixels
    :param cache bool: if True the image cache is used
    '''

    hash_dict = {
        's3_key':s3_key,
        'band':band,
        'scene':scene,
        'aoi_bounds':aoi_bounds,
        'width':width,
        'height':height,
    }
    hash_hex = frame_hash(hash_dict)
    hash_file = CACHE_DIR + hash_hex + '.npy'

    if cache:
        if os.path.isfile(hash_file):
            print('Cache hit for {}, band {}'.format(scene['scene_id'], band))
            return np.load(hash_file)

    # Reference
    # https://s3.amazonaws.com/cbers-pds-migration/CBERS4/MUX/
    # 063/095/CBERS_4_MUX_20180911_063_095_L2/
    # CBERS_4_MUX_20180911_063_095_L2_BAND5.tif
    band_address = '{s3_key}/{scene}_BAND{band}.tif'.\
                   format(s3_key=s3_key,
                          scene=scene['scene_id'],
                          band=band)
    with rio.open(band_address) as src:
        with WarpedVRT(src,
                       crs='EPSG:3857',
                       resampling=Resampling.bilinear) as vrt:

            window = vrt.window(*aoi_bounds)
            # @todo need to define
            # export AWS_REQUEST_PAYER="requester"
            # reference: https://github.com/mapbox/rio-tiler/issues/52
            matrix = vrt.read(window=window,
                              out_shape=(height, width), indexes=1,
                              resampling=Resampling.bilinear)

    if cache:
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        np.save(hash_file, matrix)

    return matrix
