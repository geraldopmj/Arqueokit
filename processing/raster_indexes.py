# -*- coding: utf-8 -*-
"""
/***********************************************
Arqueokit – Spectral Indices (0–1 normalization + NaN-safe)
Author: Geraldo Pereira de Morais Júnior
Email: geraldo.pmj@gmail.com
Date: 2025-08-12
 ***********************************************/
"""
__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-08-12'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterString,
    QgsProcessingParameterEnum, QgsProcessingParameterBoolean,
    QgsProcessingParameterRasterDestination, QgsProcessingParameterFolderDestination,
    QgsProcessingException, QgsRasterLayer, QgsProcessingContext
)
import os
import numpy as np
import rasterio


# -------------------- Utilities -------------------- #

def tr(text: str) -> str:
    return QCoreApplication.translate('Processing', text)


def parse_band_mapping(mapping_text: str) -> dict:
    """Convert 'R=3,G=2,...' into {'R':2,'G':1,...} (0-based)."""
    band_mapping = {}
    if not mapping_text:
        return band_mapping
    for token in mapping_text.split(','):
        key, value = token.split('=')
        band_mapping[key.strip().upper()] = int(value.strip()) - 1
    return band_mapping


def safe_division(numerator_array: np.ndarray, denominator_array: np.ndarray) -> np.ndarray:
    """Division that propagates NaN/Inf as NaN (no zeroing)."""
    with np.errstate(divide='ignore', invalid='ignore'):
        result = numerator_array / denominator_array
    result[~np.isfinite(result)] = np.nan
    return result


def normalize_01(input_array: np.ndarray) -> np.ndarray:
    """Min–max normalization to [0,1], ignoring NaNs. Constant bands → zeros."""
    min_value = np.nanmin(input_array)
    max_value = np.nanmax(input_array)
    if not np.isfinite(min_value) or not np.isfinite(max_value):
        return np.full_like(input_array, np.nan, dtype=np.float32)
    if max_value <= min_value:
        return np.zeros_like(input_array, dtype=np.float32)
    return ((input_array - min_value) / (max_value - min_value)).astype(np.float32)


def read_bands_and_mask(dataset: rasterio.io.DatasetReader, band_mapping: dict, feedback=None):
    """
    Read bands, apply valid mask, and inject NaN outside mask.
    Returns: dict of bands (float32 with NaN) and global boolean mask (True = valid).
    """
    band_arrays, mask_list = {}, []
    for band_name, band_index0 in band_mapping.items():
        if 0 <= band_index0 < dataset.count:
            if feedback:
                feedback.pushInfo(f"[Band] {band_name} ← band {band_index0 + 1}")
            band_array = dataset.read(band_index0 + 1).astype(np.float32)

            valid_mask = dataset.read_masks(band_index0 + 1) > 0
            if dataset.nodatavals and dataset.nodatavals[band_index0] is not None:
                nodata_value = np.float32(dataset.nodatavals[band_index0])
                valid_mask &= band_array != nodata_value

            band_array[~valid_mask] = np.nan
            band_arrays[band_name] = band_array
            mask_list.append(valid_mask)
        else:
            if feedback:
                feedback.pushInfo(f"[Aviso] '{band_name}={band_index0 + 1}' excede nº de bandas ({dataset.count}). Ignorado.")
    global_valid_mask = np.logical_and.reduce(mask_list) if mask_list else None
    return band_arrays, global_valid_mask


