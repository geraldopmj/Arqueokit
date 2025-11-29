
# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Geração de Grade Ótima (modo somente análise)
 Autor: Geraldo Pereira de Morais Júnior
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
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterNumber,
    QgsFields, QgsField, QgsFeature, 
    QgsVectorLayer, QgsProject, QgsGeometry, 
    QgsPointXY, QgsWkbTypes, QgsFeatureSink
)
import shapely
import numpy as np
from PyQt5.QtCore import QVariant

class best_grid(QgsProcessingAlgorithm):
    POLIGONO = 'POLIGONO'
    ESPACAMENTO = 'ESPACAMENTO'
    PASSO = 'PASSO'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.POLIGONO,
            'Camada de Polígono',
            [QgsProcessing.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.ESPACAMENTO,
            'Espaçamento (m)',
            QgsProcessingParameterNumber.Integer,
            defaultValue=50,
            minValue=1
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.PASSO,
            'Passo (deslocamento)',
            QgsProcessingParameterNumber.Integer,
            defaultValue=5,
            minValue=1
        ))
        
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                'OUTPUT',
                'Camada de Saída'
        ))
        
    def criar_campo(self, nome, tipo, comprimento=None, precisao=None):
        campo = QgsField(nome, tipo, '', 0, 0)  # evita DeprecationWarning
        if comprimento is not None:
            campo.setLength(comprimento)
        if precisao is not None:
            campo.setPrecision(precisao)
        return campo

    def processAlgorithm(self, parameters, context, feedback):
        fonte = self.parameterAsSource(parameters, self.POLIGONO, context)
        espacamento = self.parameterAsInt(parameters, self.ESPACAMENTO, context)
        passo = self.parameterAsInt(parameters, self.PASSO, context)

        if not fonte:
            raise Exception("Fonte de polígono inválida.")

        # Define os campos antes de criar o sink
        campos = QgsFields()
        campos.append(self.criar_campo("id", QVariant.Int, comprimento=10))
        campos.append(self.criar_campo("Name", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Longitude", QVariant.Double, comprimento=20, precisao=2))
        campos.append(self.criar_campo("Latitude", QVariant.Double, comprimento=20, precisao=2))
        campos.append(self.criar_campo("Resp", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Data", QVariant.Date))
        campos.append(self.criar_campo("Veg", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Relevo", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Realizado", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Motivo", QVariant.String, comprimento=255))
        for i in range(1, 6):
            campos.append(self.criar_campo(f"prof_C{i}", QVariant.Double, comprimento=20, precisao=2))
            campos.append(self.criar_campo(f"solo_C{i}", QVariant.String, comprimento=255))
            campos.append(self.criar_campo(f"vstg_C{i}", QVariant.String, comprimento=255))
            campos.append(self.criar_campo(f"type_vstgC{i}", QVariant.String, comprimento=255))
            campos.append(self.criar_campo(f"qnt_vstgC{i}", QVariant.Int, comprimento=10))
        for i in range(1, 5):
            campos.append(self.criar_campo(f"foto{i}", QVariant.String, comprimento=255))

        (sink, dest_id) = self.parameterAsSink(parameters, 'OUTPUT', context, campos, QgsWkbTypes.Point, fonte.sourceCrs())

        features = list(fonte.getFeatures())
        feedback.pushInfo(f"Número de feições: {len(features)}")

        geometries = [f.geometry() for f in features]
        multi_geom = QgsGeometry.unaryUnion(geometries)

        feedback.pushInfo(f"Geometria unificada criada.")
        bounds = multi_geom.boundingBox()
        #feedback.pushInfo(f"Extensão: xmin={bounds.xMinimum()}, xmax={bounds.xMaximum()}, ymin={bounds.yMinimum()}, ymax={bounds.yMaximum()}")

        deslocamentos = list(range(passo, espacamento, passo))
        total_tests = len(deslocamentos) ** 2
        feedback.pushInfo(f"Total de deslocamentos a testar: {total_tests}")

        maior_n = 0
        melhor_pts = []
        melhor_coords = (0, 0)
        test_counter = 0

        for dx in deslocamentos:
            for dy in deslocamentos:
                test_counter += 1
                feedback.setProgress(int((test_counter / total_tests) * 100))

                xmin = bounds.xMinimum() + dx
                xmax = bounds.xMaximum() + dx
                ymin = bounds.yMinimum() + dy
                ymax = bounds.yMaximum() + dy

                x_coords = np.arange(xmin, xmax, espacamento)
                y_coords = np.arange(ymin, ymax, espacamento)
                xs, ys = np.meshgrid(x_coords, y_coords)
                pontos = [QgsGeometry.fromPointXY(QgsPointXY(x, y)) for x, y in zip(xs.ravel(), ys.ravel())]

                #feedback.pushInfo(f"[{test_counter}/{total_tests}] dx={dx}, dy={dy}, pontos totais={len(pontos)}")

                pontos_dentro = [pt for pt in pontos if multi_geom.contains(pt)]

                #feedback.pushInfo(f"→ Pontos dentro do polígono: {len(pontos_dentro)}")

                if len(pontos_dentro) > maior_n:
                    maior_n = len(pontos_dentro)
                    melhor_coords = (dx, dy)
                    melhor_pts = pontos_dentro

        if maior_n > 0 and melhor_pts:
            ordenados = sorted(melhor_pts, key=lambda pt: (-pt.asPoint().y(), pt.asPoint().x()))

            for idx, geom in enumerate(ordenados):
                pt = geom.asPoint()
                fet = QgsFeature()
                fet.setGeometry(geom)
                fet.setAttributes(
                    [idx + 1, f"PT-{idx+1}", round(pt.x(), 2), round(pt.y(), 2), None,
                     None, None, None, None, None] +
                    [None]*20 +  # 4 camadas × 5 atributos (todos como None)
                    [None]       # observacao
                )
                sink.addFeature(fet, QgsFeatureSink.FastInsert)

            #feedback.pushInfo(f"Melhor dx={melhor_coords[0]}, dy={melhor_coords[1]}, pontos gerados={maior_n}")
        else:
            feedback.reportError("Nenhuma grade válida encontrada.")

        return {'OUTPUT': dest_id}

    def name(self):
        return 'best_grid'

    def displayName(self):
        return self.tr('Grade com Melhor Cobertura')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Geoprocessamento'

    def createInstance(self):
        return best_grid()

    def shortHelpString(self):
        return self.tr("""
        Gera uma grade de pontos com deslocamento ótimo de forma a maximizar o número de pontos contidos em um polígono.
        A grade resultante já inclui atributos personalizados para cadastro arqueológico.
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)