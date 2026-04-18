# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Exportar Fichas Arqueológicas (PDF - ReportLab)
 Layout profissional, logos no topo e título mais abaixo
 Autor: Geraldo Pereira de Morais Júnior
 ***********************************************/
"""
__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-06-26'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterFile,
    QgsProcessingParameterBoolean,
    QgsProcessingException
)
from qgis.PyQt.QtCore import QDate, QDateTime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
import os


class ExportRecordPDF(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    LOGO_EMPRESA = 'LOGO_EMPRESA'
    LOGO_CLIENTE = 'LOGO_CLIENTE'
    PAGINACAO = 'PAGINACAO'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT,
            'Camada de pontos com atributos da ficha',
            [QgsProcessing.TypeVectorPoint]
        ))

        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT,
            'Exportar PDF',
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

        self.addParameter(QgsProcessingParameterBoolean(
            self.PAGINACAO,
            'Exibir numeração de páginas?',
            defaultValue=True
        ))

    @staticmethod
    def draw_wrapped_text(c, text, x, y, max_width, font_name="Helvetica", font_size=9, leading=12):
        """Quebra texto automaticamente no PDF"""
        c.setFont(font_name, font_size)
        words = str(text).split()
        line = ""
        for w in words:
            if c.stringWidth(line + w, font_name, font_size) <= max_width:
                line += w + " "
            else:
                c.drawString(x, y, line)
                y -= leading
                line = w + " "
        if line:
            c.drawString(x, y, line)
            y -= leading
        return y

    @staticmethod
    def safe_attr(feat, field_name, default="-"):
        if field_name not in feat.fields().names():
            return default
        value = feat.attribute(field_name)
        if value in (None, ""):
            return default
        return value

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        output_pdf = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        logo_empresa = self.parameterAsFile(parameters, self.LOGO_EMPRESA, context)
        logo_cliente = self.parameterAsFile(parameters, self.LOGO_CLIENTE, context)
        paginacao = self.parameterAsBool(parameters, self.PAGINACAO, context)

        if not layer:
            raise QgsProcessingException("Camada inválida ou vazia.")

        idx_id = layer.fields().indexFromName('id')
        if idx_id < 0:
            raise QgsProcessingException("Campo 'id' não encontrado na camada.")

        features = sorted(layer.getFeatures(), key=lambda f: f[idx_id])
        total_page = len(features)

        # Paleta terrosa/pastel
        cor_cabecalho_tabela = HexColor("#c6a984")  # Cabeçalho tabela
        cor_linha_alternada = HexColor("#f2e6d9")   # Linhas alternadas
        cor_bordas = HexColor("#5a4b41")            # Bordas
        cor_texto = colors.black

        c = canvas.Canvas(output_pdf, pagesize=A4)
        width, height = A4
        margin = 40
        page_num = 1

        for feat in features:
            # Logos no topo
            logo_max_height = 50
            logo_max_width = 80
            top_y = height - margin - 5  # Posição para logos

            if logo_empresa and os.path.exists(logo_empresa):
                img = ImageReader(logo_empresa)
                iw, ih = img.getSize()
                ratio = min(logo_max_width / iw, logo_max_height / ih)
                new_w, new_h = iw * ratio, ih * ratio
                c.drawImage(logo_empresa, margin + 5, top_y - new_h, new_w, new_h, mask='auto')

            if logo_cliente and os.path.exists(logo_cliente):
                img = ImageReader(logo_cliente)
                iw, ih = img.getSize()
                ratio = min(logo_max_width / iw, logo_max_height / ih)
                new_w, new_h = iw * ratio, ih * ratio
                c.drawImage(logo_cliente, width - margin - new_w - 5, top_y - new_h, new_w, new_h, mask='auto')

            # Título mais abaixo que as logos
            c.setFont("Times-Bold", 15)
            c.setFillColor(cor_texto)
            c.drawCentredString(
                width / 2, top_y - logo_max_height - 25,
                f"FICHA DE PROSPECÇÃO ARQUEOLÓGICA – {self.safe_attr(feat, 'Name', feat[idx_id])}"
            )

            # Y inicial depois do título
            y = top_y - logo_max_height - 50
            c.setFont("Helvetica", 10)

            # Data formatada
            data_attr = self.safe_attr(feat, 'Data', "-")
            if isinstance(data_attr, QDate):
                data_str = data_attr.toString("dd/MM/yyyy")
            elif isinstance(data_attr, QDateTime):
                data_str = data_attr.date().toString("dd/MM/yyyy")
            else:
                data_str = str(data_attr or "-")

            # Bloco de informações condensadas
            linha1 = (
                f"Ponto: {self.safe_attr(feat, 'Name', feat[idx_id])}    "
                f"Data: {data_str}    "
                f"Vegetação: {self.safe_attr(feat, 'Veg')}    "
                f"Relevo: {self.safe_attr(feat, 'Relevo')}    "
                f"Responsável: {self.safe_attr(feat, 'Resp')}    "
            )
            linha2 = (
                f"Longitude: {self.safe_attr(feat, 'Longitude')}    "
                f"Latitude: {self.safe_attr(feat, 'Latitude')}    "
                f"{'Realizado: ' + str(self.safe_attr(feat, 'Realizado')) if str(self.safe_attr(feat, 'Realizado')).lower() == 'sim' else 'Realizado: ' + str(self.safe_attr(feat, 'Realizado')) + '   Motivo: ' + str(self.safe_attr(feat, 'Motivo'))}"
            )

            c.drawString(margin + 10, y, linha1)
            y -= 15
            c.drawString(margin + 10, y, linha2)
            y -= 25

            # Tabela com cores terrosas
            col1, col2, col3, col4, col5 = margin + 10, margin + 60, margin + 130, margin + 330, margin + 440
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(cor_cabecalho_tabela)
            c.rect(margin + 5, y - 5, width - 2 * margin - 10, 18, fill=True, stroke=False)
            c.setFillColor(cor_texto)
            c.drawString(col1, y, "Camada")
            c.drawString(col2, y, "Profundidade")
            c.drawString(col3, y, "Cor / Textura")
            c.drawString(col4, y, "Vestígios")
            c.drawString(col5, y, "Qtd. Vestígios")

            y -= 20
            c.setFont("Helvetica", 9)

            for i in range(1, 6):
                if i % 2 == 0:
                    c.setFillColor(cor_linha_alternada)
                    c.rect(margin + 5, y - 3, width - 2 * margin - 10, 15, fill=True, stroke=False)
                c.setFillColor(cor_texto)

                prof = self.safe_attr(feat, f'prof_C{i}')
                cor = self.safe_attr(feat, f'cor_C{i}')
                textura = self.safe_attr(feat, f'textura_C{i}')
                solo = f"{cor} / {textura}" if cor != "-" or textura != "-" else "-"
                vest = self.safe_attr(feat, f'vstg_C{i}')
                qvest = self.safe_attr(feat, f'qnt_vstgC{i}')

                y_temp = y
                y2 = self.draw_wrapped_text(c, solo, col3, y_temp, col4 - col3 - 5)
                y3 = self.draw_wrapped_text(c, vest, col4, y_temp, col5 - col4 - 5)

                min_y = min(y2, y3)
                c.drawString(col1, y_temp, f"C{i}")
                c.drawString(col2, y_temp, str(prof))
                c.drawString(col5, y_temp, str(qvest))

                y = min_y - 5

            y -= 20

            # Fotos
            box_size = ((width - 2 * margin - 10) / 2)
            box_height = box_size * 0.6666
            fotos = [
                self.safe_attr(feat, 'foto1', None),
                self.safe_attr(feat, 'foto2', None),
                self.safe_attr(feat, 'foto3', None),
                self.safe_attr(feat, 'foto4', None)
            ]
            c.setFont("Helvetica", 8)
            c.setStrokeColor(cor_bordas)

            for idx, foto in enumerate(fotos):
                row, col = idx // 2, idx % 2
                x = margin + col * (box_size + 10)
                y_box = y - (row * (box_height + 40))

                c.rect(x, y_box - box_height, box_size, box_height)

                if foto and os.path.exists(str(foto)):
                    try:
                        img = ImageReader(str(foto))
                        iw, ih = img.getSize()
                        ratio = min(box_size / iw, box_height / ih)
                        new_w, new_h = iw * ratio, ih * ratio
                        offset_x = (box_size - new_w) / 2
                        offset_y = (box_height - new_h) / 2
                        c.drawImage(
                            img,
                            x + offset_x,
                            y_box - box_height + offset_y,
                            new_w,
                            new_h,
                            preserveAspectRatio=True
                        )
                    except:
                        pass

                c.drawCentredString(x + box_size / 2, y_box - box_height - 10, f"Figura {self.safe_attr(feat, 'Name', feat[idx_id])} - {idx + 1}")

            # Rodapé opcional
            if paginacao:
                c.setFont("Helvetica-Oblique", 8)
                c.setFillColor(cor_bordas)
                c.drawCentredString(width / 2, margin - 20, f"Página {page_num}/{total_page}")
            page_num += 1

            c.showPage()

        c.save()
        feedback.pushInfo(f"PDF gerado: {output_pdf}")
        return {self.OUTPUT: output_pdf}

    def name(self):
        return 'export_fichas_pdf'
    def displayName(self):
        return 'Exportar Fichas de Prospecção'
    def group(self):
        return 'Exportar PDF'
    def groupId(self):
        return 'exportar_pdf'
    def createInstance(self):
        return ExportRecordPDF()
