
# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Geração de Grade Ótima (modo somente análise)
 Autor: Geraldo Pereira de Morais Júnior
 Email: geraldo.pmj@gmail.com
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

class AttributeAggregationPlot(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    ATTR1 = 'ATTR1'
    ATTR2 = 'ATTR2'
    ATTR3 = 'ATTR3'
    ATTR4 = 'ATTR4'
    ATTR5 = 'ATTR5'
    LABELS = 'LABELS'
    MODE = 'MODE'
    PALETTE = 'PALETTE'
    TITLE = 'TITLE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, 'Input vector layer', [QgsProcessing.TypeVectorAnyGeometry]))

        self.addParameter(QgsProcessingParameterField(
            self.ATTR1,
            'Atributo Numérico 1',
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            optional=False
        ))

        self.addParameter(QgsProcessingParameterField(
            self.ATTR2,
            'Atributo Numérico 2',
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            optional=False
        ))

        self.addParameter(QgsProcessingParameterField(
            self.ATTR3,
            'Atributo Numérico 3',
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            optional=True
        ))

        self.addParameter(QgsProcessingParameterField(
            self.ATTR4,
            'Atributo Numérico 4',
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            optional=True
        ))
        
        self.addParameter(QgsProcessingParameterField(
            self.ATTR5,
            'Atributo Numérico 5',
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            optional=True
        ))

        self.addParameter(QgsProcessingParameterString(
            self.LABELS, 'Rótulos para Atributos (separado por vírgula)', defaultValue='Camada 1, Camada 2'))

        self.addParameter(QgsProcessingParameterEnum(
            self.MODE, 'Método de Cálculo', options=['Soma', 'Média'], defaultValue=0))

        self.addParameter(
            QgsProcessingParameterEnum(
                'PALETTE',
                'Paleta de cores (Seaborn)',
                options=['deep', 'muted', 'pastel', 'dark', 'colorblind', 'bright',
                         'viridis', 'plasma', 'inferno', 'magma', 'cividis',
                         'coolwarm', 'Spectral', 'Blues', 'Greens', 'Reds'],
                defaultValue=0
            )
        )

        self.addParameter(QgsProcessingParameterString(
            self.TITLE, 'Plot title', defaultValue='Attribute Comparison'))

        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT, 'Output image (PNG)', fileFilter='PNG files (*.png)'))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsSource(parameters, self.INPUT, context)
        fields = [
            self.parameterAsString(parameters, self.ATTR1, context),
            self.parameterAsString(parameters, self.ATTR2, context),
            self.parameterAsString(parameters, self.ATTR3, context),
            self.parameterAsString(parameters, self.ATTR4, context),
            self.parameterAsString(parameters, self.ATTR5, context)
        ]
        fields = [f for f in fields if f]

        if not fields:
            raise Exception("Ao menos dois atributos precisam ser selecionados.")

        labels_raw = self.parameterAsString(parameters, self.LABELS, context)
        labels_list = [s.strip() for s in labels_raw.split(',')]
        labels = dict(zip(fields, labels_list)) if len(labels_list) == len(fields) else {f: f for f in fields}

        mode = self.parameterAsEnum(parameters, self.MODE, context)
        title = self.parameterAsString(parameters, self.TITLE, context)
        palette_list = ['deep', 'muted', 'pastel', 'dark', 'colorblind', 'bright',
                'viridis', 'plasma', 'inferno', 'magma', 'cividis',
                'coolwarm', 'Spectral', 'Blues', 'Greens', 'Reds']

        palette_index = self.parameterAsEnum(parameters, 'PALETTE', context)
        palette = palette_list[palette_index]
        output_path = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        data = []
        field_names = [f.name() for f in layer.fields()]
        for feat in layer.getFeatures():
            values = dict(zip(field_names, feat.attributes()))
            row = {f: values.get(f) for f in fields}
            if all(row[f] is not None for f in fields):
                data.append(row)

        if not data:
            raise Exception("No valid data found for selected fields.")

        df = pd.DataFrame(data)
        results = df.sum() if mode == 0 else df.mean()
        results = results[fields]  # Ensure field order
        
        n_fields = len(fields)

        plot_df = pd.DataFrame({
            'Field': [labels.get(f, f) for f in fields],
            'Value': results.values
        })

        sns.set(style="whitegrid")
        plt.figure(figsize=(n_fields*2, 10))
        sns.barplot(x='Field', y='Value', data=plot_df, palette=palette)
        plt.title(title)
        plt.ylabel('Soma' if mode == 0 else 'Média')
        plt.xlabel('Atributos')
        plt.grid(axis='y', linestyle='--', linewidth=0.5, alpha=0.4)
        plt.tight_layout()
        plt.savefig(output_path, dpi=450)
        plt.close()

        feedback.pushInfo(f"Plot saved to: {output_path}")
        return {self.OUTPUT: output_path}

    def name(self):
        return 'attribute_aggregation_plot'

    def displayName(self):
        return 'Soma ou Média comparando até 5 Atributos'

    def group(self):
        return 'Gráficos'

    def groupId(self):
        return 'graficos'

    def createInstance(self):
        return AttributeAggregationPlot()
        
    def shortHelpString(self):
        return (
            "Generates a bar plot comparing up to 4 numeric attributes of a vector layer.\n"
            "You can choose between summing or averaging the values.\n"
            "Labels and color palette are customizable. The plot is saved as a PNG image."
            "You can see the color palette at "
            "https://r02b.github.io/seaborn_palettes/#named-seaborn-palettes-by-category"
        )
