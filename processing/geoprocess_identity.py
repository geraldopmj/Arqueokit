# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Identity (estilo ArcGIS)
 Autor: Geraldo Pereira de Morais Júnior
 ***********************************************/
"""

__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-11-24'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProcessingException
)
import processing


class identity_like_arcgis(QgsProcessingAlgorithm):
    """
    Emula, para camadas poligonais, o comportamento geral da ferramenta
    Identity do ArcGIS, utilizando Intersection + Difference + Merge.
    Oferece um controle análogo ao 'Attributes To Join' para os campos
    provenientes da camada identidade.
    """

    ENTRADA = 'ENTRADA'
    IDENTIDADE = 'IDENTIDADE'
    SAIDA = 'SAIDA'
    MODO_ATRIBUTOS = 'MODO_ATRIBUTOS'
    CAMPO_ID_IDENTIDADE = 'CAMPO_ID_IDENTIDADE'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.ENTRADA,
                self.tr('Camada de entrada (polígonos)'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.IDENTIDADE,
                self.tr('Camada identidade (polígonos)'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.MODO_ATRIBUTOS,
                self.tr('Atributos da identidade a associar'),
                options=[
                    self.tr('Todos os atributos da identidade'),
                    self.tr('Somente campo de ID da identidade'),
                    self.tr('Nenhum atributo da identidade')
                ],
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.CAMPO_ID_IDENTIDADE,
                self.tr('Campo de ID da camada identidade (para modo "Somente campo de ID")'),
                parentLayerParameterName=self.IDENTIDADE,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.SAIDA,
                self.tr('Camada de saída (Identity)'),
                type=QgsProcessing.TypeVectorPolygon
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        entrada = self.parameterAsVectorLayer(parameters, self.ENTRADA, context)
        identidade = self.parameterAsVectorLayer(parameters, self.IDENTIDADE, context)

        if not entrada or not entrada.isValid():
            raise QgsProcessingException(self.tr('Camada de entrada inválida.'))
        if not identidade or not identidade.isValid():
            raise QgsProcessingException(self.tr('Camada identidade inválida.'))

        modo_atrib = self.parameterAsEnum(parameters, self.MODO_ATRIBUTOS, context)
        campo_id_identidade = self.parameterAsString(parameters, self.CAMPO_ID_IDENTIDADE, context)

        if modo_atrib == 1 and not campo_id_identidade:
            raise QgsProcessingException(
                self.tr('Modo "Somente campo de ID" exige a seleção de um campo de ID da camada identidade.')
            )

        saida_path = self.parameterAsOutputLayer(parameters, self.SAIDA, context)


        feedback.pushInfo(self.tr('Executando Intersection (parte em comum)...'))

        inter_res = processing.run(
            'native:intersection',
            {
                'INPUT': entrada,
                'OVERLAY': identidade,

                'INPUT_FIELDS_PREFIX': '',
                'OVERLAY_FIELDS_PREFIX': 'id_',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )
        camada_inter = inter_res['OUTPUT']

        if modo_atrib in (1, 2):
            feedback.pushInfo(self.tr('Ajustando atributos da identidade conforme o modo selecionado...'))

            all_fields = [f.name() for f in camada_inter.fields()]
            id_fields = [n for n in all_fields if n.startswith('id_')]

            campos_remover = []

            if modo_atrib == 2:

                campos_remover = id_fields

            elif modo_atrib == 1:

                id_field_prefixed = 'id_' + campo_id_identidade
                for f in id_fields:
                    if f != id_field_prefixed:
                        campos_remover.append(f)

            if campos_remover:
                del_res = processing.run(
                    'native:deletecolumn',
                    {
                        'INPUT': camada_inter,
                        'COLUMN': campos_remover,
                        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                    },
                    context=context,
                    feedback=feedback,
                    is_child_algorithm=True
                )
                camada_inter = del_res['OUTPUT']

        feedback.pushInfo(self.tr('Executando Difference (parte exclusiva da entrada)...'))

        diff_res = processing.run(
            'native:difference',
            {
                'INPUT': entrada,
                'OVERLAY': identidade,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )
        camada_diff = diff_res['OUTPUT']

        feedback.pushInfo(self.tr('Mesclando resultados (Merge)...'))

        merge_res = processing.run(
            'native:mergevectorlayers',
            {
                'LAYERS': [camada_inter, camada_diff],
                'CRS': entrada.crs(),
                'OUTPUT': saida_path
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )

        feedback.pushInfo(self.tr('Identity (estilo ArcGIS) concluído (modo poligonal).'))

        return {self.SAIDA: merge_res['OUTPUT']}


    def name(self):
        return 'identity_like_arcgis'

    def displayName(self):
        return self.tr('Identidade')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Geoprocessamento'

    def createInstance(self):
        return identity_like_arcgis()

    def shortHelpString(self):
        return self.tr("""
        **** Descrição ****
        A camada de entrada é fragmentada segundo os limites da camada identidade, preservando seus atributos e incorporando os atributos da identidade nas áreas de interseção.""")

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
