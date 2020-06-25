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
#import fiona
#import folium
#import gdal


s2_api = SentinelAPI(
    user=os.environ.get('copernicus_username') or input('Username: '),
    password=os.environ.get('copernicus_password') or input('Password: '),
    api_url='https://scihub.copernicus.eu/apihub/')

# make sure Download folder is empty !!!!

# dir_download = '/Users/sarinnhek/PycharmProjects/FF/download/'
# dir_download = 'D:/NMBU/FutureFarm/download_245/'
dir_download = '../download/'

dir_save = '/Users/sarinnhek/PycharmProjects/FF/save/'

# dir_ROI      = '/Users/sarinnhek/PycharmProjects/FF/ROI/'
# dir_ROI = 'D:/NMBU/FutureFarm/2-4-5/2-4-5/'
dir_ROI = '../../ROI/2-4-5/'

dirSub_ROI = [f for f in os.listdir(dir_ROI) if not f.startswith('.')]

# ******** Randomly choose time range???
# .... BETWEEN APRIL AND AUGUST
date_first = '20190621'
# date_last  = '20190629'
date_last = '20190625'

#### read shapefiles into regions of interest ####
init = True
for F in dirSub_ROI:
    print(F)
    files_ = os.listdir(dir_ROI + F)
    files_ROI = []
    # Traverse and search for .shp files
    for names in files_:
        if names.endswith('shp'):
            files_ROI.append(names)

    # Read .shp files
    for f in files_ROI:
        if init:
            poly_shp_file = dir_ROI + F + '/' + f
            roi = gpd.read_file(poly_shp_file)
            init = False
        # else:
        #     poly_shp_file = dir_ROI + F + '/' + f
        #     roi = roi.append(gpd.read_file(poly_shp_file), ignore_index=True)

df_farm = pd.DataFrame()

# bounding box around all regions of interest
bx = min(roi.bounds['minx'])
by = min(roi.bounds['miny'])
upx = max(roi.bounds['maxx'])
upy = max(roi.bounds['maxy'])
footprint = Polygon([(bx, by), (bx, upy), (upx, upy), (upx, by)])
# *************** Will the footprint decide the size of taken images????

############# Loop on dates and download satellite images ##########

# ****** Date to yyyymmdd, one by one
date_last = datetime.strptime(date_last, '%Y%m%d')
date_s = datetime.strptime(date_first, '%Y%m%d')
date_start = date_s.strftime('%Y%m%d')

count = 0

while date_s < date_last:
    date_e = date_s + timedelta(days=1)
    date_end = date_e.strftime('%Y%m%d')
    print((date_start, date_end))
    # Taken from the documentation of sentinelsat???
    # https://scihub.copernicus.eu/userguide/FullTextSearch#Search_Keywords
    products = s2_api.query(footprint, producttype='S2MSI1C', date=(
        date_start, date_end), platformname='Sentinel-2')
    print('#products', len(products))
    if products != {}:
        s2_api.download_all(products, directory_path=dir_download)

        ########## Extract all zip files between date_start and date_end and delete zip files##########
        files_ = [f for f in os.listdir(dir_download) if not f.startswith('.')]
        for f in files_:
            with zipfile.ZipFile(dir_download + f, 'r') as zip_ref:
                zip_ref.extractall(dir_download)
            os.remove(dir_download + f)
        ##########################################################################################

        # get file names for d in dirSub_download:
        dirSub_download = [f for f in os.listdir(
            dir_download) if not f.startswith('.')]

        # ***** Read the .jp2 images
        df = pd.DataFrame(
            columns=['farm', 'date', 'band', 'dim_img', 'img', 'img_r', 'area'])
        for d in dirSub_download:
            # d = dirSub_download[1]
            dir_imgdata = dir_download + d + '/GRANULE/'
            tmp = [f for f in os.listdir(dir_imgdata) if not f.startswith('.')]
            dir_imgdata = dir_imgdata + tmp[0] + '/IMG_DATA/'

            f = [f for f in os.listdir(dir_imgdata) if not f.startswith('.')]
            f.sort()
            ########## Apply ROI to all images ##########
            for img_name in f:
                print(img_name)
                with rasterio.open(dir_imgdata + img_name, driver='JP2OpenJPEG') as src:
                    print('src', src.crs, ' ,   roi', roi.crs)
                    roi = roi.to_crs(epsg=int(src.crs.to_string()[5:]))
                    out_image, out_transform = rasterio.mask.mask(
                        src, roi.geometry, crop=True)
                    out_meta = src.meta.copy()
                    out_meta.update({"driver": "JP2OpenJPEG",
                                     "height": out_image.shape[1],
                                     "width": out_image.shape[2],
                                     "transform": out_transform})

                    # meta data
                    df = df.append({'farm': 'farm1',  # farm_name or 'AUTO',
                                    'date': img_name[7:15],
                                    'band': img_name[23:26],
                                    'dim_img': out_image.shape,
                                    'img': out_image,
                                    'area': sum(out_image.flatten() != 0)
                                    }, ignore_index=True)

        # area for sorting? Why need sorting??
        ind = df.sort_values(by=['band', 'area'], ascending=False)[
            ['band']].drop_duplicates().index
        df = df.loc[np.sort(ind)]
        df = df.drop(columns=['area'])
        print('df drop area ok')

        # *** standard size for all band???
        dim_up = df['dim_img'][df['band'] == 'B02'].iloc[0]

        # img_r = resized img
        # CHANGE LATER to make either img_r be dim CxVxH or img to be dim VxHxC
        # for now img_r is VxHxC and img the original CxVxH
        for i in df.index:
            # *** Can we use bilinear here??
            df['img_r'][i] = cv2.resize(df['img'][i][0, :, :], (
                dim_up[2], dim_up[1]), interpolation=cv2.INTER_NEAREST)  # Why not bilinear

        # remove directory d
        for d in dirSub_download:
            shutil.rmtree(dir_download + d)

        df_farm = df_farm.append(df)
        del df

    date_s = date_e
    date_start = date_s.strftime('%Y%m%d')
    count = count + 1
    print(count, ' : ', date_start)

##########################################################
df_farm = df_farm.sort_values(by=['date', 'band'])
df_farm = df_farm.reset_index()
df_farm = df_farm.drop('index', axis=1)


def to_tensor(df, img, modes):
    sz = df[img].iloc[0].shape
    numel = np.size(df[img].iloc[0])

    if modes == '':
        N = df.shape[0]
    else:
        N = []
        for m in modes:
            N.append(len(df[m].unique()))

    dim = np.append(N, sz).astype(int)
    Nrows = np.prod(N)

    tl_X = np.zeros((Nrows, numel))
    im_1d = df[img].apply(lambda x: x.reshape(numel))

    for i in range(0, Nrows):
        tl_X[i] = im_1d.iloc[i]

    tl_X = tl_X.reshape(dim)
    return tl_X
