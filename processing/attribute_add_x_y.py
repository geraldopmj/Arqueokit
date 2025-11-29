# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Atualizar Longitude e Latitude (Estável)
 Autor: Geraldo Pereira de Morais Júnior
 ***********************************************/
"""

__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-07-26'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsField,
    QgsProcessingException
)

class AddXY(QgsProcessingAlgorithm):
    ENTRADA = 'ENTRADA'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.ENTRADA,
            self.tr('Camada de entrada (será editada)'),
            [QgsProcessing.TypeVectorPoint]
        ))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.ENTRADA, context)
        if not layer:
            raise QgsProcessingException(self.tr("Camada de entrada inválida."))

        dp = layer.dataProvider()

        if not layer.isEditable():
            layer.startEditing()

        feedback.pushInfo("Verificando estrutura da tabela...")
        
        campos_necessarios = ["Longitude", "Latitude"]
        novos_campos = []
        
        for campo in campos_necessarios:
            if layer.fields().indexFromName(campo) == -1:
                novos_campos.append(QgsField(campo, QVariant.Double, len=20, prec=6))
            else:
                feedback.pushInfo(f"Campo '{campo}' já existe. Será atualizado.")

        if novos_campos:
            if not dp.addAttributes(novos_campos):
                raise QgsProcessingException(self.tr("Erro ao adicionar colunas de coordenadas."))
            layer.updateFields()
            feedback.pushInfo(f"Criados {len(novos_campos)} novos campos.")

        idx_lon = layer.fields().indexFromName("Longitude")
        idx_lat = layer.fields().indexFromName("Latitude")

        if idx_lon == -1 or idx_lat == -1:
            raise QgsProcessingException(self.tr("Falha crítica: Campos de coordenadas inacessíveis."))

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

        if not attr_changes:
            feedback.pushInfo("Nenhuma feição geométrica válida encontrada para atualizar.")
            return {}

        feedback.pushInfo(f"Atualizando coordenadas de {len(attr_changes)} pontos...")
        
        if not dp.changeAttributeValues(attr_changes):
            raise QgsProcessingException(self.tr("Erro ao persistir valores na tabela."))

        if not layer.commitChanges():
             layer.rollBack()
             raise QgsProcessingException(self.tr("Erro ao salvar no disco. Verifique permissões."))
        
        feedback.pushInfo("Processo concluído com sucesso.")

        return {}

    def name(self):
        return 'atualizar_lat_long'

    def displayName(self):
        return self.tr('Atualizar Longitude e Latitude')

    def group(self):
        return 'Adicionar Atributo'

    def groupId(self):
        return 'adicionar_atributo'

    def createInstance(self):
        return AddXY()

    def shortHelpString(self):
        return self.tr("""
        Verifica e cria campos 'Longitude' e 'Latitude' e atualiza com coordenadas 
        com precisão de 6 casas decimais. Não apaga dados existentes.
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)