def available_index_definitions(available_keys: set) -> dict:
    """
    Catalog {index_name: lambda(bands)}; only if required bands exist.
    Input bands are normalized to [0,1] with NaNs at invalid pixels.
    """
    has = {k: (k in available_keys) for k in ['R', 'G', 'B', 'NIR', 'SWIR1', 'SWIR2']}
    index_functions = {}

    # Vegetation
    if has['NIR'] and has['R']:
        index_functions['NDVI']   = lambda B: safe_division(B['NIR'] - B['R'], B['NIR'] + B['R'])
        index_functions['EVI2']   = lambda B: 2.5 * safe_division(B['NIR'] - B['R'], B['NIR'] + 2.4*B['R'] + 1.0)
        index_functions['SAVI']   = lambda B: 1.7 * safe_division(B['NIR'] - B['R'], B['NIR'] + B['R'] + 0.7)
        index_functions['MSAVI2'] = lambda B: (2*B['NIR'] + 1.0 - np.sqrt((2*B['NIR'] + 1.0)**2 - 8.0*(B['NIR'] - B['R'])))/2.0
        index_functions['OSAVI']  = lambda B: 1.16 * safe_division(B['NIR'] - B['R'], B['NIR'] + B['R'] + 0.16)
        index_functions['EVI']    = lambda B: 2.5 * safe_division(B['NIR'] - B['R'], B['NIR'] + 6.0*B['R'] - 7.5*B['B'] + 1.0)
    if has['NIR'] and has['G']:
        index_functions['GCVI']   = lambda B: safe_division(B['NIR'], B['G']) - 1.0
        index_functions['GNDVI']  = lambda B: safe_division(B['NIR'] - B['G'], B['NIR'] + B['G'])
    if has['R'] and has['NIR'] and has['SWIR2']:
        index_functions['HallCover'] = lambda B: (-0.017*B['R']) + (-0.007*B['NIR']) + (-0.079*B['SWIR2']) + 5.22

    # Water / moisture
    if has['NIR'] and has['SWIR1']:
        index_functions['NDWI']  = lambda B: safe_division(B['NIR'] - B['SWIR1'], B['NIR'] + B['SWIR1'])  # ≃ NDMI
        index_functions['NDMI']  = lambda B: safe_division(B['NIR'] - B['SWIR1'], B['NIR'] + B['SWIR1'])
        index_functions['BSCI']  = lambda B: safe_division(B['SWIR1'] - B['NIR'], B['SWIR1'] + B['NIR'])
    if has['G'] and has['NIR']:
        index_functions['NDWI_McFeeters'] = lambda B: safe_division(B['G'] - B['NIR'], B['G'] + B['NIR'])

    # Soil / burn
    if has['SWIR2'] and has['SWIR1']:
        index_functions['CAI']   = lambda B: safe_division(B['SWIR2'], B['SWIR1'])
        index_functions['NBR2']  = lambda B: safe_division(B['SWIR1'] - B['SWIR2'], B['SWIR1'] + B['SWIR2'])
    if has['NIR'] and has['SWIR2']:
        index_functions['NBR']   = lambda B: safe_division(B['NIR'] - B['SWIR2'], B['NIR'] + B['SWIR2'])
    if has['G'] and has['SWIR1']:
        index_functions['NDSI']  = lambda B: safe_division(B['G'] - B['SWIR1'], B['G'] + B['SWIR1'])
    if all(k in available_keys for k in ('SWIR1','R','NIR','B')):
        index_functions['BSI']   = lambda B: safe_division((B['SWIR1'] + B['R']) - (B['NIR'] + B['B']),
                                                           (B['SWIR1'] + B['R']) + (B['NIR'] + B['B']))

    # Pigments / atmosphere
    if all(k in available_keys for k in ('NIR','R','B')):
        index_functions['ARVI']  = lambda B: safe_division(B['NIR'] - (2.0*B['R'] - B['B']),
                                                           B['NIR'] + (2.0*B['R'] - B['B']))
    if all(k in available_keys for k in ('NIR','B','R')):
        index_functions['SIPI']  = lambda B: safe_division(B['NIR'] - B['B'], B['NIR'] + B['R'])
    if has['B'] and has['G']:
        index_functions['PRI']   = lambda B: safe_division(B['B'] - B['G'], B['B'] + B['G'])

    # Visible color / veg
    if has['G'] and has['R'] and has['B']:
        index_functions['VARI']  = lambda B: safe_division(B['G'] - B['R'], B['G'] + B['R'] - B['B'])
        index_functions['EXG']   = lambda B: 2.0*B['G'] - B['R'] - B['B']
    if has['G'] and has['R']:
        index_functions['GRVI']  = lambda B: safe_division(B['G'] - B['R'], B['G'] + B['R'])
        index_functions['NDTI']  = lambda B: safe_division(B['R'] - B['G'], B['R'] + B['G'])

    # Advanced moisture
    if all(k in available_keys for k in ('NIR','SWIR2')):
        index_functions['GVMI']  = lambda B: safe_division((B['NIR'] + 0.1) - (B['SWIR2'] + 0.02),
                                                           (B['NIR'] + 0.1) + (B['SWIR2'] + 0.02))
    if all(k in available_keys for k in ('NIR','SWIR1','SWIR2')):
        index_functions['NMDI']  = lambda B: safe_division(B['NIR'] - (B['SWIR1'] - B['SWIR2']),
                                                           B['NIR'] + (B['SWIR1'] - B['SWIR2']))
    return index_functions


