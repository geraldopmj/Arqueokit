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
    QgsProcessingException,
    QgsProject
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

        # Definição do Esquema
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
            field_defs[f'prof_C{c}'] = QVariant.Double
            field_defs[f'solo_C{c}'] = QVariant.String
            field_defs[f'vstg_C{c}'] = QVariant.String
            field_defs[f'type_vstgC{c}'] = QVariant.String
            field_defs[f'qnt_vstgC{c}'] = QVariant.Int

        for f in ['foto1', 'foto2', 'foto3', 'foto4']:
            field_defs[f] = QVariant.String

        if not layer.isEditable():
            layer.startEditing()

        feedback.pushInfo("Verificando estrutura de campos...")
        
        current_field_names = [f.name() for f in layer.fields()]
        new_fields = []

        for name, qtype in field_defs.items():
            if name not in current_field_names:
                new_fields.append(QgsField(name, qtype))
            else:
                # Opcional: Validar se o tipo confere, mas para evitar crash, apenas ignoramos
                feedback.pushInfo(f"Campo '{name}' já existe. Mantido.")

        if new_fields:
            if not dp.addAttributes(new_fields):
                raise QgsProcessingException(self.tr("Erro ao adicionar novos campos em lote."))
            layer.updateFields() # Crucial para atualizar os índices locais
            feedback.pushInfo(f"{len(new_fields)} novos campos adicionados.")
        else:
            feedback.pushInfo("Nenhum campo novo necessário.")

        feedback.pushInfo("Calculando geometria e ordenação...")
        
        pontos = []
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                p = geom.asPoint()
                pontos.append((feat.id(), p.y(), p.x()))

        if not pontos:
            raise QgsProcessingException(self.tr("A camada não contém feições válidas."))

        # Ordenação NW -> SE (Maior Y, Menor X? Ajuste conforme sua lógica. Aqui: Cima->Baixo, Esq->Dir)
        # Sua lógica original: (-x[1], x[2]) -> Decrescente Y (Norte para Sul), Crescente X (Oeste para Leste)
        pontos.sort(key=lambda x: (-x[1], x[2]))

        fields = layer.fields()
        try:
            idx_id = fields.indexFromName('id')
            idx_name = fields.indexFromName('Name')
            idx_lat = fields.indexFromName('Latitude') 
            idx_lon = fields.indexFromName('Longitude')
        except KeyError:
             raise QgsProcessingException(self.tr("Erro ao recuperar índices dos campos criados."))

        attr_changes = {}
        
        for ordem, (fid, lat, lon) in enumerate(pontos, start=1):
            attr_map = {
                idx_id: ordem,
                idx_name: f"PT-{ordem}", # Usando a ordem sequencial, não o FID original, para manter consistência
                idx_lat: round(lat, 2), 
                idx_lon: round(lon, 2)
            }
            attr_changes[fid] = attr_map

        if attr_changes:
            feedback.pushInfo(f"Atualizando atributos de {len(attr_changes)} feições...")
            if not dp.changeAttributeValues(attr_changes):
                raise QgsProcessingException(self.tr("Erro ao comitar valores dos atributos."))
        
        if layer.isEditable():
            if not layer.commitChanges():
                layer.rollBack()
                raise QgsProcessingException(self.tr("Erro ao salvar alterações no disco. Verifique permissões ou bloqueios."))
            feedback.pushInfo("Alterações salvas com sucesso.")

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
