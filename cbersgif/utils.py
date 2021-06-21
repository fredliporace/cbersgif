"""cbersgif utils module."""
# -*- coding: utf-8 -*-

import hashlib
import json
import os
import pickle
import re
import tempfile
from functools import partial
from typing import List

import imageio
import numpy as np
import pyproj
import rasterio as rio
from aws_sat_api.search import cbers
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform

from cbersgif.search import StacSearch

CACHE_DIR = "/tmp/cbersgifcache/"


def stac_to_aws_sat_api(stac_id: str):
    """Build awd_sat_api scene from stac_id.

    Args:
    stac_id: stac item id

    Returns:
    aws_sat_api scene id, required keys: key, acquisition_date, scene_id
    """
    match = re.match(
        r"CBERS_(?P<sat>\d)_(?P<cam>\w+)_(?P<date>\d+)_"
        r"(?P<path>\d{3})_(?P<row>\d{3})_L(?P<level>\d{1})",
        stac_id,
    )
    assert match, "Can't match {}".format(stac_id)
    scene = dict()
    scene["key"] = (
        "CBERS{sat}/{sensor}/{path}/{row}/CBERS_{sat}_{sensor}_"
        "{date}_{path}_{row}_"
        "L{level}".format(
            sat=match.group("sat"),
            sensor=match.group("cam"),
            path=match.group("path"),
            row=match.group("row"),
            level=match.group("level"),
            date=match.group("date"),
        )
    )
    scene["acquisition_date"] = match.group("date")
    scene["scene_id"] = stac_id
    return scene


def search(**kwargs):
    """Return available images for parameters.

    Parameters are:
       sensor, level, start_date, end_date for both modes.
       path, row for 'aws_sat_api' mode.
       lat, lon for 'stac' mode. stac_endpoint is mandatory for this mode

    Args:
    mode str: 'aws_sat_api' or 'stac'
    sensor str: Sensor ID, in ('MUX','AWFI','PAN5M','PAN10M')
    path int: Path number
    row int: Row number
    level str: Levels to be used, for instance, 'L2' or 'L4'.
    start_date str: Start date in YYYY-MM-DD format
    end_date str: End date in YYYY-MM-DD format

    Returns:
    Scenes list
    """
    mode = "aws_sat_api" if not kwargs.get("mode") else kwargs["mode"]

    assert mode in ("aws_sat_api", "stac"), "Invalid search mode: {}".format(mode)

    start_date = "1900-01-01" if not kwargs.get("start_date") else kwargs["start_date"]
    end_date = "9999-12-31" if not kwargs.get("end_date") else kwargs["end_date"]
    level = kwargs.get("level")

    if mode == "aws_sat_api":

        matches = cbers(kwargs["path"], kwargs["row"], kwargs["sensor"])

        s_date = start_date.replace("-", "")
        e_date = end_date.replace("-", "")
        matches[:] = [
            value
            for value in matches
            if value["acquisition_date"] >= s_date
            and value["acquisition_date"] <= e_date
        ]

        if level:
            matches[:] = [
                value for value in matches if value["processing_level"] == level
            ]

    else:

        ss1 = StacSearch(kwargs["stac_endpoint"])
        bbox = [kwargs["lon"], kwargs["lat"], kwargs["lon"], kwargs["lat"]]
        ids = ss1.search(
            instrument=kwargs["sensor"],
            start_date=start_date,
            end_date=end_date,
            level=level,
            bbox=bbox,
            limit=300,
        )
        matches = list()
        for sid in ids:
            matches.append(stac_to_aws_sat_api(stac_id=sid["id"]))
        matches = sorted(matches, key=lambda k: k["acquisition_date"])

    # Remove duplicate acquisition dates
    seen = set()
    seen_add = seen.add
    filtered_matches = [
        x
        for x in matches
        if not (x["acquisition_date"] in seen or seen_add(x["acquisition_date"]))
    ]

    return filtered_matches


