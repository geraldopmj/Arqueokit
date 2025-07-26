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


class BivariateRasterRGB(QgsProcessingAlgorithm):
    RASTER_A = 'RASTER_A'
    RASTER_B = 'RASTER_B'
    OUTPUT = 'OUTPUT'
    LEGENDA = 'LEGENDA'

    def initAlgorithm(self, config=None):
            self.addParameter(QgsProcessingParameterRasterLayer(self.RASTER_A, 'Raster A (Coluna)'))
            self.addParameter(QgsProcessingParameterRasterLayer(self.RASTER_B, 'Raster B (Linha)'))
            self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, 'Bivariate (RGB)'))
            self.addParameter(QgsProcessingParameterFileDestination(
                self.LEGENDA,
                'Legenda (imagem PNG)',
                fileFilter='PNG files (*.png)'
            ))

            self.addParameter(
                QgsProcessingParameterEnum(
                    'PALETA',
                    'Paleta de Cores',
                    options=['Rosa-Ciano', 'Laranja-Azul', 'Verde-Roxo', 'Azul-Vermelho'],
                    defaultValue=0
                ))

    def processAlgorithm(self, parameters, context, feedback):
        raster_a = self.parameterAsRasterLayer(parameters, self.RASTER_A, context)
        raster_b = self.parameterAsRasterLayer(parameters, self.RASTER_B, context)
        output_path = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        legend_path = self.parameterAsFileOutput(parameters, self.LEGENDA, context)

        classes = 3
        
        palette_index = self.parameterAsEnum(parameters, 'PALETA', context)
        palettes = {
            0: np.array([  # Rosa–Ciano
                ["#d3d3d3", "#D4C9E5", "#E7B6D7"],
                ["#7BB7E0", "#8A8CC5", "#A868B4"],
                ["#3478BC", "#4D589E", "#6C377E"]
            ]),
            1: np.array([  # Laranja–Azul
                ["#d3d3d3", "#d4c080", "#d4a200"],
                ["#96d0d4", "#96c080", "#96a200"],
                ["#39c9d4", "#39c080", "#39a200"]
            ]),
            2: np.array([  # Verde–Roxo
                ["#d3d3d3", "#bc92cb", "#a24ac2"],
                ["#a2d4b4", "#777a8f", "#673e89"],
                ["#54d483", "#549283", "#353e64"]
            ]),
            3: np.array([  # Azul-Vermelho
                ["#d3d3d3", "#ba8890", "#9d3545"],
                ["#8aa6c2", "#796b83", "#682a41"],
                ["#4179af", "#3a4e78", "#311d3a"]
            ])
        }
        palette = palettes[palette_index]
        
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
        # RGB bands como float32
        rgb_arr = np.full((*arr_a.shape, 3), np.nan, dtype=np.float32)
        for j in range(classes):
            for i in range(classes):
                color_hex = palette[j, i].lstrip('#')
                rgb = tuple(int(color_hex[k:k + 2], 16) for k in (0, 2, 4))
                mask = (i_class == i) & (j_class == j) & valid_mask
                for b in range(3):
                    rgb_arr[:, :, b][mask] = rgb[b]

        #-----------------------------------
        # Bandas originais como float32 com np.nan
        band4 = np.full(shape, np.nan, dtype=np.float32)
        band5 = np.full(shape, np.nan, dtype=np.float32)
        band4[valid_mask] = arr_a.data[valid_mask]
        band5[valid_mask] = arr_b.data[valid_mask]

        #-----------------------------------
        # Atualizar metadata
        meta.update({
            'count': 5,
            'dtype': 'float32',
            'nodata': -9999.0
        })

        #-----------------------------------
        # Escrever TIFF com 5 bandas em float32
        with rasterio.open(output_path, 'w', **meta) as dst:
            for b in range(3):
                dst.write(np.nan_to_num(rgb_arr[:, :, b], nan=-9999.0), b + 1)
            dst.write(np.nan_to_num(band4, nan=-9999.0), 4)
            dst.write(np.nan_to_num(band5, nan=-9999.0), 5)
            dst.update_tags(1, BANDNAME='Red')
            dst.update_tags(2, BANDNAME='Green')
            dst.update_tags(3, BANDNAME='Blue')
            dst.update_tags(4, BANDNAME='Raw values - Raster A')
            dst.update_tags(5, BANDNAME='Raw values - Raster B (aligned)')

        #-----------------------------------
        # Carregar no QGIS
        result_layer = QgsRasterLayer(output_path, 'bivariate_raster', 'gdal')
        if not result_layer.isValid():
            raise Exception("Falha ao criar o raster resultante.")
        context.temporaryLayerStore().addMapLayer(result_layer)

        renderer = QgsMultiBandColorRenderer(result_layer.dataProvider(), 1, 2, 3)
        result_layer.setRenderer(renderer)
        result_layer.triggerRepaint()


        #-----------------------------------
        #generate image for map legend
        cell = 200
        arrow_len = cell*3+20
        arrow_thickness = 4
        arrow_head = 15
        offset_x = arrow_len 
        offset_y = arrow_len 
        
        #image size
        img_w = classes * cell + 40
        img_h = classes * cell + 35
        
        legend = Image.new("RGB", (img_w, img_h), "white")
        draw = ImageDraw.Draw(legend)
        
        # deslocamento da matriz
        offset_matrix_x = 25
        offset_matrix_y = 10
        for j in range(classes):
            for i in range(classes):
                cor = palette[j, i]
                x0 = offset_matrix_x + i * cell
                y0 = offset_matrix_y + (classes - 1 - j) * cell
                x1 = x0 + cell
                y1 = y0 + cell
                draw.rectangle([x0, y0, x1, y1], fill=cor)
                
        # arrow origin
        origin_x = 10
        origin_y = classes * cell +5
        
        # Right arrow
        draw.line([(origin_x + 15, origin_y + 20), (origin_x + arrow_len-15, origin_y + 20)], fill="black", width=arrow_thickness)
        draw.polygon([
            (origin_x + arrow_len, origin_y + 20),
            (origin_x + arrow_len - arrow_head, origin_y + 20 - arrow_head / 2),
            (origin_x + arrow_len - arrow_head, origin_y + 20 + arrow_head / 2)
        ], fill="black")

        # Up arrow
        draw.line([(origin_x, origin_y + 20 - 15), (origin_x, origin_y+ 20 - arrow_len+15)], fill="black", width=arrow_thickness)
        draw.polygon([
            (origin_x, origin_y+ 20 - arrow_len),
            (origin_x - arrow_head / 2, origin_y+ 20 - arrow_len + arrow_head),
            (origin_x + arrow_head / 2, origin_y+ 20 - arrow_len + arrow_head)
        ], fill="black")
                
        legend.save(legend_path)
        return {self.OUTPUT: result_layer.id(), self.LEGENDA: legend_path}
        #-----------------------------------
        #-----------------------------------
        #-----------------------------------
    def name(self):
        return 'bivariate_raster_rgb'

    def displayName(self):
        return self.tr('Raster Bivariado RGB')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Raster'

    def createInstance(self):
        return BivariateRasterRGB()
    
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def shortHelpString(self):
        return self.tr("""Gera um raster bivariado RGB com cores pronto para o layout a partir de dois rasters de entrada. O RGB representa combinações de classes. 
        As bandas 4 e 5 contêm os valores brutos dos rasters A e B. A legenda é salva como PNG. 
        Dica: use valores min=0  e max=255 quando usar a simbologia multibanda RGB.""")
