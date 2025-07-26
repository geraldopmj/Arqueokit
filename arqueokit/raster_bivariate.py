# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 GIS algorithms for Archaeologists
 Author: Geraldo Pereira de Morais Júnior
 Email: geraldo.pmj@gmail.com
 ***********************************************/
"""

__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-07-19'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterEnum,
    QgsRasterLayer,
    QgsSingleBandColorDataRenderer, 
    QgsMultiBandColorRenderer
)

import numpy as np
from PIL import Image, ImageDraw
import rasterio
from rasterio.warp import reproject, Resampling


class BivariateRaster(QgsProcessingAlgorithm):
    RASTER_A = 'RASTER_A'
    RASTER_B = 'RASTER_B'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
            self.addParameter(QgsProcessingParameterRasterLayer(self.RASTER_A, 'Raster A (Coluna)'))
            self.addParameter(QgsProcessingParameterRasterLayer(self.RASTER_B, 'Raster B (Linha)'))
            self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Bivariate'))

    def processAlgorithm(self, parameters, context, feedback):
        raster_a = self.parameterAsRasterLayer(parameters, self.RASTER_A, context)
        raster_b = self.parameterAsRasterLayer(parameters, self.RASTER_B, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        classes = 3
        
        # funcs
        def class_index(val, breaks):
            idx = np.searchsorted(breaks, val, side="right") - 1
            return np.clip(idx, 0, len(breaks) - 2)

        #------------------------------------------------------------
        # Raster A
        with rasterio.open(raster_a.source()) as src_a:
            arr_a = src_a.read(1, masked=True)
            meta = src_a.meta.copy()
            transform = src_a.transform
            crs = src_a.crs
            shape = arr_a.shape

        if np.all(arr_a.mask):
            raise Exception("Raster A está completamente mascarado.")

        #-----------------------------------
        # Reproject B to A
        with rasterio.open(raster_b.source()) as src_b:
            arr_b = np.zeros(shape, dtype=np.float32)
            reproject(
                source=rasterio.band(src_b, 1),
                destination=arr_b,
                src_transform=src_b.transform,
                src_crs=src_b.crs,
                dst_transform=transform,
                dst_crs=crs,
                resampling=Resampling.bilinear
            )

        arr_b = np.ma.masked_invalid(arr_b)
        valid_mask = (~arr_a.mask) & (~arr_b.mask)

        a_vals = arr_a[valid_mask]
        b_vals = arr_b[valid_mask]

        if len(a_vals) == 0 or len(b_vals) == 0:
            raise Exception("Sem valores válidos cruzados entre os dois rasters.")

        #-----------------------------------
        # Classify equal interval
        breaks_a = np.linspace(np.nanmin(a_vals), np.nanmax(a_vals), classes + 1)
        breaks_b = np.linspace(np.nanmin(b_vals), np.nanmax(b_vals), classes + 1)

        i_class = class_index(arr_a, breaks_a)
        j_class = class_index(arr_b, breaks_b)

        #-----------------------------------
        # Bands As float32
        band1 = np.full(shape, np.nan, dtype=np.float32)
        for j in range(classes):
            for i in range(classes):
                mask = (i_class == i) & (j_class == j) & valid_mask
                band1[mask] = j * classes + i + 1  # valores de 1 a 9

        #-----------------------------------
        meta.update({
            'count': 1,
            'dtype': 'float32',
            'nodata': -9999.0
        })

        #-----------------------------------
        # write TIF
        with rasterio.open(output_path, 'w', **meta) as dst:
            dst.write(np.nan_to_num(band1, nan=-9999.0), 1)
            dst.update_tags(1, BANDNAME='Bivariate')
        #-----------------------------------
        result_layer = QgsRasterLayer(output_path, 'bivariate_raster', 'gdal')
        if not result_layer.isValid():
            raise Exception("Falha ao criar o raster resultante.")
        context.temporaryLayerStore().addMapLayer(result_layer)

        return {self.OUTPUT: result_layer.id()}
        #-----------------------------------
        #-----------------------------------
        #-----------------------------------
    def name(self):
        return 'bivariate_raster'

    def displayName(self):
        return self.tr('Raster Bivariado')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Raster'

    def createInstance(self):
        return BivariateRaster()
    
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def shortHelpString(self):
        return self.tr("""Gera um raster bivariado a partir de dois rasters de entrada.
        Values:
        B2..^7  8  9
        B1..|4  5  6
        B0..|1  2  3
        .....------>
        .....A0 A1 A2""")