def lonlat_to_geojson(lon: float, lat: float, buff_size: float = None):
    """Create GeoJSON feature collection from a Lat Lon center and buffer.

    Coordinate as center coordinate, optional square buffer.

    Args:
    lon: Longitude (WGS84, angular)
    lat: Latitude (WGS84, angular)
    buff_size: Buffer size in meters

    Returns:
    GeoJSON feature collection
    """
    geom = Point(lon, lat)

    if buff_size:
        to_web_mercator = partial(
            pyproj.transform,
            pyproj.Proj(init="epsg:4326"),
            pyproj.Proj(init="epsg:3857"),
        )

        to_wgs84 = partial(
            pyproj.transform,
            pyproj.Proj(init="epsg:3857"),
            pyproj.Proj(init="epsg:4326"),
        )

        point_wm = transform(to_web_mercator, geom)
        geom = point_wm.buffer(buff_size, cap_style=3)
        geom = transform(to_wgs84, geom)

    return json.dumps(mapping(geom))


def feat_to_bounds(geom, crs: str = "epsg:3857") -> List[int]:
    """Return bounds from a Feature Collection.

    Args:
    geom: GeoJSON Feature Collection
    crs: EPSG for bounds

    Returns:
    Bounds as list, (minx, miny, maxx, maxy)
    """
    geom = shape(json.loads(geom))

    project = partial(
        pyproj.transform, pyproj.Proj(init="epsg:4326"), pyproj.Proj(init=crs)
    )

    geom = transform(project, geom)

    return geom.bounds


def linear_rescale(image, in_range, out_range):
    """Linear rescaling.

    Args:
    image: np array
    in_range: list two items, begin and end input range
    out_range: list two items, begin and end output range
    """
    imin, imax = in_range
    omin, omax = out_range
    image = np.clip(image, imin, imax) - imin
    image = image / float(imax - imin)

    return image * (omax - omin) + omin


def frame_hash(input_dict):
    """Builds a hash for given dictionary.

    Args:
    input_dict dict: Input for hash function, all items are considered

    Returns:
    computed hash
    """
    serial = pickle.dumps(sorted(input_dict.items()))
    return hashlib.md5(serial).hexdigest()


def save_animated_gif(filename: str, pil_images, duration: float):
    """Save PIL images passed in pil_images as an animated GIF.

    Args:
    filename:  output filename
    pil_images: list of PIL Images
    duration: duration for each frame in seconds
    """
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
            # bmp_file.seek(0)
            imageio_images.append(imageio.imread(bmp_file.name))
    kargs = {"duration": duration}
    imageio.mimsave(filename, imageio_images, **kargs)


def get_frame_matrix(  # pylint: disable=too-many-arguments
    s3_key: str, band, scene, aoi_bounds, width: int, height: int, cache: bool = True,
):
    """Build a image frame.

    Args:
    s3_key: S3 prefix for scene, up to directory
    band:  list, band number
    scene: dict, scene data as returned from CBERS search
    aoi_bounds: list, (minx, miny, maxx, maxy)
    width: image output width in pixels
    height: image output height in pixels
    cache: if True the image cache is used
    """
    hash_dict = {
        "s3_key": s3_key,
        "band": band,
        "scene": scene,
        "aoi_bounds": aoi_bounds,
        "width": width,
        "height": height,
    }
    hash_hex = frame_hash(hash_dict)
    hash_file = CACHE_DIR + hash_hex + ".npy"

    if cache:
        if os.path.isfile(hash_file):
            print("Cache hit for {}, band {}".format(scene["scene_id"], band))
            return np.load(hash_file)

    # Reference
    # https://s3.amazonaws.com/cbers-pds-migration/CBERS4/MUX/
    # 063/095/CBERS_4_MUX_20180911_063_095_L2/
    # CBERS_4_MUX_20180911_063_095_L2_BAND5.tif
    band_address = "{s3_key}/{scene}_BAND{band}.tif".format(
        s3_key=s3_key, scene=scene["scene_id"], band=band
    )
    with rio.open(band_address) as src:
        with WarpedVRT(src, crs="EPSG:3857", resampling=Resampling.bilinear) as vrt:

            window = vrt.window(*aoi_bounds)
            # @todo need to define
            # export AWS_REQUEST_PAYER=requester
            # reference: https://github.com/mapbox/rio-tiler/issues/52
            matrix = vrt.read(
                window=window,
                out_shape=(height, width),
                indexes=1,
                resampling=Resampling.bilinear,
            )

    if cache:
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        np.save(hash_file, matrix)

    return matrix
