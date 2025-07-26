# -*- coding: utf-8 -*-

"""
/***********************************************
 Arqueokit - QGIS Plugin
 GIS algorithms for Archaeologists
 Author: Geraldo Pereira de Morais Júnior
 Email: geraldo.pmj@gmail.com
 ***********************************************/
"""

__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-07-20'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsVectorLayer,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsProcessingException,
    Qgis
)
import requests

class FunaiDownloader(QgsProcessingAlgorithm):

    CAMADAS = 'CAMADAS'

    def initAlgorithm(self, config=None):
        self.options = [
            "Aldeias Indígenas (pontos)",
            "Terras Indígenas Amazônia Legal (poligonais)",
            "Coordenações Regionais - CR (pontos)",
            "Coordenações Técnicas Locais - CTL (pontos)",
            "Terras Indígenas (poligonais)",
            "Terras Indígenas com Portarias (poligonais)",
            "Terras Indígenas em Estudo (pontos)",
            "Terras Indígenas em Estudo com Portarias (pontos)"
        ]

        self.links = {
            "Aldeias Indígenas (pontos)": "https://geoserver.funai.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=Funai:aldeias_pontos&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Terras Indígenas Amazônia Legal (poligonais)": "https://geoserver.funai.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=Funai:tis_amazonia_legal_poligonais&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Coordenações Regionais - CR (pontos)": "https://geoserver.funai.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=Funai:tis_cr&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Coordenações Técnicas Locais - CTL (pontos)": "https://geoserver.funai.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=Funai:tis_ctl&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Terras Indígenas (poligonais)": "https://geoserver.funai.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=Funai:tis_poligonais&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Terras Indígenas com Portarias (poligonais)": "https://geoserver.funai.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=Funai:tis_poligonais_portarias&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Terras Indígenas em Estudo (pontos)": "https://geoserver.funai.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=Funai:tis_pontos&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Terras Indígenas em Estudo com Portarias (pontos)": "https://geoserver.funai.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=Funai:tis_pontos_portarias&maxFeatures=2147483647&outputFormat=application%2Fjson"
        }

        self.addParameter(
            QgsProcessingParameterEnum(
                self.CAMADAS,
                'Selecionar camadas da FUNAI para download',
                options=self.options,
                defaultValue=0,
                allowMultiple=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        indices = self.parameterAsEnums(parameters, self.CAMADAS, context)
        selecionadas = [self.options[i] for i in indices]
        
        test_url = "https://geoserver.funai.gov.br/geoserver/ows"
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(test_url, headers=headers, timeout=5, stream=True)
            if response.status_code != 200:
                raise Exception(f'Servidor respondeu com status {response.status_code}')
        except Exception as e:
            feedback.reportError(f"Erro ao conectar ao servidor da FUNAI: {e}")
            raise QgsProcessingException("Servidor da FUNAI indisponível. Tente novamente mais tarde.")


        for i, nome in enumerate(selecionadas):
            url = self.links[nome]
            feedback.pushInfo(f'Baixando camada: {nome}')

            layer = QgsVectorLayer(url, nome, "ogr")
            if not layer.isValid():
                feedback.reportError(f'Erro ao carregar: {nome}')
                continue

            layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4674"))
            QgsProject.instance().addMapLayer(layer)

            progresso = int((i + 1) / len(selecionadas) * 100)
            feedback.setProgress(progresso)

        return {}

    def name(self):
        return 'funai_downloader'

    def displayName(self):
        return self.tr('Download de Camadas da FUNAI')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'FUNAI'

    def createInstance(self):
        return FunaiDownloader()

    def shortHelpString(self):
        return self.tr("""
        Este algoritmo permite baixar e carregar diretamente no QGIS diversas camadas disponibilizadas pela FUNAI (via WFS - GeoJSON).
        As camadas selecionadas são adicionadas ao projeto com o sistema de referência SIRGAS 2000 (EPSG:4674).
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
