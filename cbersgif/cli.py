#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
cbersgif cli
"""

#import os

#import numpy as np

import time
import uuid

import click

#from rasterio import transform

import rasterio as rio

from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

import numpy as np

from PIL import Image, ImageDraw, ImageFont

from cbersgif import utils

#from matplotlib import cm

from cbersgif import __version__ as cbersgif_version

FONT = ImageFont.load_default()

#@click.group()
#@click.version_option(version=cbersgif_version, message='%(version)s')
#def main():
#    """
#    main
#    """
#    pass

@click.command()
@click.option('--lat', type=float, required=True,
              help='Latitude of the query, between 90 and -90.')
@click.option('--lon', type=float, required=True,
              help='Longitude of the query, between 180 and -180.')
@click.option('--path', type=int, required=True,
              help='CBERS 4 path')
@click.option('--row', type=int, required=True,
              help='CBERS 4 row')
@click.option('--sensor', type=click.Choice(['MUX', 'AWFI', 'PAN5M',
                                             'PAN10M']),
              default='MUX',
              help='Sensor')
@click.option('--level', type=click.Choice(['L2', 'L4', 'all']),
              default='L4',
              help='Levels to be used')
@click.option('--start_date', '-s', type=str, default='2013-01-01',
              help='Start date of the query in the format YYYY-MM-DD.')
@click.option('--end_date', '-e', type=str, default=time.strftime('%Y-%m-%d'),
              help='End date of the query in the format YYYY-MM-DD.')
@click.option('--res', type=int, default=20,
              help='Output Resolution')
@click.option('--bands', type=str, default='7,6,5',
              help='Comma separated list of RGB bands, in that order.')
@click.option('--buffer_size', '-b', type=int, default=10000,
              help='Buffer size around lat/lon point for image creation.'
              ' (in meters)')
@click.option('--output', '-o', type=str,
              default='./{}.gif'.format(str(uuid.uuid1())),
              help='output filename')
@click.option('--saveintermediary/--nosaveintermediary', default=False,
              help='Save intermediary files as bmp')
@click.option('--max_images', type=int, default=100,
              help='Maximum number of images to be used')
def main(lat, lon, path, row, sensor, level,
         start_date, end_date, buffer_size, res, bands,
         output, saveintermediary, max_images):
    """ Create animated GIF from CBERS 4 data"""

    rgb = bands.split(',')
    assert len(rgb) == 3, "Exactly 3 bands must be defined"

    scenes = utils.search(sensor, path, row,
                          None if level == 'all' else level)
    click.echo('{} scenes found'.format(len(scenes)))

    # Output transform
    aoi_wgs84 = utils.lonlat_to_geojson(lon, lat, buffer_size)
    aoi_bounds = utils.feat_to_bounds(aoi_wgs84) # (minx, miny, maxx, maxy)
    width = int((aoi_bounds[2] - aoi_bounds[0]) / float(res))
    height = int((aoi_bounds[3] - aoi_bounds[1]) / float(res))
    #dst_affine = transform.from_bounds(*aoi_bounds, width, height)

    s3_bucket = 'cbers-pds'

    images = []

    for scene_no, scene in enumerate(scenes):

        if scene_no >= max_images:
            break

        print(scene)
        s3_key = 's3://{bucket}/{dir}'.format(bucket=s3_bucket,
                                              dir=scene['key'])
        print(s3_key)

        out = np.zeros((3, height, width), dtype=np.uint8)

        for band_no, band in enumerate(rgb):
            # Reference
            # https://s3.amazonaws.com/cbers-pds-migration/CBERS4/MUX/
            # 063/095/CBERS_4_MUX_20180911_063_095_L2/
            # CBERS_4_MUX_20180911_063_095_L2_BAND5.tif
            band_address = '{s3_key}/{scene}_BAND{band}.tif'.\
                           format(s3_key=s3_key,
                                  scene=scene['scene_id'],
                                  band=band)
            #print(band_address)
            with rio.open(band_address) as src:
                with WarpedVRT(src,
                               crs='EPSG:3857',
                               resampling=Resampling.bilinear) as vrt:

                    window = vrt.window(*aoi_bounds)
                    # @todo need to define
                    # export AWS_REQUEST_PAYER="requester"
                    matrix = vrt.read(window=window,
                                      out_shape=(height, width), indexes=1,
                                      resampling=Resampling.bilinear)

                    p02, p98 = np.percentile(matrix[matrix > 0], (2, 98))
                    matrix = np.where(matrix > 0,
                                      utils.linear_rescale(matrix,
                                                           in_range=[int(p02),
                                                                     int(p98)],
                                                           out_range=[1, 255]),
                                      0)

                    out[band_no] = matrix.astype(np.uint8)

        img = Image.fromarray(np.dstack(out))
        draw = ImageDraw.Draw(img)
        xst, yst = draw.textsize(scene['acquisition_date'], font=FONT)
        draw.rectangle([(5, 5), (xst+15, yst+15)],
                       fill=(255, 255, 255))
        draw.text((10, 10), scene['acquisition_date'],
                  (0, 0, 0), font=FONT)
        if saveintermediary:
            img.save('{}.bmp'.format(scene_no))
        images.append(img)

    if images:
        utils.save_animated_gif(output, images, duration=0.5)

if __name__ == '__main__':
    main()
