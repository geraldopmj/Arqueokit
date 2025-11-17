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
__date__ = '2025-11-07'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsFeature,
    QgsFeatureSink,
    QgsFields,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes
)
import math

class ConnectLineEndpoints(QgsProcessingAlgorithm):
    """
    Junta/ajusta vértices extremos de linhas em dois modos:
    - v1: cria linhas de conexão entre vértices próximos;
    - v2: move vértices extremos para o centro dos clusters de proximidade.
    """

    INPUT = "INPUT"
    THRESHOLD = "THRESHOLD"
    MODE = "MODE"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                "Camada de linhas de entrada",
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.THRESHOLD,
                "Distância máxima entre vértices (unidades do SRC)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=5.0,
                minValue=0.0
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.MODE,
                "Modo de junção",
                options=[
                    "v1: Criar linhas de conexão entre vértices próximos",
                    "v2: Mover vértices extremos para o centro dos clusters"
                ],
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                "Camada de saída"
            )
        )
    # ---------------------------------------------------------
    @staticmethod
    def _dist(p1: QgsPointXY, p2: QgsPointXY) -> float:
        dx = p1.x() - p2.x()
        dy = p1.y() - p2.y()
        return math.sqrt(dx * dx + dy * dy)

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        threshold = self.parameterAsDouble(parameters, self.THRESHOLD, context)
        mode = self.parameterAsEnum(parameters, self.MODE, context)

        if source is None:
            raise QgsProcessingException("Fonte de dados inválida.")

        crs = source.sourceCrs()

        endpoints_v1 = []  # (QgsPointXY, fid, "start"/"end")
        endpoints_v2 = []  # dict: {point, fid, part, idx}

        total = 100.0 / max(1, source.featureCount())
        for current, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break

            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue

            fid = feat.id()

            if geom.isMultipart():
                lines = geom.asMultiPolyline()
                for part_idx, line in enumerate(lines):
                    if len(line) < 2:
                        continue

                    # início
                    p_start = QgsPointXY(line[0])
                    endpoints_v1.append((p_start, fid, "start"))
                    endpoints_v2.append({
                        "point": p_start,
                        "fid": fid,
                        "part": part_idx,
                        "idx": 0
                    })

                    # fim
                    p_end = QgsPointXY(line[-1])
                    endpoints_v1.append((p_end, fid, "end"))
                    endpoints_v2.append({
                        "point": p_end,
                        "fid": fid,
                        "part": part_idx,
                        "idx": len(line) - 1
                    })
            else:
                line = geom.asPolyline()
                if len(line) < 2:
                    continue

                p_start = QgsPointXY(line[0])
                endpoints_v1.append((p_start, fid, "start"))
                endpoints_v2.append({
                    "point": p_start,
                    "fid": fid,
                    "part": 0,
                    "idx": 0
                })

                p_end = QgsPointXY(line[-1])
                endpoints_v1.append((p_end, fid, "end"))
                endpoints_v2.append({
                    "point": p_end,
                    "fid": fid,
                    "part": 0,
                    "idx": len(line) - 1
                })

            feedback.setProgress(int(current * total))

        # MODO v1: criar linhas de conexão entre vértices próximos
        if mode == 0:
            # Definição de campos da saída (conexões)
            fields = QgsFields()
            fields.append(QgsField("from_fid", QVariant.LongLong))
            fields.append(QgsField("to_fid", QVariant.LongLong))
            fields.append(QgsField("from_pos", QVariant.String))  # "start"/"end"
            fields.append(QgsField("to_pos", QVariant.String))

            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                fields,
                QgsWkbTypes.LineString,
                crs
            )

            if sink is None:
                raise QgsProcessingException("Não foi possível criar o sink de saída.")

            n = len(endpoints_v1)
            created = 0
            total_pairs = max(1, n * (n - 1) / 2.0)
            progress_step = 100.0 / total_pairs
            pair_counter = 0

            for i in range(n):
                p1, fid1, pos1 = endpoints_v1[i]
                for j in range(i + 1, n):
                    if feedback.isCanceled():
                        break

                    p2, fid2, pos2 = endpoints_v1[j]
                    pair_counter += 1

                    # evita conectar vértices da mesma feição
                    if fid1 == fid2:
                        continue

                    if self._dist(p1, p2) <= threshold:
                        geom_conn = QgsGeometry.fromPolylineXY([p1, p2])
                        f = QgsFeature(fields)
                        f.setGeometry(geom_conn)
                        f["from_fid"] = int(fid1)
                        f["to_fid"] = int(fid2)
                        f["from_pos"] = pos1
                        f["to_pos"] = pos2
                        sink.addFeature(f, QgsFeatureSink.FastInsert)
                        created += 1

                    if pair_counter % 100 == 0:
                        feedback.setProgress(int(pair_counter * progress_step))

            feedback.pushInfo(f"Conexões criadas: {created}")
            return {self.OUTPUT: dest_id}

        # MODO v2: mover vértices extremos para centro de clusters
        else:
            # Construir clusters de endpoints próximos (componentes conexas)
            n = len(endpoints_v2)
            visited = [False] * n
            clusters = []

            for i in range(n):
                if visited[i]:
                    continue
                # DFS num grafo de proximidade
                stack = [i]
                visited[i] = True
                comp = [i]

                while stack:
                    k = stack.pop()
                    pk = endpoints_v2[k]["point"]

                    for j in range(n):
                        if visited[j]:
                            continue
                        pj = endpoints_v2[j]["point"]
                        if self._dist(pk, pj) <= threshold:
                            visited[j] = True
                            stack.append(j)
                            comp.append(j)

                if len(comp) > 1:
                    clusters.append(comp)

            # Mapa de ajustes: (fid, part, idx) -> novo ponto
            adjust_map = {}
            for comp in clusters:
                xs = []
                ys = []
                for idx_ep in comp:
                    pt = endpoints_v2[idx_ep]["point"]
                    xs.append(pt.x())
                    ys.append(pt.y())
                if not xs:
                    continue

                cx = sum(xs) / len(xs)
                cy = sum(ys) / len(ys)
                center_pt = QgsPointXY(cx, cy)

                for idx_ep in comp:
                    ep = endpoints_v2[idx_ep]
                    key = (ep["fid"], ep["part"], ep["idx"])
                    adjust_map[key] = center_pt

            feedback.pushInfo(f"Clusters formados: {len(clusters)}")
            feedback.pushInfo(f"Vértices ajustáveis: {len(adjust_map)}")

            # Definir campos de saída iguais aos da camada de entrada
            fields = source.fields()

            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                fields,
                source.wkbType(),
                crs
            )

            if sink is None:
                raise QgsProcessingException("Não foi possível criar o sink de saída.")

            # Reaplicar feições com geometria ajustada
            total = 100.0 / max(1, source.featureCount())
            for current, feat in enumerate(source.getFeatures()):
                if feedback.isCanceled():
                    break

                fid = feat.id()
                geom = feat.geometry()
                if geom is None or geom.isEmpty():
                    sink.addFeature(feat, QgsFeatureSink.FastInsert)
                    continue

                changed = False

                if geom.isMultipart():
                    lines = geom.asMultiPolyline()
                    for part_idx, line in enumerate(lines):
                        for vidx, pt in enumerate(line):
                            key = (fid, part_idx, vidx)
                            if key in adjust_map:
                                line[vidx] = adjust_map[key]
                                changed = True
                    if changed:
                        new_geom = QgsGeometry.fromMultiPolylineXY(lines)
                    else:
                        new_geom = geom
                else:
                    line = geom.asPolyline()
                    for vidx, pt in enumerate(line):
                        key = (fid, 0, vidx)
                        if key in adjust_map:
                            line[vidx] = adjust_map[key]
                            changed = True
                    if changed:
                        new_geom = QgsGeometry.fromPolylineXY(line)
                    else:
                        new_geom = geom

                new_feat = QgsFeature(fields)
                new_feat.setAttributes(feat.attributes())
                new_feat.setGeometry(new_geom)
                sink.addFeature(new_feat, QgsFeatureSink.FastInsert)

                feedback.setProgress(int(current * total))

            return {self.OUTPUT: dest_id}


    def name(self):
        return "connect_line_endpoints"

    def displayName(self):
        return "Juntar extremidades soltas de linhas"

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Geoprocessamento'

    def createInstance(self):
        return ConnectLineEndpoints()

    def shortHelpString(self):
        return (
            "Opera sobre vértices extremos (início/fim) de feições lineares. Algoritmos:"
            "- v1: cria novas linhas conectando pares de vértices extremos que estejam a uma distância ≤ threshold."
            "- v2: identifica clusters de vértices extremos no threshold, calcula o centro geométrico de cada cluster e move todos os vértices desse cluster para essa coordenada central."
        )
    
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)