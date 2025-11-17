# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Atualizar Longitude e Latitude (Passo a Passo)
 Autor: Geraldo Pereira de Morais Júnior
 ***********************************************/
"""

__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-07-26'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsField,
    QgsProcessingException
)


class add_x_y(QgsProcessingAlgorithm):
    ENTRADA = 'ENTRADA'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.ENTRADA,
            'Camada de entrada (será editada)',
            [QgsProcessing.TypeVectorPoint]
        ))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.ENTRADA, context)
        if not layer:
            raise QgsProcessingException("Camada de entrada inválida.")

        dp = layer.dataProvider()

        # -------------------------------
        # 1) Remover os campos Latitude e Longitude (se existirem)
        # -------------------------------
        campos_remover = []
        for campo in ["Longitude", "Latitude"]:
            idx = layer.fields().indexFromName(campo)
            if idx != -1:
                campos_remover.append(idx)

        if campos_remover:
            if not dp.deleteAttributes(campos_remover):
                raise QgsProcessingException("Erro ao remover campos Latitude/Longitude.")
            layer.updateFields()
            feedback.pushInfo("Campos antigos Latitude/Longitude removidos com sucesso.")
            if not layer.commitChanges():
                layer.startEditing()
                feedback.pushInfo("Salvo após remover campos Latitude/Longitude.")

        # -------------------------------
        # 2) Adicionar campos Latitude e Longitude
        # -------------------------------
        novos_campos = []
        if layer.fields().indexFromName("Longitude") == -1:
            novos_campos.append(QgsField("Longitude", QVariant.Double, len=10, prec=4))
        if layer.fields().indexFromName("Latitude") == -1:
            novos_campos.append(QgsField("Latitude", QVariant.Double, len=10, prec=4))

        if novos_campos:
            if not dp.addAttributes(novos_campos):
                raise QgsProcessingException("Erro ao adicionar campos Latitude/Longitude.")
            layer.updateFields()
            feedback.pushInfo("Campos Latitude/Longitude adicionados com sucesso.")
            if not layer.commitChanges():
                layer.startEditing()
                feedback.pushInfo("Salvo após adicionar campos Latitude/Longitude.")

        # -------------------------------
        # 3) Atualizar os valores de Latitude e Longitude
        # -------------------------------
        idx_lon = layer.fields().indexFromName("Longitude")
        idx_lat = layer.fields().indexFromName("Latitude")

        if idx_lon == -1 or idx_lat == -1:
            raise QgsProcessingException("Campos Latitude/Longitude não encontrados após criação.")

        attr_changes = {}
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue
            pt = geom.asPoint()
            attr_changes[feat.id()] = {
                idx_lon: round(pt.x(), 2),
                idx_lat: round(pt.y(), 2)
            }

        if not dp.changeAttributeValues(attr_changes):
            raise QgsProcessingException("Erro ao atualizar valores de Latitude/Longitude.")

        feedback.pushInfo("Latitude e Longitude atualizadas com sucesso.")
        if not layer.commitChanges():
            layer.startEditing()
            feedback.pushInfo("Salvo após atualizar Latitude/Longitude.")

        return {}

    def name(self):
        return 'add_x_y'

    def displayName(self):
        return self.tr('Atualizar Longitude e Latitude')

    def group(self):
        return 'Adicionar Atributo'

    def groupId(self):
        return 'adicionar_atributo'

    def createInstance(self):
        return add_x_y()

    def shortHelpString(self):
        return self.tr("""
        Remove os campos 'Longitude' e 'Latitude' (se existirem),
        os recria e atualiza com as coordenadas dos pontos (2 casas decimais).
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
