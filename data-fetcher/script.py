import os
import zipfile
import shutil
from datetime import datetime, timedelta
import numpy as np
import matplotlib.pyplot as plt
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio import plot
import rasterio.mask
from rasterio.enums import Resampling
import cv2
from shapely.geometry import Polygon


def setup_api():
    username = os.environ.get('copernicus_username') or input('Username: ')
    password = os.environ.get('copernicus_password') or input('Password: ')

    s2_api = SentinelAPI(
        user=username,
        password=password,
        api_url='https://scihub.copernicus.eu/apihub/')

    return s2_api


def get_shape_files(folder='./'):
    shape_files = []
    for item in os.listdir(folder):
        subpath = os.path.join(folder, item)
        if os.path.isdir(subpath):
            # pass
            shp_files = [os.path.join(subpath, file_name)
                         for file_name in os.listdir(subpath)
                         if file_name.endswith('.shp')]
            shape_files.extend(shp_files)
        elif item.endswith('.shp'):
            shape_files.append(os.path.join(folder, item))

    return shape_files


def get_ROI(shape_files, mode='all'):
    """
    get ROI from shape files

    :param shape_files: path to shape file
    :type shape_files: str
    :param mode: defaults to 'all'. Others: 'alone'
    :type mode: str, optional
    """
    if mode == 'all':
        roi = None
        for shp_file in shape_files:
            if roi is None:
                roi = gpd.read_file(shp_file)
            else:
                roi.append(gpd.read_file(shp_file), ignore_index=True)
    else:
        roi = []
        for shp_file in shape_files:
            roi.append(gpd.read_file(shp_file))

    return roi


def _bounding_box_roi(roi):
    bx, by = min(roi.bounds['minx']), min(roi.bounds['miny'])
    upx, upy = max(roi.bounds['maxx']), max(roi.bounds['maxy'])

    return Polygon([(bx, by), (bx, upy), (upx, upy), (upx, by)])


def get_footprint(roi):
    if type(roi) is list:
        footprints = []
        for item in roi:
            footprints.append(_bounding_box_roi(item))

        return footprints

    else:
        return _bounding_box_roi(roi)


def footprint_from_shp(shape_files, mode='all'):
    roi = get_ROI(shape_files, mode)

    return get_footprint(roi)


if __name__ == '__main__':
    s2_api = setup_api()

    dir_download = '../download/'
    dir_ROI = '../../ROI/'

    shape_files = get_shape_files(dir_ROI+'2-4-5')
    footprint = footprint_from_shp(shape_files, mode='alone')

    date_first = '20190621'
    date_last = '20190629'

    date_start = '20190621'
    date_end = '20190623'

    for fp in footprint:
        products = s2_api.query(fp,
                                producttype='S2MSI1C',
                                date=(date_start, date_end),
                                platformname='Sentinel-2')
        print('#products', len(products))
