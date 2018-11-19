"""
cbersgif utils module
"""
# -*- coding: utf-8 -*-

from functools import partial
import json
import tempfile

from aws_sat_api.search import cbers

import pyproj

from shapely.ops import transform
from shapely.geometry import mapping, shape, Point

import numpy as np

import imageio

def search(sensor, path, row):
    '''
    Returns available images for sensor, path, row

    :param str sensor: Sensor ID, in ('MUX','AWFI','PAN5M','PAN10M')
    :param int path: Path number
    :param int row: Row number
    :return: Scenes
    :rtype: list
    '''
    return cbers(path, row, sensor)

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

def save_animated_gif(filename, pil_images, duration):
    '''
    Save PIL images passed in pil_images as an animated
    GIF to filename

    :param filename: output filename
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
