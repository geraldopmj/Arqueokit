# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Update (estilo ArcGIS)
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
    QgsProcessingException
)
import processing


class update_like_arcgis(QgsProcessingAlgorithm):
    """
    Emula o comportamento da ferramenta Update do ArcGIS para camadas poligonais,
    utilizando Intersection + Difference + Merge, com:
      - harmonização de schema (apenas campos da camada de entrada na saída);
      - opção de tratamento das bordas (aproximação do parâmetro 'Borders').
    """

    ENTRADA = 'ENTRADA'
    ATUALIZACAO = 'ATUALIZACAO'
    SAIDA = 'SAIDA'
    BORDAS = 'BORDAS'

    # --------------------------------------------------------
    # **** Definição de parâmetros ****
    # --------------------------------------------------------
    def initAlgorithm(self, config=None):
        # Camada de entrada: será parcialmente substituída.
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.ENTRADA,
                self.tr('Camada de entrada (polígonos)'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        # Camada de atualização: fornece geometrias (e atributos) que substituirão
        # a entrada nas áreas de sobreposição.
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.ATUALIZACAO,
                self.tr('Camada de atualização (polígonos)'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        # Modo de tratamento das bordas (aproximação de 'Borders').
        # 0 = Manter bordas (comportamento padrão)
        # 1 = Remover bordas internas quando atributos coincidirem (Dissolve por todos os campos)
        self.addParameter(
            QgsProcessingParameterEnum(
                self.BORDAS,
                self.tr('Tratamento das bordas'),
                options=[
                    self.tr('Manter bordas'),
                    self.tr('Remover bordas quando atributos coincidirem (aprox. NO_BORDERS)')
                ],
                defaultValue=0
            )
        )

        # Camada de saída (nova camada gerada).
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.SAIDA,
                self.tr('Camada de saída (Update)'),
                type=QgsProcessing.TypeVectorPolygon
            )
        )

    # --------------------------------------------------------
    # **** Utilitário interno: garantir QgsVectorLayer ****
    # --------------------------------------------------------
    def _as_layer(self, value, context):
        """
        Converte o valor retornado por processing.run (ID ou layer)
        em QgsVectorLayer; lança exceção se não conseguir.
        Usar APENAS para saídas temporárias (QgsProcessing.TEMPORARY_OUTPUT).
        """
        # Se já é camada, retorna direto
        if hasattr(value, 'fields'):
            return value
        # Se é string, presume ID de camada no contexto
        if isinstance(value, str):
            lyr = context.getMapLayer(value)
            if lyr is None:
                raise QgsProcessingException(
                    self.tr('Não foi possível recuperar camada intermediária (ID: {})').format(value)
                )
            return lyr
        # Qualquer outra coisa é anômala
        raise QgsProcessingException(
            self.tr('Tipo de saída intermediária inesperado: {}').format(type(value))
        )

    # --------------------------------------------------------
    # **** Núcleo do algoritmo ****
    # --------------------------------------------------------
    def processAlgorithm(self, parameters, context, feedback):
        # 1) Obter camadas
        entrada = self.parameterAsVectorLayer(parameters, self.ENTRADA, context)
        atualizacao = self.parameterAsVectorLayer(parameters, self.ATUALIZACAO, context)

        if not entrada or not entrada.isValid():
            raise QgsProcessingException(self.tr('Camada de entrada inválida.'))
        if not atualizacao or not atualizacao.isValid():
            raise QgsProcessingException(self.tr('Camada de atualização inválida.'))

        # 2) Parâmetros auxiliares
        modo_bordas = self.parameterAsEnum(parameters, self.BORDAS, context)
        saida_path = self.parameterAsOutputLayer(parameters, self.SAIDA, context)

        # ----------------------------------------------------
        # **** Etapa 1: Intersection(ATUALIZACAO, ENTRADA) ****
        # ----------------------------------------------------
        feedback.pushInfo(self.tr(
            'Executando Intersection (recortando camada de atualização pela entrada)...'
        ))

        inter_res = processing.run(
            'native:intersection',
            {
                'INPUT': atualizacao,
                'OVERLAY': entrada,
                'INPUT_FIELDS_PREFIX': '',
                'OVERLAY_FIELDS_PREFIX': 'in_',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )
        atualizacao_clip = self._as_layer(inter_res['OUTPUT'], context)

        # ----------------------------------------------------
        # **** Etapa 1b: Harmonização de schema (campos) ****
        # ----------------------------------------------------
        feedback.pushInfo(self.tr(
            'Harmonizando schema: saída terá apenas os campos da camada de entrada...'
        ))

        entrada_fields = entrada.fields()
        atualizacao_fields = {f.name(): f for f in atualizacao_clip.fields()}

        fields_mapping = []
        for f in entrada_fields:
            nome = f.name()
            if nome in atualizacao_fields:
                expr = '"{}"'.format(nome.replace('"', '""'))
            else:
                expr = 'NULL'

            fields_mapping.append({
                'expression': expr,
                'name': nome,
                'type': f.type(),
                'length': f.length(),
                'precision': f.precision()
            })

        ref_res = processing.run(
            'native:refactorfields',
            {
                'INPUT': atualizacao_clip,
                'FIELDS_MAPPING': fields_mapping,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )
        atualizacao_ref = self._as_layer(ref_res['OUTPUT'], context)

        # ----------------------------------------------------
        # **** Etapa 2: Difference(ENTRADA, ATUALIZACAO) ****
        # ----------------------------------------------------
        feedback.pushInfo(self.tr(
            'Executando Difference (removendo área a ser atualizada da entrada)...'
        ))

        diff_res = processing.run(
            'native:difference',
            {
                'INPUT': entrada,
                'OVERLAY': atualizacao,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )
        entrada_diff = self._as_layer(diff_res['OUTPUT'], context)

        # ----------------------------------------------------
        # **** Etapa 3: Merge(entrada_diff + atualizacao_ref) ****
        # ----------------------------------------------------
        feedback.pushInfo(self.tr(
            'Mesclando área remanescente da entrada com a atualização recortada (Merge)...'
        ))

        # Se for aplicar dissolução posterior (modo_bordas == 1),
        # usamos saída temporária aqui; caso contrário, já escrevemos na saída final.
        merge_output_target = (
            QgsProcessing.TEMPORARY_OUTPUT
            if modo_bordas == 1
            else saida_path
        )

        merge_res = processing.run(
            'native:mergevectorlayers',
            {
                'LAYERS': [entrada_diff, atualizacao_ref],
                'CRS': entrada.crs(),
                'OUTPUT': merge_output_target
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )

        # ----------------------------------------------------
        # **** Etapa 4: Tratamento das bordas (opcional) ****
        # ----------------------------------------------------
        if modo_bordas == 1:
            camada_merge = self._as_layer(merge_res['OUTPUT'], context)

            feedback.pushInfo(self.tr(
                'Removendo bordas internas quando atributos coincidirem (Dissolve por todos os campos)...'
            ))
            campos = [f.name() for f in camada_merge.fields()]

            dissol_res = processing.run(
                'native:dissolve',
                {
                    'INPUT': camada_merge,
                    'FIELD': campos,
                    'SEPARATE_DISJOINT': False,
                    'OUTPUT': saida_path
                },
                context=context,
                feedback=feedback,
                is_child_algorithm=True
            )
            # Para saída final em arquivo não precisamos converter para layer:
            camada_saida = dissol_res['OUTPUT']
        else:
            # Sem tratamento adicional de bordas: saída final já é o resultado do merge.
            camada_saida = merge_res['OUTPUT']

        feedback.pushInfo(self.tr('Update (estilo ArcGIS) concluído.'))

        return {self.SAIDA: camada_saida}

    def name(self):
        return 'update_like_arcgis'

    def displayName(self):
        return self.tr('Atualizar')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Geoprocessamento'

    def createInstance(self):
        return update_like_arcgis()

    def shortHelpString(self):
        return self.tr("""A camada de entrada é recortada na área coberta pela camada de atualização, e em seguida as feições da camada de atualização recortadas pela entrada são inseridas na saída, substituindo geometricamente a área removida.""")

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
