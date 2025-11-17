# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Soma de atributos por feição (com campo de rótulo)
 Autor: Geraldo Pereira de Morais Júnior
 ***********************************************/
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterString,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFileDestination
)
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


class FeatureSumPlot(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    LABEL_FIELD = 'LABEL_FIELD'
    ATTR1 = 'ATTR1'
    ATTR2 = 'ATTR2'
    ATTR3 = 'ATTR3'
    ATTR4 = 'ATTR4'
    ATTR5 = 'ATTR5'
    TITLE = 'TITLE'
    PALETTE = 'PALETTE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        # Camada
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, 'Camada vetorial', [QgsProcessing.TypeVectorAnyGeometry]))

        # Campo para rótulo (opcional)
        self.addParameter(QgsProcessingParameterField(
            self.LABEL_FIELD,
            'Atributo para rótulos no eixo X',
            parentLayerParameterName=self.INPUT,
            optional=True
        ))

        # Até 5 atributos numéricos
        for i in range(1, 6):
            self.addParameter(QgsProcessingParameterField(
                getattr(self, f'ATTR{i}'),
                f'Atributo Numérico {i}',
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.Numeric,
                optional=(i > 2)  # os 2 primeiros obrigatórios
            ))

        self.addParameter(QgsProcessingParameterEnum(
            self.PALETTE, 'Paleta de cores (Seaborn)',
            options=['deep', 'muted', 'pastel', 'dark', 'colorblind', 'bright',
                     'viridis', 'plasma', 'inferno', 'magma', 'cividis',
                     'coolwarm', 'Spectral', 'Blues', 'Greens', 'Reds'],
            defaultValue=0
        ))

        self.addParameter(QgsProcessingParameterString(
            self.TITLE, 'Título do Gráfico', defaultValue='Soma por Feição'))

        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT, 'Salvar gráfico (PNG)', fileFilter='PNG files (*.png)'))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsSource(parameters, self.INPUT, context)
        label_field = self.parameterAsString(parameters, self.LABEL_FIELD, context)

        # Campos selecionados
        fields = [self.parameterAsString(parameters, getattr(self, f'ATTR{i}'), context)
                  for i in range(1, 6)]
        fields = [f for f in fields if f]

        if len(fields) < 2:
            raise Exception("Selecione ao menos 2 atributos.")

        title = self.parameterAsString(parameters, self.TITLE, context)
        palette_list = ['deep', 'muted', 'pastel', 'dark', 'colorblind', 'bright',
                        'viridis', 'plasma', 'inferno', 'magma', 'cividis',
                        'coolwarm', 'Spectral', 'Blues', 'Greens', 'Reds']
        palette = palette_list[self.parameterAsEnum(parameters, self.PALETTE, context)]
        output_path = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        # Extrai dados e soma por feição
        data = []
        for feat in layer.getFeatures():
            valores = [feat[f] for f in fields if feat[f] is not None]
            if valores:
                valor_total = sum(valores)
                if label_field and feat[label_field] is not None:
                    label = str(feat[label_field])
                else:
                    label = f'ID {feat.id()}'
                data.append({'Feição': label, 'Valor': valor_total})

        if not data:
            raise Exception("Não foram encontrados dados válidos para os atributos selecionados.")

        # DataFrame e ordena pelo maior valor
        df = pd.DataFrame(data).sort_values('Valor', ascending=False)

        # Plot
        sns.set(style="whitegrid")
        plt.figure(figsize=(max(6, len(df) * 0.6), 10))
        sns.barplot(x='Feição', y='Valor', data=df, palette=palette)
        plt.title(title)
        plt.ylabel('Soma')
        plt.xlabel('Feições')
        plt.xticks(rotation=90)
        plt.grid(axis='y', linestyle='--', linewidth=0.5, alpha=0.4)
        plt.tight_layout()
        plt.savefig(output_path, dpi=450)
        plt.close()

        feedback.pushInfo(f"Gráfico salvo em: {output_path}")
        return {self.OUTPUT: output_path}

    def name(self):
        return 'feature_sum_plot'

    def displayName(self):
        return 'Soma de Atributos por Feição'

    def group(self):
        return 'Gráficos'

    def groupId(self):
        return 'graficos'

    def createInstance(self):
        return FeatureSumPlot()

    def shortHelpString(self):
        return (
            "Gera um gráfico de barras mostrando a soma dos atributos "
            "numéricos selecionados, agrupados por feição. "
            "É possível escolher um atributo para rótulo no eixo X."
        )
