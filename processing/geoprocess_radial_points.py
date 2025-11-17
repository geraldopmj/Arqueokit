# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Geração de Pontos Radiais
 Autor: Geraldo Pereira de Morais Júnior
 Email: geraldo.pmj@gmail.com
 ***********************************************/
"""

__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-07-26'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

import math
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsFields, QgsField, QgsFeature,
    QgsPointXY, QgsWkbTypes, QgsFeatureSink,
    QgsGeometry
)
from PyQt5.QtCore import QVariant

class radial_points(QgsProcessingAlgorithm):
    PONTOS = 'PONTOS'
    DISTANCIA = 'DISTANCIA'
    LIMIT_MODE = 'LIMIT_MODE'
    LIMITE = 'LIMITE'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.PONTOS,
            'Camada de Pontos',
            [QgsProcessing.TypeVectorPoint]
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.DISTANCIA,
            'Distância entre pontos (m)',
            QgsProcessingParameterNumber.Double,
            defaultValue=50.0,
            minValue=1.0
        ))
        # Tipo de limite
        self.addParameter(QgsProcessingParameterEnum(
            self.LIMIT_MODE,
            'Modo de Limite',
            options=[
                'Distância máxima (m)',
                'Buffer (raio em m)',
                'Número de pontos por direção'
            ],
            defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.LIMITE,
            'Valor do limite (m ou nº de pontos)',
            QgsProcessingParameterNumber.Double,
            defaultValue=300.0,
            minValue=1.0
        ))
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                'OUTPUT',
                'Camada de Saída'
        ))

    def criar_campo(self, nome, tipo, comprimento=None, precisao=None):
        campo = QgsField(nome, tipo, '', 0, 0)
        if comprimento is not None:
            campo.setLength(comprimento)
        if precisao is not None:
            campo.setPrecision(precisao)
        return campo

    def processAlgorithm(self, parameters, context, feedback):
        fonte = self.parameterAsSource(parameters, self.PONTOS, context)
        dist = self.parameterAsDouble(parameters, self.DISTANCIA, context)
        limit_mode = self.parameterAsEnum(parameters, self.LIMIT_MODE, context)
        limite = self.parameterAsDouble(parameters, self.LIMITE, context)

        if not fonte:
            raise Exception("Fonte de pontos inválida.")

        # Campos de saída
        campos = QgsFields()
        campos.append(self.criar_campo("orig_id", QVariant.Int, comprimento=10))
        campos.append(self.criar_campo("dir", QVariant.String, comprimento=5))
        campos.append(self.criar_campo("dist_m", QVariant.Double, comprimento=20, precisao=2))

        (sink, dest_id) = self.parameterAsSink(parameters, 'OUTPUT', context, campos, QgsWkbTypes.Point, fonte.sourceCrs())

        # Direções cardeais e diagonais
        directions = [
            (0, 1, "N"), (0, -1, "S"), (1, 0, "E"), (-1, 0, "O"),
            (1, 1, "NE"), (-1, 1, "NO"), (1, -1, "SE"), (-1, -1, "SO")
        ]

        # Usa selecionados se houver
        features = list(fonte.getFeatures())
        if hasattr(fonte, "selectedFeatureCount") and fonte.selectedFeatureCount() > 0:
            features = list(fonte.getSelectedFeatures())

        total = len(features)
        feedback.pushInfo(f"Pontos de origem: {total}")

        for idx, feat in enumerate(features):
            if feedback.isCanceled():
                break

            pt = feat.geometry().asPoint()
            x0, y0 = pt.x(), pt.y()

            # Buffer para o modo 2
            buffer_geom = None
            if limit_mode == 1:
                buffer_geom = QgsGeometry.fromPointXY(QgsPointXY(x0, y0)).buffer(limite, 16)

            for dx, dy, dir_name in directions:
                d = dist
                count = 0

                while True:
                    # Condições de parada
                    if limit_mode == 0 and d > limite:  # distância máxima
                        break
                    if limit_mode == 1:  # buffer
                        offset = d / math.sqrt(2) if (dx != 0 and dy != 0) else d
                        test_point = QgsGeometry.fromPointXY(QgsPointXY(x0 + dx * offset, y0 + dy * offset))
                        if not buffer_geom.contains(test_point):
                            break
                    if limit_mode == 2 and count >= int(limite):  # nº de pontos
                        break

                    # Ajuste de distância nas diagonais
                    offset = d / math.sqrt(2) if (dx != 0 and dy != 0) else d
                    new_x = x0 + dx * offset
                    new_y = y0 + dy * offset

                    fet = QgsFeature()
                    fet.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(new_x, new_y)))
                    fet.setAttributes([feat.id(), dir_name, round(offset, 2)])
                    sink.addFeature(fet, QgsFeatureSink.FastInsert)

                    d += dist
                    count += 1

            feedback.setProgress(int((idx + 1) / total * 100))

        return {'OUTPUT': dest_id}

    def name(self):
        return 'radial_points'

    def displayName(self):
        return self.tr('Gerar Pontos Radiais')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Geoprocessamento'

    def createInstance(self):
        return radial_points()

    def shortHelpString(self):
        return self.tr("""
        Gera pontos radiais (N, S, L, O, NE, NO, SE, SO) a partir de cada ponto da camada de entrada.

        Modo de limite:
        - Distância máxima (m): gera pontos até atingir a distância.
        - Buffer (raio em m): gera pontos até cruzar o buffer do ponto de origem.
        - Número de pontos por direção: ignora a distância máxima e gera N pontos por direção.
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
