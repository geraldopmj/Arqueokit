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

from qgis.PyQt.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsVectorLayer,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsProcessingException,
    Qgis,
    QgsNetworkAccessManager
)

class IphanDownloader(QgsProcessingAlgorithm):

    CAMADAS = 'CAMADAS'

    @staticmethod
    def _check_service_available(url, timeout_ms=5000):
        def enum_value(value):
            if hasattr(value, "value"):
                return value.value
            try:
                return int(value)
            except (TypeError, ValueError):
                return value

        http_status_attr = getattr(QNetworkRequest, "HttpStatusCodeAttribute", None)
        if http_status_attr is None and hasattr(QNetworkRequest, "Attribute"):
            http_status_attr = QNetworkRequest.Attribute.HttpStatusCodeAttribute

        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"Arqueokit-QGIS")
        reply = QgsNetworkAccessManager.blockingGet(request)

        error_code = enum_value(reply.error())
        if error_code != 0:
            raise QgsProcessingException(f"Servidor do IPHAN indisponível. Detalhes: {reply.errorString()}")

        status_code = enum_value(reply.attribute(http_status_attr)) if http_status_attr is not None else None
        if status_code and int(status_code) >= 400:
            raise QgsProcessingException(f"Servidor do IPHAN respondeu com status {status_code}.")

    def initAlgorithm(self, config=None):
        self.options = [
            "Sitios Arqueológicos (Ponto)",
            "Sitios Arqueológicos (Polígono)",
            "Instituto de Guarda",
            "Bens Materiais",
            "Bens Imateriais"
        ]

        self.links = {
            "Sitios Arqueológicos (Ponto)": "http://portal.iphan.gov.br/geoserver/SICG/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=SICG%3Asitios&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Sitios Arqueológicos (Polígono)": "http://portal.iphan.gov.br/geoserver/SICG/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=SICG%3Asitios_pol&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Instituto de Guarda": "http://portal.iphan.gov.br/geoserver/CNA/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=CNA%3Acnigp&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Bens Materiais": "http://portal.iphan.gov.br/geoserver/SICG/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=SICG%3Atg_bem_classificacao&maxFeatures=2147483647&outputFormat=application%2Fjson",
            "Bens Imateriais": "http://portal.iphan.gov.br/geoserver/SICG/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=SICG%3Atg_bem_imaterial&maxFeatures=2147483647&outputFormat=application%2Fjson"
        }

        self.addParameter(
            QgsProcessingParameterEnum(
                self.CAMADAS,
                'Selecionar camadas do IPHAN para download',
                options=self.options,
                defaultValue=0,
                allowMultiple=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        indices = self.parameterAsEnums(parameters, self.CAMADAS, context)
        selecionadas = [self.options[i] for i in indices]
        
        test_url = "http://portal.iphan.gov.br/geoserver/ows"
        try:
            self._check_service_available(test_url)
        except Exception as e:
            feedback.reportError(f"Erro ao conectar ao servidor do IPHAN: {e}")
            raise QgsProcessingException("Servidor do IPHAN indisponível. Tente novamente mais tarde.")


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
        return 'iphan_downloader'

    def displayName(self):
        return self.tr('Download de Camadas IPHAN')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'IPHAN'

    def createInstance(self):
        return IphanDownloader()

    def shortHelpString(self):
        return self.tr("""
        Este algoritmo permite baixar e carregar diretamente no QGIS diversas camadas disponibilizadas pelo IPHAN (via WFS - GeoJSON).
        As camadas selecionadas são adicionadas ao projeto com o sistema de referência SIRGAS 2000 (EPSG:4674).
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
