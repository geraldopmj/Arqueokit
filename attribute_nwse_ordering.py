# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Ordenação espacial NW → SE (Passo a Passo)
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
    QgsProcessingParameterString,
    QgsField,
    QgsProcessingException
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
            'Nome do campo de ordenação',
            defaultValue='OrderNum'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.LAYER, context)
        nome_campo = self.parameterAsString(parameters, self.CAMPO, context)

        if not layer:
            raise QgsProcessingException("Camada inválida.")

        dp = layer.dataProvider()

        # -------------------------------
        # 1) Remover o campo de ordenação se já existir
        # -------------------------------
        idx = layer.fields().indexFromName(nome_campo)
        if idx != -1:
            if not dp.deleteAttributes([idx]):
                raise QgsProcessingException(f"Erro ao remover o campo {nome_campo}.")
            layer.updateFields()
            feedback.pushInfo(f"Campo {nome_campo} removido.")
            if not layer.commitChanges():
                layer.startEditing()
                feedback.pushInfo(f"Salvo após remover {nome_campo}.")

        # -------------------------------
        # 2) Criar o campo de ordenação
        # -------------------------------
        if layer.fields().indexFromName(nome_campo) == -1:
            if not dp.addAttributes([QgsField(nome_campo, QVariant.Int)]):
                raise QgsProcessingException(f"Erro ao adicionar o campo {nome_campo}.")
            layer.updateFields()
            feedback.pushInfo(f"Campo {nome_campo} criado.")
            if not layer.commitChanges():
                layer.startEditing()
                feedback.pushInfo(f"Salvo após criar {nome_campo}.")

        campo_idx = layer.fields().indexFromName(nome_campo)
        if campo_idx == -1:
            raise QgsProcessingException("Não foi possível localizar o campo de ordenação.")

        # -------------------------------
        # 3) Coletar feições e ordenar NW → SE
        # -------------------------------
        pontos = []
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                p = geom.asPoint()
                pontos.append((feat.id(), p.y(), p.x()))  # (fid, lat, lon)

        if not pontos:
            raise QgsProcessingException("A camada não contém feições para ordenar.")

        pontos.sort(key=lambda x: (-x[1], x[2]))  # latitude desc, longitude asc

        # -------------------------------
        # 4) Atualizar valores de ordenação em lote
        # -------------------------------
        attr_changes = {}
        for ordem, (fid, _, _) in enumerate(pontos, start=1):
            attr_changes[fid] = {campo_idx: ordem}

        if not dp.changeAttributeValues(attr_changes):
            raise QgsProcessingException("Erro ao atualizar a ordenação NW→SE.")

        feedback.pushInfo(f"Campo {nome_campo} atualizado com sucesso (NW→SE).")
        if not layer.commitChanges():
            layer.startEditing()
            feedback.pushInfo("Salvo após atualizar ordenação.")

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
        Remove e recria o campo de ordenação e atribui valores de 1..n
        seguindo a ordem espacial NW → SE.
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
