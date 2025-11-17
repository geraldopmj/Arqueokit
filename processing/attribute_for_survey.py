# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Attribute for Survey
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


class AddRecordAttributes(QgsProcessingAlgorithm):

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

        dp = layer.dataProvider()

        field_defs = {
            "id": QVariant.Int,
            "Name": QVariant.String,
            "Longitude": QVariant.Double,
            "Latitude": QVariant.Double,
            "Resp": QVariant.String,
            "Data": QVariant.Date,
            "Veg": QVariant.String,
            "Relevo": QVariant.String,
            "Realizado": QVariant.String,
            "Motivo": QVariant.String,
        }

        for c in range(1, 6):
            field_defs[f'prof_C{c}'] = QVariant.Double  # igual ao primeiro trecho
            field_defs[f'solo_C{c}'] = QVariant.String
            field_defs[f'vstg_C{c}'] = QVariant.String
            field_defs[f'type_vstgC{c}'] = QVariant.String
            field_defs[f'qnt_vstgC{c}'] = QVariant.Int

        for f in ['foto1', 'foto2', 'foto3', 'foto4']:
            field_defs[f] = QVariant.String

        # -------------------------------
        # 1) Remover atributos existentes um por um
        # -------------------------------
        existing_fields = [f.name() for f in layer.fields()]
        for name in field_defs:
            if name in existing_fields:
                idx = layer.fields().indexFromName(name)
                if idx >= 0:
                    if not dp.deleteAttributes([idx]):
                        raise QgsProcessingException(self.tr(f"Erro ao remover campo {name}."))
                    layer.updateFields()
                    feedback.pushInfo(f"Campo removido: {name}")
                    if not layer.commitChanges():
                        layer.startEditing()
                        feedback.pushInfo(f"Salvo após remover {name}")

        # -------------------------------
        # 2) Adicionar atributos um por um
        # -------------------------------
        for name, qtype in field_defs.items():
            if layer.fields().indexFromName(name) == -1:
                if not dp.addAttributes([QgsField(name, qtype)]):
                    raise QgsProcessingException(self.tr(f"Erro ao adicionar campo {name}."))
                layer.updateFields()
                feedback.pushInfo(f"Campo adicionado: {name}")
                if not layer.commitChanges():
                    layer.startEditing()
                    feedback.pushInfo(f"Salvo após adicionar {name}")

        # -------------------------------
        # 3) Atualizar id NW→SE
        # -------------------------------
        pontos = []
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                p = geom.asPoint()
                pontos.append((feat.id(), p.y(), p.x()))

        if not pontos:
            raise QgsProcessingException(self.tr("A camada não contém feições."))

        pontos.sort(key=lambda x: (-x[1], x[2]))
        idx_id = layer.fields().indexFromName('id')
        attr_changes = {}
        for ordem, (fid, _, _) in enumerate(pontos, start=1):
            attr_changes[fid] = {idx_id: ordem}

        if not dp.changeAttributeValues(attr_changes):
            raise QgsProcessingException(self.tr("Erro ao atualizar campo id."))

        feedback.pushInfo("IDs (NW→SE) atualizados com sucesso.")
        if not layer.commitChanges():
            layer.startEditing()
            feedback.pushInfo("Salvo após atualizar IDs")
            
        # -------------------------------
        # 3.1) Atualizar Name = 'PT-' || id
        # -------------------------------
        idx_name = layer.fields().indexFromName('Name')
        attr_changes = {}
        for feat in layer.getFeatures():
            new_name = f"PT-{feat['id']}"
            attr_changes[feat.id()] = {idx_name: new_name}

        if not dp.changeAttributeValues(attr_changes):
            raise QgsProcessingException(self.tr("Erro ao atualizar campo Name."))

        feedback.pushInfo("Campo Name atualizado com sucesso (PT-<id>).")
        if not layer.commitChanges():
            layer.startEditing()
            feedback.pushInfo("Salvo após atualizar Name")

        # -------------------------------
        # 4) Atualizar Lat/Long
        # -------------------------------
        idx_lat = layer.fields().indexFromName('Lat')
        idx_lon = layer.fields().indexFromName('Long')
        attr_changes = {}
        for fid, lat, lon in pontos:
            attr_changes[fid] = {idx_lat: round(lat, 2), idx_lon: round(lon, 2)}

        if not dp.changeAttributeValues(attr_changes):
            raise QgsProcessingException(self.tr("Erro ao atualizar campos Lat/Long."))

        feedback.pushInfo("Coordenadas Lat/Long atualizadas com sucesso.")
        if not layer.commitChanges():
            layer.startEditing()
            feedback.pushInfo("Salvo após atualizar Lat/Long")

        return {}

    # Metadados
    def name(self):
        return 'adicionar_atributos_ficha_step'
    def displayName(self):
        return self.tr('Adicionar Atributos de Ficha')
    def group(self):
        return 'Adicionar Atributo'
    def groupId(self):
        return 'adicionar_atributo'
    def createInstance(self):
        return AddRecordAttributes()
    def shortHelpString(self):
        return self.tr("""
        Remove e adiciona os campos da ficha arqueológica em etapas.
        Salva a camada a cada sucesso para reduzir travamentos.
        """)
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