# -------------------- Processing Algorithm -------------------- #

class Spectral_Indices_Generator(QgsProcessingAlgorithm):
    RASTER = 'RASTER'
    BANDMAP = 'BANDMAP'
    WHICH = 'WHICH'
    WRITE_SEPARATE = 'WRITE_SEPARATE'
    OUT_DIR = 'OUT_DIR'
    STACK_OUT = 'STACK_OUT'

    INDEX_CATALOG = [
        "NDVI","EVI2","SAVI","MSAVI2","OSAVI",
        "CAI","NBR2",
        "NDWI","NDMI","BSCI",
        "GCVI","GNDVI",
        "HallCover","PRI","VARI","EXG","GRVI","NDTI",
        "BSI","ARVI","SIPI","GVMI","NMDI",
        "NDWI_McFeeters","NBR","NDSI","EVI"
    ]

    # QGIS metadata
    def tr(self, s): return tr(s)
    def name(self): return 'spectral_indices'
    def displayName(self): return self.tr('Geração de Índices Espectrais')
    def group(self): return self.tr('Índices Espectrais')
    def groupId(self): return 'spectral_indices'
    def createInstance(self): return Spectral_Indices_Generator()
    def shortHelpString(self):
        return self.tr("""
Calcula índices espectrais a partir de raster multibanda (conforme BANDMAP).
As bandas são normalizadas para [0,1] antes dos cálculos. Operações propagam NaN.
Permite gravar rasters separados e/ou um empilhado.
""")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.RASTER, self.tr('Raster multibanda')))
        self.addParameter(QgsProcessingParameterString(
            self.BANDMAP, self.tr('Mapeamento de bandas (ex.: R=3,G=2,B=1,NIR=4,SWIR1=5,SWIR2=6)'),
            defaultValue='R=3,G=2,B=1,NIR=4,SWIR1=5,SWIR2=6'
        ))
        default_all = list(range(len(self.INDEX_CATALOG)))
        self.addParameter(QgsProcessingParameterEnum(
            self.WHICH, self.tr('Índices a calcular'),
            options=self.INDEX_CATALOG, allowMultiple=True, defaultValue=default_all
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.WRITE_SEPARATE, self.tr('Gravar rasters separados (um por índice)'), defaultValue=True))
        self.addParameter(QgsProcessingParameterFolderDestination(
            self.OUT_DIR, self.tr('Pasta de saída (rasters separados)')))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.STACK_OUT, self.tr('Raster Empilhado (GeoTIFF) [opcional]')))

    def processAlgorithm(self, parameters, context, feedback):
        raster_layer = self.parameterAsRasterLayer(parameters, self.RASTER, context)
        if raster_layer is None:
            raise QgsProcessingException("Raster inválido.")
        source_path = raster_layer.dataProvider().dataSourceUri().split('|')[0]

        band_mapping = parse_band_mapping(self.parameterAsString(parameters, self.BANDMAP, context))
        selected_index_indices = self.parameterAsEnums(parameters, self.WHICH, context) or list(range(len(self.INDEX_CATALOG)))
        write_separate = self.parameterAsBool(parameters, self.WRITE_SEPARATE, context)
        output_directory = self.parameterAsString(parameters, self.OUT_DIR, context)
        stack_output_path = self.parameterAsOutputLayer(parameters, self.STACK_OUT, context)

        if write_separate and not output_directory:
            raise QgsProcessingException("Seleção de rasters separados requer pasta de saída.")

        selected_index_names = [self.INDEX_CATALOG[i] for i in selected_index_indices]

        with rasterio.open(source_path) as dataset:
            feedback.pushInfo(f"[Open] {source_path}")
            band_arrays, _global_mask = read_bands_and_mask(dataset, band_mapping, feedback)
            if not band_arrays:
                raise QgsProcessingException("BANDMAP não corresponde a bandas existentes.")

            # Normalize each band to [0,1]
            for band_key in list(band_arrays.keys()):
                band_arrays[band_key] = normalize_01(band_arrays[band_key])

            index_defs = available_index_definitions(set(band_arrays.keys()))

            # Filter available indices
            index_jobs = []
            for index_name in selected_index_names:
                if index_name in index_defs:
                    index_jobs.append((index_name, index_defs[index_name]))
                else:
                    feedback.pushInfo(f"[Aviso] Índice {index_name} indisponível (bandas insuficientes).")
            if not index_jobs:
                raise QgsProcessingException("Nenhum índice a calcular com as bandas fornecidas.")

            # Output profile
            base_profile = dataset.profile.copy()
            base_profile.update(count=1, dtype='float32', nodata=np.float32(-9999), compress='deflate', predictor=2)

            stack_band_list, stack_band_names = [], []
            total_jobs = len(index_jobs)

            for job_index, (index_name, index_fn) in enumerate(index_jobs, start=1):
                feedback.setProgressText(f"Índice {index_name} ({job_index}/{total_jobs})")
                feedback.setProgress(int(100 * job_index / max(1, total_jobs)))

                try:
                    index_array = index_fn(band_arrays).astype(np.float32)
                except Exception as exc:
                    feedback.pushInfo(f"[Erro] {index_name}: {exc}")
                    continue

                output_array = index_array.copy()
                output_array[~np.isfinite(output_array)] = -9999.0

                stack_band_list.append(output_array)
                stack_band_names.append(index_name)

                if write_separate:
                    os.makedirs(output_directory, exist_ok=True)
                    output_path = os.path.join(
                        output_directory,
                        f"{os.path.splitext(os.path.basename(source_path))[0]}_{index_name}.tif"
                    )
                    with rasterio.open(output_path, 'w', **base_profile) as outds:
                        outds.write(output_array, 1)
                    feedback.pushInfo(f"[Saída] {index_name} → {output_path}")

                    # Schedule auto-load into QGIS project
                    raster_tmp_layer = QgsRasterLayer(output_path, index_name)
                    if raster_tmp_layer.isValid():
                        context.temporaryLayerStore().addMapLayer(raster_tmp_layer)
                        layer_details = QgsProcessingContext.LayerDetails(index_name, context.project())
                        context.addLayerToLoadOnCompletion(raster_tmp_layer.id(), layer_details)
                    else:
                        feedback.reportError(f"[Aviso] Raster inválido ao carregar: {output_path}")

            results = {}

            # Optional stacked output
            if stack_output_path:
                if stack_band_list:
                    stack_cube = np.stack(stack_band_list, axis=0)  # [bands, rows, cols]
                    stack_profile = base_profile.copy()
                    stack_profile.update(count=stack_cube.shape[0])
                    with rasterio.open(stack_output_path, 'w', **stack_profile) as outds:
                        outds.write(stack_cube)
                        try:
                            for band_i, band_name in enumerate(stack_band_names, start=1):
                                outds.set_band_description(band_i, band_name)
                        except Exception:
                            pass
                    feedback.pushInfo(f"[Empilhado] {len(stack_band_names)} bandas → {stack_output_path}")
                    results[self.STACK_OUT] = stack_output_path
                else:
                    feedback.pushInfo("[Empilhado] Nada a escrever.")

            if write_separate:
                results[self.OUT_DIR] = output_directory

            feedback.pushInfo(f"[Resumo] Selecionados: {len(selected_index_names)}; gravados: {len(stack_band_names)}.")
            return results
