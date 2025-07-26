# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Atualizar Longitude e Latitude
 Autor: Geraldo Pereira de Morais Júnior
 Email: geraldo.pmj@gmail.com
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

        # Inicia edição
        if not layer.isEditable():
            layer.startEditing()

        # Adiciona campos se não existirem
        if layer.fields().indexFromName("Longitude") == -1:
            layer.addAttribute(QgsField("Longitude", QVariant.Double, len=10, prec=4))
        if layer.fields().indexFromName("Latitude") == -1:
            layer.addAttribute(QgsField("Latitude", QVariant.Double, len=10, prec=4))

        layer.updateFields()

        x_idx = layer.fields().indexFromName("Longitude")
        y_idx = layer.fields().indexFromName("Latitude")

        # Atualiza atributos
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if not geom:
                continue
            pt = geom.asPoint()
            layer.changeAttributeValue(feat.id(), x_idx, round(pt.x(), 2))
            layer.changeAttributeValue(feat.id(), y_idx, round(pt.y(), 2))

        if not layer.commitChanges():
            raise QgsProcessingException("Não foi possível salvar as alterações.")

        feedback.pushInfo("Longitude e Latitude atualizadas com sucesso!")
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
        Atualiza os campos 'Longitude' e 'Latitude' diretamente na camada (in-place).
        Se os campos não existirem, serão criados com 2 casas decimais.
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
