"""
cbersgif utils module
"""
# -*- coding: utf-8 -*-

from functools import partial
import json

from aws_sat_api.search import cbers

import pyproj

from shapely.ops import transform
from shapely.geometry import mapping, shape, Point

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
