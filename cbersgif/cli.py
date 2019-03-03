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

import numpy as np

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from cbersgif import utils

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
#@click.option('--path', type=int, required=True,
#              help='CBERS 4 path')
#@click.option('--row', type=int, required=True,
#              help='CBERS 4 row')
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
@click.option('--singleenhancement/--nosingleenhancement', default=False,
              help='If True the same contrast stretch is performed for '
              'all scenes, this stretch is computed for the first scene')
@click.option('--enhancement/--noenhancement', default=False,
              help='If True histogram stretch is computed for scenes')
@click.option('--percentiles', type=str, default='2,98',
              help='Percentiles for upper and lower histogram enhancement')
@click.option('--contrast_factor', type=float, default=1.0,
              help='Contrast enhancement factor')
@click.option('--brightness_factor', type=float, default=1.0,
              help='Brightness enhancement factor')
@click.option('--duration', type=float, default=0.5,
              help='Duration of each frame, in seconds')
@click.option('--taboo_index', type=str, default=None,
              help='List of comma separated integers with image indices that '
              'will not be included in the timelapse')
@click.option('--stac_endpoint', '-s', type=str,
              default='https://4jp7f1hqlj.execute-api.us-east-1.amazonaws.com/'\
              'prod/stac/search',
              help='STAC search endpoint')
def main(lat, lon, 
         #path, row,
         sensor, level,
         start_date, end_date, buffer_size, res, bands,
         output, saveintermediary, max_images, singleenhancement,
         enhancement, percentiles, contrast_factor, brightness_factor,
         duration,
         taboo_index, stac_endpoint):
    """ Create animated GIF from CBERS 4 data"""

    rgb = bands.split(',')
    assert len(rgb) == 3, "Exactly 3 bands must be defined"

    percents = percentiles.split(',')
    assert len(percents) == 2, 'Two percentiles must be defined'
    p_min = int(percents[0])
    p_max = int(percents[1])

    taboo_list = list()
    if taboo_index:
        for item in taboo_index.split(','):
            taboo_list.append(int(item))

    scenes = utils.search(sensor=sensor,
                          mode='stac',
                          lon=lon, lat=lat,
                          level=None if level == 'all' else level,
                          start_date=start_date,
                          end_date=end_date,
                          stac_endpoint=stac_endpoint)
    click.echo('{} scenes found'.format(len(scenes)))

    # Output transform
    aoi_wgs84 = utils.lonlat_to_geojson(lon, lat, buffer_size)
    aoi_bounds = utils.feat_to_bounds(aoi_wgs84) # (minx, miny, maxx, maxy)
    width = int((aoi_bounds[2] - aoi_bounds[0]) / float(res))
    height = int((aoi_bounds[3] - aoi_bounds[1]) / float(res))
    #dst_affine = transform.from_bounds(*aoi_bounds, width, height)

    s3_bucket = 'cbers-pds'

    images = []

    p_min_value = [None] * 3
    p_max_value = [None] * 3

    for scene_no, scene in enumerate(scenes):

        if scene_no in taboo_list:
            print('Skipping scene {}'.format(scene_no))
            continue

        if scene_no >= max_images:
            break

        print(scene)
        s3_key = 's3://{bucket}/{dir}'.format(bucket=s3_bucket,
                                              dir=scene['key'])
        print(s3_key)

        out = np.zeros((3, height, width), dtype=np.uint8)

        for band_no, band in enumerate(rgb):

            matrix = utils.get_frame_matrix(s3_key, band, scene, aoi_bounds,
                                            width, height)

            if (scene_no == 0 or not singleenhancement) and enhancement:
                p_min_value[band_no], \
                    p_max_value[band_no] = np.\
                                           percentile(matrix[matrix > 0],
                                                      (p_min, p_max))
                print('{}, {}-{}, {}-{}'.format(band_no,
                                                p_min,
                                                p_max,
                                                p_min_value,
                                                p_max_value))

            if enhancement:
                matrix = np.where(matrix > 0,
                                  utils.\
                                  linear_rescale(matrix,
                                                 in_range=\
                                                 [int(p_min_value[band_no]),
                                                  int(p_max_value[band_no])],
                                                 out_range=[1, 255]),
                                  0)

            out[band_no] = matrix.astype(np.uint8)

        img = Image.fromarray(np.dstack(out))

        if saveintermediary:
            img.save('{}.bmp'.format(scene_no))

        contrast = ImageEnhance.Contrast(img)
        enh_image = contrast.enhance(contrast_factor)
        enh_image = ImageEnhance.Contrast(enh_image).enhance(brightness_factor)

        text_value = '%d, %s' % (scene_no,
                                 scene['acquisition_date'])
        draw = ImageDraw.Draw(enh_image)
        xst, yst = draw.textsize(text_value, font=FONT)
        draw.rectangle([(5, 5), (xst+15, yst+15)],
                       fill=(255, 255, 255))
        draw.text((10, 10), text_value,
                  (0, 0, 0), font=FONT)

        images.append(enh_image)

    if images:
        utils.save_animated_gif(output, images, duration=duration)

if __name__ == '__main__':
    main()
