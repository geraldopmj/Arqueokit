
# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Geração de Grade Ótima (modo somente análise)
 Autor: Geraldo Pereira de Morais Júnior
 Email: geraldo.pmj@gmail.com
 ***********************************************/
"""

__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-07-19'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterString,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFileDestination
)
from qgis.PyQt.QtCore import QCoreApplication
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

class CountUniqueAttribute(QgsProcessingAlgorithm):

    CAMADA = 'CAMADA'
    ATRIBUTO = 'ATRIBUTO'
    TITLE = 'TITLE'
    PALETA = 'PALETA'   
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.CAMADA,
                'Camada vetorial',
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.ATRIBUTO,
                'Campo categórico',
                parentLayerParameterName=self.CAMADA
            )
        )
        
        self.addParameter(QgsProcessingParameterString(
            self.TITLE, 'Título do Gráfico', defaultValue=f''))
        
        self.addParameter(
            QgsProcessingParameterEnum(
                'PALETA',
                'Paleta de cores (Seaborn)',
                options=['deep', 'muted', 'pastel', 'dark', 'colorblind', 'bright',
                         'viridis', 'plasma', 'inferno', 'magma', 'cividis',
                         'coolwarm', 'Spectral', 'Blues', 'Greens', 'Reds'],
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                'Salvar gráfico como PNG',
                fileFilter='Imagem PNG (*.png)'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        camada = self.parameterAsSource(parameters, self.CAMADA, context)
        atributo = self.parameterAsString(parameters, self.ATRIBUTO, context)
        title = self.parameterAsString(parameters, self.TITLE, context)
        paletas = ['deep', 'muted', 'pastel', 'dark', 'colorblind', 'bright',
           'viridis', 'plasma', 'inferno', 'magma', 'cividis',
           'coolwarm', 'Spectral', 'Blues', 'Greens', 'Reds']

        paleta_index = self.parameterAsEnum(parameters, 'PALETA', context)
        paleta = paletas[paleta_index]
        output_path = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        valores = [str(f[atributo]) for f in camada.getFeatures() if f[atributo] is not None]
        df = pd.DataFrame(valores, columns=[atributo])
        contagem = df[atributo].value_counts().sort_values(ascending=False)

        plt.figure(figsize=(len(contagem)*2, 10))
        sns.barplot(x=contagem.index, y=contagem.values, palette=paleta)
        plt.title(title)
        plt.xlabel('Categoria')
        plt.ylabel('Frequência')
        plt.grid(True, linestyle='--', linewidth=0.5, alpha=0.4)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(output_path, dpi=450)
        plt.close()

        feedback.pushInfo(f"Gráfico salvo em: {output_path}")

        return {self.OUTPUT: output_path}

    def tr(self, string):
        return QCoreApplication.translate('count_unique_attribute', string)

    def createInstance(self):
        return CountUniqueAttribute()

    def name(self):
        return 'contagem_categorias_grafico'

    def displayName(self):
        return self.tr('Contagem de Valores Únicos em Atributo')

    def group(self):
        return self.tr('Gráficos')

    def groupId(self):
        return 'graficos'

    def shortHelpString(self):
        return self.tr("Conta quantos valores únicos existem em um campo categórico e plota o resultado com seaborn/matplotlib."
                       "You can see the color palette at "
                       "https://r02b.github.io/seaborn_palettes/#named-seaborn-palettes-by-category")

    
