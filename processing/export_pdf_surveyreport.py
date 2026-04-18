# -*- coding: utf-8 -*-
"""
/***********************************************
Arqueokit - QGIS Plugin
Exportar Relatório Pós-Campo (PDF - ReportLab)
Layout compacto e científico, cores terrosas e gráfico daltônico-friendly
Autor: Geraldo Pereira de Morais Júnior
 ***********************************************/
"""
__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-08-13'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterFile,
    QgsProcessingException
)
from qgis.PyQt.QtCore import QDate, QDateTime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.graphics.charts.lineplots import LinePlot
from collections import Counter, defaultdict
import statistics
import os


class ExportReportPDF(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    LOGO_EMPRESA = 'LOGO_EMPRESA'
    LOGO_CLIENTE = 'LOGO_CLIENTE'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT,
            'Camada de pontos com atributos da ficha',
            [QgsProcessing.TypeVectorPoint]
        ))

        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT,
            'Exportar Relatório Pós-Campo',
            fileFilter='PDF (*.pdf)'
        ))

        self.addParameter(QgsProcessingParameterFile(
            self.LOGO_EMPRESA,
            'Logo da empresa (opcional)',
            behavior=QgsProcessingParameterFile.File,
            fileFilter='Imagens (*.png *.jpg *.jpeg)',
            optional=True
        ))

        self.addParameter(QgsProcessingParameterFile(
            self.LOGO_CLIENTE,
            'Logo do cliente (opcional)',
            behavior=QgsProcessingParameterFile.File,
            fileFilter='Imagens (*.png *.jpg *.jpeg)',
            optional=True
        ))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        output_pdf = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        logo_empresa = self.parameterAsFile(parameters, self.LOGO_EMPRESA, context)
        logo_cliente = self.parameterAsFile(parameters, self.LOGO_CLIENTE, context)

        if not layer:
            raise QgsProcessingException("Camada inválida ou vazia.")

        # --- Agregados e contadores ---
        total_pts = 0
        total_realizados = 0
        pts_com_vestigios = 0
        profundidades_maximas = []
        vestigios = []
        vegetacao = Counter()
        relevo = Counter()
        pontos_por_dia = Counter()
        camadas_presentes = Counter()
        profundidade_por_camada = {i: [] for i in range(1, 6)}
        vestigios_por_camada = {i: [] for i in range(1, 6)}
        profundidades_por_resp = {}
        pontos_por_resp = Counter()
        vestigios_por_resp = Counter()
        datas_por_resp = defaultdict(set)

        # --- Loop pontos ---
        for feat in layer.getFeatures():
            total_pts += 1
            if str(feat.attribute("Realizado")).lower() in ["sim", "1", "yes"]:
                total_realizados += 1

            vegetacao[str(feat.attribute("Veg") or "-")] += 1
            relevo[str(feat.attribute("Relevo") or "-")] += 1

            encontrou_vestigio = False
            maior_profundidade = None

            for i in range(1, 6):
                prof = feat.attribute(f"prof_C{i}")
                qtd = feat.attribute(f"qnt_vstgC{i}")

                if prof not in (None, "-", ""):
                    try:
                        profundidade = float(prof)
                        profundidade_por_camada[i].append(profundidade)
                        camadas_presentes[i] += 1
                        if maior_profundidade is None or profundidade > maior_profundidade:
                            maior_profundidade = profundidade
                    except:
                        pass

                if qtd not in (None, "-", ""):
                    try:
                        v = float(qtd)
                        if v > 0:
                            vestigios.append(v)
                            vestigios_por_camada[i].append(v)
                            encontrou_vestigio = True
                    except:
                        pass

            if maior_profundidade is not None:
                profundidades_maximas.append(maior_profundidade)

                resp = str(feat.attribute("Resp") or "Sem responsável")
                profundidades_por_resp.setdefault(resp, []).append(maior_profundidade)
                pontos_por_resp[resp] += 1

                data_attr = feat.attribute("Data")
                if isinstance(data_attr, QDate):
                    data = data_attr
                elif isinstance(data_attr, QDateTime):
                    data = data_attr.date()
                else:
                    data = QDate.fromString(str(data_attr), "yyyy-MM-dd")
                if data and data.isValid():
                    datas_por_resp[resp].add(data.toString("yyyy-MM-dd"))
                    pontos_por_dia[data.toString("yyyy-MM-dd")] += 1

                if encontrou_vestigio:
                    vestigios_por_resp[resp] += 1

            if encontrou_vestigio:
                pts_com_vestigios += 1

        # --- Paleta terrosa ---
        cor_titulo = colors.black
        cor_linha = HexColor("#5a4b41")
        cor_destaque = HexColor("#c6a984")
        cor_linha_alternada = HexColor("#f2e6d9")

        # --- PDF ---
        c = canvas.Canvas(output_pdf, pagesize=A4)
        width, height = A4
        margin = 40
        y = height - margin

        # --- Logos no topo ---
        logo_max_height = 50
        logo_max_width = 80
        top_y = height - margin - 5

        if logo_empresa and os.path.exists(logo_empresa):
            try:
                img = ImageReader(logo_empresa)
                iw, ih = img.getSize()
                ratio = min(logo_max_width / iw, logo_max_height / ih)
                new_w, new_h = iw * ratio, ih * ratio
                c.drawImage(img, margin + 5, top_y - new_h, new_w, new_h, mask='auto')
            except:
                pass

        if logo_cliente and os.path.exists(logo_cliente):
            try:
                img = ImageReader(logo_cliente)
                iw, ih = img.getSize()
                ratio = min(logo_max_width / iw, logo_max_height / ih)
                new_w, new_h = iw * ratio, ih * ratio
                c.drawImage(img, width - margin - new_w - 5, top_y - new_h, new_w, new_h, mask='auto')
            except:
                pass

        # --- Título centralizado ---
        c.setFont("Times-Bold", 16)
        c.setFillColor(cor_titulo)
        c.drawCentredString(width / 2, top_y - logo_max_height - 10,
                            "RELATÓRIO PÓS-CAMPO – RESUMO ESTATÍSTICO")

        # Linha de separação
        c.setStrokeColor(cor_linha)
        c.line(margin, top_y - logo_max_height - 20, width - margin, top_y - logo_max_height - 20)

        # --- Estatísticas gerais ---
        y = top_y - logo_max_height - 50
        c.setFont("Helvetica", 11)
        c.drawString(margin, y, f"Total de pontos cadastrados: {total_pts}")
        y -= 20
        c.drawString(margin, y, f"Total de pontos realizados: {total_realizados}")
        y -= 20
        c.drawString(margin, y,
                     f"Pontos com vestígios: {pts_com_vestigios} ({(pts_com_vestigios / total_pts * 100):.1f}%)")
        y -= 30

        # --- Distribuições lado a lado ---
        col1_x = margin
        col2_x = width / 2 + 10
        col_y = y

        c.setFont("Helvetica-Bold", 12)
        c.drawString(col1_x, col_y, "Distribuição por Vegetação:")
        col_y -= 20
        c.setFont("Helvetica", 10)
        for veg, n in vegetacao.items():
            c.drawString(col1_x, col_y, f"{veg}: {(n / total_pts * 100):.1f}%")
            col_y -= 15

        col_y_rel = y
        c.setFont("Helvetica-Bold", 12)
        c.drawString(col2_x, col_y_rel, "Distribuição por Relevo:")
        col_y_rel -= 20
        c.setFont("Helvetica", 10)
        for rel, n in relevo.items():
            c.drawString(col2_x, col_y_rel, f"{rel}: {(n / total_pts * 100):.1f}%")
            col_y_rel -= 15

        y = min(col_y, col_y_rel) - 30

        # --- Score produtividade ---
        total_vest = sum(vestigios_por_resp.values())
        total_pontos = sum(pontos_por_resp.values())

        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, "Produtividade por arqueólogo (Score 0–100):")
        y -= 20
        c.setFont("Helvetica", 10)

        for resp, profundidades in profundidades_por_resp.items():
            media_profundidade = statistics.mean(profundidades)
            pontos = pontos_por_resp[resp]
            vest = vestigios_por_resp[resp]
            total_dias = len(datas_por_resp[resp]) if datas_por_resp[resp] else 1
            media_por_dia = pontos / total_dias
            pct_vest = (vest / pontos * 100) if pontos else 0

            score = (
                (0.4 * ((vest / total_vest * 100) if total_vest > 0 else 0)) +
                (0.4 * media_profundidade) +
                (0.2 * ((pontos / total_pontos * 100) if total_pontos > 0 else 0))
            ) / 100

            c.drawString(
                margin, y,
                f"{resp}: Prof. média {media_profundidade:.2f} cm | "
                f"{pontos} pts ({media_por_dia:.1f}/dia) | {pct_vest:.1f}% c/ vestígios | "
                f"Score: {score*100:.1f}"
            )
            y -= 15

        y -= 25

        # --- Gráfico pontos por dia ---
        if pontos_por_dia:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin, y, "Pontos por dia (geral):")
            y -= 160

            datas = sorted(pontos_por_dia.keys())
            valores = [pontos_por_dia[d] for d in datas]
            n = len(valores)
            media_valores = sum(valores) / n
            x_vals = list(range(n))

            # regressão linear
            m = (n * sum(i * valores[i] for i in x_vals) - sum(x_vals) * sum(valores)) / \
                ((n * sum(i**2 for i in x_vals) - (sum(x_vals) ** 2)) or 1)
            b = (sum(valores) - m * sum(x_vals)) / n

            drawing = Drawing(400, 120)
            lp = LinePlot()
            lp.x = 20
            lp.y = 20
            lp.height = 100
            lp.width = 360
            lp.data = [list(zip(x_vals, valores))]
            lp.lines[0].strokeColor = HexColor("#0072B2")
            lp.joinedLines = 1
            lp.xValueAxis.valueMin = 0
            lp.xValueAxis.valueMax = n - 1
            lp.xValueAxis.valueSteps = x_vals
            lp.xValueAxis.labelTextFormat = lambda i: datas[i][-5:]
            lp.yValueAxis.valueMin = 0
            lp.yValueAxis.valueMax = max(valores + [media_valores, m * (n - 1) + b]) + 1

            drawing.add(lp)

            # linha média
            linha_media = Line(
                lp.x, 20 + (media_valores / lp.yValueAxis.valueMax) * lp.height,
                lp.x + lp.width, 20 + (media_valores / lp.yValueAxis.valueMax) * lp.height
            )
            linha_media.strokeColor = colors.black
            linha_media.strokeDashArray = [4, 4]
            drawing.add(linha_media)

            # linha regressão
            linha_reg = Line(
                lp.x, 20 + (b / lp.yValueAxis.valueMax) * lp.height,
                lp.x + lp.width, 20 + (m * (n - 1) + b) / lp.yValueAxis.valueMax * lp.height
            )
            linha_reg.strokeColor = HexColor("#E69F00")
            linha_reg.strokeDashArray = [4, 4]
            drawing.add(linha_reg)

            drawing.drawOn(c, margin, y)
            y -= 50

        # --- Resumo por camada ---
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, "Resumo por Camada:")
        y -= 20
        c.setFont("Helvetica", 10)
        for i in range(1, 6):
            c.drawString(
                margin, y,
                f"C{i}: {(camadas_presentes[i]/total_pts*100):.1f}% pts | "
                f"Média Prof.: {statistics.mean(profundidade_por_camada[i]) if profundidade_por_camada[i] else 0:.2f} m | "
                f"Média Vestígios: {statistics.mean(vestigios_por_camada[i]) if vestigios_por_camada[i] else 0:.1f}"
            )
            y -= 15

        c.save()
        feedback.pushInfo(f"Relatório gerado: {output_pdf}")
        return {self.OUTPUT: output_pdf}

    def name(self):
        return 'export_resumo_pdf'

    def displayName(self):
        return 'Exportar Relatório Pós-Campo'

    def group(self):
        return 'Exportar PDF'

    def groupId(self):
        return 'exportar_pdf'

    def createInstance(self):
        return ExportReportPDF()
