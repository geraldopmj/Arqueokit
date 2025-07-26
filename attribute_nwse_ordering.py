# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Ordenação espacial NW → SE
 Autor: Geraldo Pereira de Morais Júnior
 Email: geraldo.pmj@gmail.com
 ***********************************************/
"""

__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-07-19'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterString,
    QgsProcessingParameterField,
    QgsVectorLayer,
    QgsFeature,
    QgsField,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    edit
)

class OrdenarPontosNWSE(QgsProcessingAlgorithm):
    LAYER = 'LAYER'
    CAMPO = 'CAMPO'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.LAYER,
            'Camada de Pontos',
            types=[QgsProcessing.TypeVectorPoint]
        ))
        self.addParameter(QgsProcessingParameterString(
            self.CAMPO,
            'Nome do campo a ser criado',
            defaultValue='OrderNum'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.LAYER, context)
        nome_campo = self.parameterAsString(parameters, self.CAMPO, context)

        if not layer.isEditable():
            layer.startEditing()

        if nome_campo not in [f.name() for f in layer.fields()]:
            layer.dataProvider().addAttributes([QgsField(nome_campo, QVariant.Int)])
            layer.updateFields()

        campo_idx = layer.fields().indexOf(nome_campo)

        # Coleta e ordena
        pontos = []
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                p = geom.asPoint()
                pontos.append((feat.id(), p.y(), p.x()))  # (fid, lat, lon)

        pontos.sort(key=lambda x: (-x[1], x[2]))  # NW → SE

        if not layer.isEditable():
            if not layer.startEditing():
                raise QgsProcessingException("Não foi possível iniciar a edição da camada.")
        
        if not any(layer.getFeatures()):
            raise QgsProcessingException("A camada não contém feições para ordenar.")

        for i, (fid, _, _) in enumerate(pontos, start=1):
            layer.changeAttributeValue(fid, campo_idx, i)

        if not layer.commitChanges():
            raise QgsProcessingException("Falha ao salvar as alterações na camada.")

        return {}

    def name(self):
        return 'ordenar_pontos_nw_se'

    def displayName(self):
        return self.tr('Ordenar Pontos de NW para SE')

    def group(self):
        return 'Adicionar Atributo'

    def groupId(self):
        return 'adicionar_atributo'

    def createInstance(self):
        return OrdenarPontosNWSE()

    def shortHelpString(self):
        return self.tr("""
        Este algoritmo ordena geograficamente uma camada de pontos do noroeste para o sudeste (NW → SE),
        baseado nas coordenadas (latitude decrescente e longitude crescente), e atribui um número sequencial
        em um novo campo inteiro.
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
