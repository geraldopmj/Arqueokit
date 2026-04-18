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

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterNumber,
    QgsFields, QgsField, QgsFeature,
    QgsGeometry,
    QgsPointXY, QgsWkbTypes, QgsFeatureSink
)
import numpy as np
from qgis.PyQt.QtCore import QVariant
import math


class best_grid(QgsProcessingAlgorithm):
    POLIGONO = 'POLIGONO'
    ESPACAMENTO = 'ESPACAMENTO'
    PASSO = 'PASSO'

    # NOVOS PARÂMETROS (busca angular)
    ANGULO_INI = 'ANGULO_INI'
    ANGULO_FIM = 'ANGULO_FIM'
    ANGULO_PASSO = 'ANGULO_PASSO'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.POLIGONO,
            'Camada de Polígono',
            [QgsProcessing.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.ESPACAMENTO,
            'Espaçamento (m)',
            QgsProcessingParameterNumber.Integer,
            defaultValue=50,
            minValue=1
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.PASSO,
            'Passo (deslocamento)',
            QgsProcessingParameterNumber.Integer,
            defaultValue=5,
            minValue=1
        ))

        # Busca angular completa (por padrão: 0..175 de 5 em 5)
        self.addParameter(QgsProcessingParameterNumber(
            self.ANGULO_INI,
            'Ângulo inicial (graus)',
            QgsProcessingParameterNumber.Double,
            defaultValue=0.0,
            minValue=0.0,
            maxValue=359.999
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.ANGULO_FIM,
            'Ângulo final (graus)',
            QgsProcessingParameterNumber.Double,
            defaultValue=175.0,
            minValue=0.0,
            maxValue=359.999
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.ANGULO_PASSO,
            'Passo angular (graus)',
            QgsProcessingParameterNumber.Double,
            defaultValue=5.0,
            minValue=0.1,
            maxValue=180.0
        ))

        self.addParameter(
            QgsProcessingParameterVectorDestination(
                'OUTPUT',
                'Camada de Saída'
            )
        )

    def criar_campo(self, nome, tipo, comprimento=None, precisao=None):
        campo = QgsField(nome, tipo, '', 0, 0)  # evita DeprecationWarning
        if comprimento is not None:
            campo.setLength(comprimento)
        if precisao is not None:
            campo.setPrecision(precisao)
        return campo

    def _rotate_xy(self, x, y, cx, cy, ang_rad):
        # Rotaciona (x,y) ao redor de (cx,cy) por ang_rad
        dx = x - cx
        dy = y - cy
        ca = math.cos(ang_rad)
        sa = math.sin(ang_rad)
        xr = cx + (dx * ca - dy * sa)
        yr = cy + (dx * sa + dy * ca)
        return xr, yr

    def processAlgorithm(self, parameters, context, feedback):
        fonte = self.parameterAsSource(parameters, self.POLIGONO, context)
        espacamento = self.parameterAsInt(parameters, self.ESPACAMENTO, context)
        passo = self.parameterAsInt(parameters, self.PASSO, context)

        ang_ini = self.parameterAsDouble(parameters, self.ANGULO_INI, context)
        ang_fim = self.parameterAsDouble(parameters, self.ANGULO_FIM, context)
        ang_passo = self.parameterAsDouble(parameters, self.ANGULO_PASSO, context)

        if not fonte:
            raise Exception("Fonte de polígono inválida.")

        # Define os campos antes de criar o sink
        campos = QgsFields()
        campos.append(self.criar_campo("id", QVariant.Int, comprimento=10))
        campos.append(self.criar_campo("Name", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Longitude", QVariant.Double, comprimento=20, precisao=2))
        campos.append(self.criar_campo("Latitude", QVariant.Double, comprimento=20, precisao=2))
        campos.append(self.criar_campo("Resp", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Data", QVariant.Date))
        campos.append(self.criar_campo("Data_mod", QVariant.Date))
        campos.append(self.criar_campo("Veg", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Relevo", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Realizado", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Motivo", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Observ", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("X_Realizado", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("Y_Realizado", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("bool_X", QVariant.String, comprimento=255))
        campos.append(self.criar_campo("bool_Y", QVariant.String, comprimento=255))
        for i in range(1, 6):
            campos.append(self.criar_campo(f"prof_C{i}", QVariant.Double, comprimento=20, precisao=2))
            campos.append(self.criar_campo(f"cor_C{i}", QVariant.String, comprimento=255))
            campos.append(self.criar_campo(f"textura_C{i}", QVariant.String, comprimento=255))
            campos.append(self.criar_campo(f"bioint_C{i}", QVariant.String, comprimento=255))
            campos.append(self.criar_campo(f"rocha_C{i}", QVariant.String, comprimento=255))
            campos.append(self.criar_campo(f"carvao_C{i}", QVariant.String, comprimento=255))
            campos.append(self.criar_campo(f"vstg_C{i}", QVariant.String, comprimento=255))
            campos.append(self.criar_campo(f"type_vstgC{i}", QVariant.String, comprimento=255))
            campos.append(self.criar_campo(f"qnt_vstgC{i}", QVariant.Int, comprimento=10))
        for i in range(1, 5):
            campos.append(self.criar_campo(f"foto{i}", QVariant.String, comprimento=255))

        (sink, dest_id) = self.parameterAsSink(
            parameters, 'OUTPUT', context, campos,
            QgsWkbTypes.Point, fonte.sourceCrs()
        )

        features = list(fonte.getFeatures())
        feedback.pushInfo(f"Número de feições: {len(features)}")

        geometries = [f.geometry() for f in features]
        multi_geom = QgsGeometry.unaryUnion(geometries)
        feedback.pushInfo("Geometria unificada criada.")

        if multi_geom.isEmpty() or multi_geom.isNull():
            raise Exception("Geometria unificada vazia/nula.")

        # Centro de rotação: centróide (robusto para rotacionar geometria e pontos)
        centroid = multi_geom.centroid()
        cpt = centroid.asPoint()
        cx, cy = cpt.x(), cpt.y()

        # Deslocamentos: cobre todas as fases dentro do “tile” [0, espacamento)
        deslocamentos = list(range(0, espacamento, passo))
        if not deslocamentos:
            deslocamentos = [0]

        # Ângulos a testar (normaliza faixa e garante inclusão do final)
        if ang_passo <= 0:
            ang_passo = 1.0
        # Se ang_fim < ang_ini, varre “por cima” (ex.: 350..10)
        angles = []
        if ang_fim >= ang_ini:
            a = ang_ini
            while a <= ang_fim + 1e-9:
                angles.append(a)
                a += ang_passo
        else:
            a = ang_ini
            while a < 360.0 - 1e-9:
                angles.append(a)
                a += ang_passo
            a = 0.0
            while a <= ang_fim + 1e-9:
                angles.append(a)
                a += ang_passo

        total_tests = len(angles) * (len(deslocamentos) ** 2)
        feedback.pushInfo(f"Ângulos a testar: {len(angles)} | Deslocamentos: {len(deslocamentos)}×{len(deslocamentos)} | Total testes: {total_tests}")

        maior_n = 0
        melhor_pts = []
        melhor_params = {"angulo": None, "dx": None, "dy": None}
        test_counter = 0

        # Loop completo: para cada ângulo, testa todas as combinações de deslocamento (dx,dy)
        for ang_deg in angles:
            ang_rad = math.radians(ang_deg)

            # Para gerar uma grade axis-aligned no “referencial rotacionado”,   
            # rotaciona o polígono por -ang_deg e usa o bbox dele.
            rot_geom = QgsGeometry(multi_geom)
            rot_geom.rotate(-ang_deg, QgsPointXY(cx, cy))
            bounds = rot_geom.boundingBox()

            largura = bounds.xMaximum() - bounds.xMinimum()
            altura = bounds.yMaximum() - bounds.yMinimum()

            expansao_x = largura * 3.0
            expansao_y = altura * 3.0

            xmin_base = bounds.xMinimum() - expansao_x
            xmax_base = bounds.xMaximum() + expansao_x
            ymin_base = bounds.yMinimum() - expansao_y
            ymax_base = bounds.yMaximum() + expansao_y

            # coords base no referencial rotacionado
            # (Depois os pontos serão rotacionados +ang_deg de volta)
            for dx in deslocamentos:
                for dy in deslocamentos:
                    test_counter += 1
                    if total_tests > 0:
                        feedback.setProgress(int((test_counter / total_tests) * 100))

                    xmin = xmin_base + dx
                    xmax = xmax_base + dx
                    ymin = ymin_base + dy
                    ymax = ymax_base + dy

                    x_coords = np.arange(xmin, xmax, espacamento)
                    y_coords = np.arange(ymin, ymax, espacamento)

                    if len(x_coords) == 0 or len(y_coords) == 0:
                        continue

                    xs, ys = np.meshgrid(x_coords, y_coords)

                    pontos_dentro = []
                    # Cada ponto está no frame rotacionado; volta para o frame original rotacionando +ang_rad
                    for x_r, y_r in zip(xs.ravel(), ys.ravel()):
                        x_o, y_o = self._rotate_xy(x_r, y_r, cx, cy, ang_rad)
                        gpt = QgsGeometry.fromPointXY(QgsPointXY(x_o, y_o))
                        if multi_geom.contains(gpt):
                            pontos_dentro.append(gpt)

                    n_in = len(pontos_dentro)
                    if n_in > maior_n:
                        maior_n = n_in
                        melhor_pts = pontos_dentro
                        melhor_params["angulo"] = ang_deg
                        melhor_params["dx"] = dx
                        melhor_params["dy"] = dy

        if maior_n > 0 and melhor_pts:
            feedback.pushInfo(f"Melhor solução: ang={melhor_params['angulo']}°, dx={melhor_params['dx']}, dy={melhor_params['dy']}, pontos={maior_n}")

            # Ordenação: top-down (Y desc), left-right (X asc) no frame original
            ordenados = sorted(melhor_pts, key=lambda g: (-g.asPoint().y(), g.asPoint().x()))

            # Garante que a lista de atributos bate com o total de campos
            n_fields = campos.count()

            for idx, geom in enumerate(ordenados):
                pt = geom.asPoint()
                fet = QgsFeature(campos)
                fet.setGeometry(geom)

                attrs = [None] * n_fields
                # preenche os campos principais por índice (conforme criação acima)
                attrs[0] = idx + 1
                attrs[1] = f"PT-{idx+1}"
                attrs[2] = round(pt.x(), 2)  # Longitude
                attrs[3] = round(pt.y(), 2)  # Latitude

                fet.setAttributes(attrs)
                sink.addFeature(fet, QgsFeatureSink.FastInsert)
        else:
            feedback.reportError("Nenhuma grade válida encontrada.")

        return {'OUTPUT': dest_id}

    def name(self):
        return 'best_grid'

    def displayName(self):
        return self.tr('Grade com Melhor Cobertura (com ângulo)')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Geoprocessamento'

    def createInstance(self):
        return best_grid()

    def shortHelpString(self):
        return self.tr("""
        Gera uma grade de pontos com deslocamento ótimo para maximizar pontos dentro de um polígono.
        Agora também testa rotação (ângulo) da grade: para cada ângulo, varre todos os deslocamentos (dx,dy)
        com passo definido, cobrindo todas as possibilidades de “fase” e direção da grade.
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
