# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Adicionar Atributos de Ficha Arqueológica
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


class AddRecordAttributes(QgsProcessingAlgorithm):
    """Adiciona os campos padrão da ficha arqueológica a uma camada de pontos"""

    INPUT = 'INPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT,
            self.tr('Camada de pontos (será editada)'),
            types=[QgsProcessing.TypeVectorPoint]
        ))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)

        if not layer:
            raise QgsProcessingException(self.tr("Camada inválida ou não encontrada."))

        if not layer.isEditable():
            layer.startEditing()

        # Definições dos campos com tipos corretos
        field_defs = {
            "id": QVariant.Int,
            "Name": QVariant.String,
            "Lat": QVariant.Double,
            "Long": QVariant.Double,
            "Data": QVariant.Date,
            "Veg": QVariant.String,
            "Rel": QVariant.String,
            "Realizado": QVariant.String,
            "Motivo": QVariant.String,
            "Resp": QVariant.String,
        }

        for c in range(1, 6):
            field_defs[f'prof_C{c}'] = QVariant.String
            field_defs[f'solo_C{c}'] = QVariant.String
            field_defs[f'vestigios_C{c}'] = QVariant.String
            field_defs[f'qnt_vstgC{c}'] = QVariant.Int

        for f in ['foto1', 'foto2', 'foto3', 'foto4']:
            field_defs[f] = QVariant.String

        # Adiciona apenas campos que não existem
        existing_fields = [f.name() for f in layer.fields()]
        for name, qtype in field_defs.items():
            if name not in existing_fields:
                layer.addAttribute(QgsField(name, qtype))

        layer.updateFields()

        idx_lat = layer.fields().indexFromName('Lat')
        idx_lon = layer.fields().indexFromName('Long')
        idx_id = layer.fields().indexFromName('id')
        idx_name = layer.fields().indexFromName('Name')

        if idx_lat < 0 or idx_lon < 0 or idx_id < 0 or idx_name < 0:
            raise QgsProcessingException(self.tr("Erro ao criar os campos essenciais (id, Name, Lat, Long)."))

        # Coletar feições para ordenar NW -> SE
        pontos = []
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                p = geom.asPoint()
                pontos.append((feat.id(), p.y(), p.x()))  # (fid, lat, lon)

        if not pontos:
            raise QgsProcessingException(self.tr("A camada não contém feições para processar."))

        # Ordenar NW -> SE (latitude decrescente e longitude crescente)
        pontos.sort(key=lambda x: (-x[1], x[2]))

        # Preencher atributos automáticos
        for ordem, (fid, lat, lon) in enumerate(pontos, start=1):
            # id = $id
            layer.changeAttributeValue(fid, idx_id, ordem)

            # coordenadas
            layer.changeAttributeValue(fid, idx_lat, lat)
            layer.changeAttributeValue(fid, idx_lon, lon)

            # Name = PT-numero ordenado
            layer.changeAttributeValue(fid, idx_name, f"PT-{ordem}")

        if not layer.commitChanges():
            raise QgsProcessingException(self.tr("Não foi possível salvar as alterações."))

        feedback.pushInfo(self.tr("Campos da ficha adicionados e atributos automáticos preenchidos (Name = PT-<número> NW→SE)!"))
        return {}

    # Metadados do algoritmo
    def name(self):
        return 'adicionar_atributos_ficha'

    def displayName(self):
        return self.tr('Adicionar Atributos de Ficha Arqueológica')

    def group(self):
        return 'Adicionar Atributo'

    def groupId(self):
        return 'adicionar_atributo'

    def createInstance(self):
        return AddRecordAttributes()

    def shortHelpString(self):
        return self.tr("""
        Este algoritmo adiciona os campos utilizados nas fichas arqueológicas diretamente na camada (in-place) 
        e preenche automaticamente:
        - id = $id
        - Lat/Long = coordenadas do ponto
        - Name = PT-<número ordenado NW→SE>
        - Data (Date)
        - qnt_vstgC# (Int)
        Os demais campos são de texto (String).
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
