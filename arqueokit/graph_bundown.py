# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Gráfico Burndown Temporal
 Autor: Geraldo Pereira de Morais Júnior
 Email: geraldo.pmj@gmail.com
 ***********************************************/
"""

__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-07-25'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterDateTime,
    QgsProcessingParameterString,
    QgsProcessingParameterFileDestination
)
from qgis.PyQt.QtCore import QCoreApplication
import pandas as pd
import matplotlib.pyplot as plt


class BurndownTemporal(QgsProcessingAlgorithm):

    CAMADA = 'CAMADA'
    ATRIBUTO_DATA = 'ATRIBUTO_DATA'
    DATA_INICIO = 'DATA_INICIO'
    DATA_FIM = 'DATA_FIM'
    TITLE = 'TITLE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.CAMADA,
                'Camada',
                [QgsProcessing.TypeVectorPoint]
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.ATRIBUTO_DATA,
                'Atributo de data',
                parentLayerParameterName=self.CAMADA
            )
        )

        self.addParameter(
            QgsProcessingParameterDateTime(
                self.DATA_INICIO,
                'Data de início'
            )
        )

        self.addParameter(
            QgsProcessingParameterDateTime(
                self.DATA_FIM,
                'Data de término'
            )
        )

        self.addParameter(QgsProcessingParameterString(
            self.TITLE, 'Título do Gráfico', defaultValue='Burndown Temporal da Prospecção '))

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                'Salvar gráfico como PNG',
                fileFilter='Imagem PNG (*.png)'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        camada = self.parameterAsSource(parameters, self.CAMADA, context)
        campo_data = self.parameterAsString(parameters, self.ATRIBUTO_DATA, context)

        # Datas definidas pelo usuário
        data_inicio = self.parameterAsDateTime(parameters, self.DATA_INICIO, context).toPyDateTime()
        data_fim = self.parameterAsDateTime(parameters, self.DATA_FIM, context).toPyDateTime()

        title = self.parameterAsString(parameters, self.TITLE, context)
        output_path = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        # Lista todas as feições (não consumir iterador duas vezes)
        features = list(camada.getFeatures())
        total_pontos = len(features)

        # Extrai datas
        datas = []
        for f in features:
            d = f[campo_data]
            if d:
                # converte tipos possíveis para datetime.date
                if hasattr(d, 'toPyDate'):
                    datas.append(d.toPyDate())
                elif hasattr(d, 'toPyDateTime'):
                    datas.append(d.toPyDateTime())
                else:
                    datas.append(pd.to_datetime(d, dayfirst=True, errors='coerce'))

        # DataFrame com datas normalizadas (remove hora)
        df = pd.DataFrame(datas, columns=['data'])
        df['data'] = pd.to_datetime(df['data'], errors='coerce').dt.normalize()

        # Normaliza início e fim
        data_inicio = pd.to_datetime(data_inicio).normalize()
        data_fim = pd.to_datetime(data_fim).normalize()

        # Cria série completa de datas
        todas_datas = pd.date_range(data_inicio, data_fim, freq='D')

        # Conta quantos pontos foram feitos em cada data
        contagem = df.groupby('data').size()

        # Descobre a última data com ponto realizado
        if not contagem.empty:
            ultima_data_realizada = contagem.index.max()
        else:
            ultima_data_realizada = data_inicio  # fallback caso não tenha pontos feitos

        # Reindexa até a última data realizada (não vai até data_fim)
        datas_real = pd.date_range(data_inicio, ultima_data_realizada, freq='D')

        realizados_cum = contagem.reindex(datas_real, fill_value=0).cumsum()
        restantes = total_pontos - realizados_cum

        # Logs
        feedback.pushInfo(f"Total de pontos planejados: {total_pontos}")
        feedback.pushInfo(f"Pontos realizados até {data_fim.date()}: {realizados_cum.max()}")
        feedback.pushInfo(f"Pontos restantes: {restantes.iloc[-1]}")

        # Linha ideal: decresce linearmente até 0
        ideal = pd.Series(
            [total_pontos - (i * total_pontos / (len(todas_datas) - 1))
             for i in range(len(todas_datas))],
            index=todas_datas
        )

        # Plota
        plt.figure(figsize=(10, 6))
        plt.plot(ideal.index, ideal.values, color='blue', label='Ideal Burndown', linewidth=2)
        plt.plot(restantes.index, restantes.values, color='orange', label='Burndown Real', linewidth=2)
        plt.margins(x=0)
        plt.ylim(top=total_pontos, bottom=0)
        plt.xlim(left=data_inicio)
        plt.xticks(rotation=30)
        plt.ylabel('Pontos restantes')
        plt.xlabel('Data')
        plt.title(title)
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()
        plt.savefig(output_path, dpi=450)
        plt.close()

        feedback.pushInfo(f"Gráfico Burndown salvo em: {output_path}")

        return {self.OUTPUT: output_path}

    def tr(self, string):
        return QCoreApplication.translate('burndown_temporal', string)

    def createInstance(self):
        return BurndownTemporal()

    def name(self):
        return 'burndown_temporal'

    def displayName(self):
        return self.tr('Gráfico Burndown Temporal')

    def group(self):
        return self.tr('Gráficos')

    def groupId(self):
        return 'graficos'

    def shortHelpString(self):
        return self.tr("Gera um gráfico de Burndown com base em um campo de data, "
                       "comparando a curva ideal e a curva real.")
