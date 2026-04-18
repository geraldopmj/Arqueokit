# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Atributos para Prospeccão
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

        def start_editing():
            if layer.isEditable():
                return
            if not layer.startEditing():
                raise QgsProcessingException(self.tr("Não foi possível iniciar a edição da camada."))

        def commit_step(success_message):
            if not layer.isEditable():
                return
            if not layer.commitChanges():
                raise QgsProcessingException(self.tr("Erro ao salvar alterações da camada."))
            feedback.pushInfo(success_message)

        field_defs = {
            "id": QVariant.Int,
            "Name": QVariant.String,
            "Longitude": QVariant.Double,
            "Latitude": QVariant.Double,
            "Resp": QVariant.String,
            "Data": QVariant.Date,
            "Data_mod": QVariant.Date,
            "Veg": QVariant.String,
            "Relevo": QVariant.String,
            "Realizado": QVariant.String,
            "Motivo": QVariant.String,
            "Observ": QVariant.String,
            "X_Realizado": QVariant.String,
            "Y_Realizado": QVariant.String,
            "bool_X": QVariant.String,
            "bool_Y": QVariant.String,
        }

        for c in range(1, 6):
            field_defs[f'prof_C{c}'] = QVariant.Double
            field_defs[f'cor_C{c}'] = QVariant.String
            field_defs[f'textura_C{c}'] = QVariant.String
            field_defs[f'bioint_C{c}'] = QVariant.String
            field_defs[f'rocha_C{c}'] = QVariant.String
            field_defs[f'carvao_C{c}'] = QVariant.String
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
                    start_editing()
                    if not dp.deleteAttributes([idx]):
                        raise QgsProcessingException(self.tr(f"Erro ao remover campo {name}."))
                    layer.updateFields()
                    commit_step(f"Campo removido: {name}")

        # -------------------------------
        # 2) Adicionar atributos um por um
        # -------------------------------
        for name, qtype in field_defs.items():
            if layer.fields().indexFromName(name) == -1:
                start_editing()
                if not dp.addAttributes([QgsField(name, qtype)]):
                    raise QgsProcessingException(self.tr(f"Erro ao adicionar campo {name}."))
                layer.updateFields()
                commit_step(f"Campo adicionado: {name}")

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

        start_editing()
        if not dp.changeAttributeValues(attr_changes):
            raise QgsProcessingException(self.tr("Erro ao atualizar campo id."))

        commit_step("IDs (NW→SE) atualizados com sucesso.")
            
        # -------------------------------
        # 3.1) Atualizar Name = 'PT-' || id
        # -------------------------------
        idx_name = layer.fields().indexFromName('Name')
        attr_changes = {}
        for feat in layer.getFeatures():
            new_name = f"PT-{feat['id']}"
            attr_changes[feat.id()] = {idx_name: new_name}

        start_editing()
        if not dp.changeAttributeValues(attr_changes):
            raise QgsProcessingException(self.tr("Erro ao atualizar campo Name."))

        commit_step("Campo Name atualizado com sucesso (PT-<id>).")

        # -------------------------------
        # 4) Atualizar Lat/Long
        # -------------------------------
        idx_lat = layer.fields().indexFromName('Latitude')
        idx_lon = layer.fields().indexFromName('Longitude')
        attr_changes = {}
        for fid, lat, lon in pontos:
            attr_changes[fid] = {idx_lat: round(lat, 2), idx_lon: round(lon, 2)}

        start_editing()
        if not dp.changeAttributeValues(attr_changes):
            raise QgsProcessingException(self.tr("Erro ao atualizar campos Lat/Long."))

        commit_step("Coordenadas Lat/Long atualizadas com sucesso.")

        return {}

    # Metadados
    def name(self):
        return 'adicionar_atributos_ficha_step'
    def displayName(self):
        return self.tr('Inicializar Atributos da Ficha de Prospecção')
    def group(self):
        return 'Adicionar Atributo'
    def groupId(self):
        return 'adicionar_atributo'
    def createInstance(self):
        return AddRecordAttributes()
    def shortHelpString(self):
        return self.tr("""
        Estrutura uma camada de pontos para ficha arqueológica.
        Remove e recria campos padronizados, redefine IDs, atualiza Name e sobrescreve Latitude/Longitude.
        """)
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
