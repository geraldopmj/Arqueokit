# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 WebGIS - Export
 Author: Geraldo Pereira de Morais Júnior
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
    QgsProcessingParameterMultipleLayers,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
    QgsProcessingException,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsPointXY,
    QgsCsException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    NULL as QGIS_NULL,
    QgsMapSettings,
    QgsMapRendererCustomPainterJob,
)
from qgis.PyQt.QtCore import QDate, QDateTime, QSize
from qgis.PyQt.QtGui import QImage, QPainter

import folium
from folium.plugins import LocateControl, MarkerCluster
from folium.map import FitOverlays

import json, re, math, os

class ExportFoliumMap(QgsProcessingAlgorithm):
    INPUT_LAYERS  = 'INPUT_LAYERS'    # vetores
    RASTER_LAYERS = 'RASTER_LAYERS'   # rasters
    RASTER_WIDTH  = 'RASTER_WIDTH'    # px
    OUTPUT_HTML   = 'OUTPUT_HTML'

    def initAlgorithm(self, config=None):
        # Vetores
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_LAYERS,
                self.tr('Camadas vetoriais a incluir'),
                layerType=QgsProcessing.TypeVectorAnyGeometry,
                optional=True
            )
        )
        # Rasters
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.RASTER_LAYERS,
                self.tr('Rasters a incluir (renderizados como ImageOverlay)'),
                layerType=QgsProcessing.TypeRaster,
                optional=True
            )
        )
        # Largura de renderização
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RASTER_WIDTH,
                self.tr('Largura de renderização dos rasters (px)'),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=2000,
                minValue=256, maxValue=10000,
                optional=True
            )
        )

        self.addParameter(QgsProcessingParameterString('MAP_TITLE',  self.tr('Título do Mapa'),  defaultValue=''))
        self.addParameter(QgsProcessingParameterString('MAP_AUTHOR', self.tr('Elaboração'),      defaultValue=''))
        self.addParameter(QgsProcessingParameterString('MAP_NOTE',   self.tr('Nome Empresa'),    defaultValue=''))
        self.addParameter(
            QgsProcessingParameterString(
                'MAP_NOTE_LINK',
                self.tr('Link (opcional) para abrir ao clicar na Nota'),
                defaultValue='', optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_HTML,
                self.tr('Arquivo HTML de saída'),
                fileFilter='HTML (*.html)'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        vectors = self.parameterAsLayerList(parameters, self.INPUT_LAYERS, context) or []
        rasters = self.parameterAsLayerList(parameters, self.RASTER_LAYERS, context) or []
        if not vectors and not rasters:
            raise QgsProcessingException(self.tr("Nenhuma camada fornecida (vetor ou raster)."))

        output_html = self.parameterAsFileOutput(parameters, self.OUTPUT_HTML, context)
        out_dir = os.path.dirname(output_html) or os.getcwd()
        os.makedirs(out_dir, exist_ok=True)

        raster_width = self.parameterAsInt(parameters, self.RASTER_WIDTH, context) or 2000

        cores = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf']
        map_author = self.parameterAsString(parameters, 'MAP_AUTHOR', context)

        m = folium.Map(location=[0, 0], zoom_start=2, tiles=None, attr=map_author or None)
        LocateControl(auto_start=False).add_to(m)

        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr=(f"Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community | {map_author}"
                  if map_author else "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community"),
            name="Esri World Imagery"
        ).add_to(m)
        folium.TileLayer(
            tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
            name='OpenTopoMap',
            attr=(f"Map data: © OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap (CC-BY-SA) | {map_author}"
                  if map_author else "Map data: © OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap (CC-BY-SA)")
        ).add_to(m)
        folium.TileLayer(
            tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            name='OpenStreetMap',
            attr=f"© OpenStreetMap contributors | {map_author}" if map_author else '© OpenStreetMap contributors'
        ).add_to(m)
        folium.TileLayer(
            tiles="https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}{r}.png",
            attr=f"© OpenStreetMap contributors © CARTO | {map_author}" if map_author else "© OpenStreetMap contributors © CARTO",
            name="Carto Voyager"
        ).add_to(m)

        lat_min, lon_min = 90.0, 180.0
        lat_max, lon_max = -90.0, -180.0
        grupos_poligonos, grupos_linhas, grupos_pontos = [], [], []

        # Título e nota
        map_title = self.parameterAsString(parameters, 'MAP_TITLE', context)
        if map_title:
            title_html = f"""
            <div style="position:fixed;top:10px;left:50%;transform:translateX(-50%);
                        z-index:1000;background:#fff;padding:8px 15px;border-radius:4px;
                        font-size:16px;font-weight:bold;font-family:'Segoe UI',Arial,sans-serif;
                        max-width:80%;text-align:center;">{map_title}</div>"""
            m.get_root().html.add_child(folium.Element(title_html))

        map_note = self.parameterAsString(parameters, 'MAP_NOTE', context)
        note_link = self.parameterAsString(parameters, 'MAP_NOTE_LINK', context)
        if map_note:
            content_html = (f"<a href='{note_link}' target='_blank' rel='noopener noreferrer' "
                            f"style='text-decoration:none;color:inherit;'>{map_note}</a>") if note_link else map_note
            note_html = f"""
            <div id="map-note" style="position:fixed;top:20px;right:10px;z-index:1000;background:#fff;
                 padding:6px 10px;border-radius:4px;font-size:12px;font-family:'Segoe UI',Arial,sans-serif;
                 font-weight:bold;max-width:300px;max-height:200px;box-shadow:0 1px 3px rgba(0,0,0,.2);">
                {content_html}
            </div>"""
            m.get_root().html.add_child(folium.Element(note_html))

        # ===== RASTERS (render → PNG → ImageOverlay) =====
        for rlayer in rasters:
            if not rlayer or not rlayer.isValid():
                continue
            png_path, ext = self._render_raster_to_png(rlayer, out_dir, raster_width)
            feedback.pushInfo(self.tr(f"Raster renderizado: {png_path}"))
            # bounds em WGS84
            crs_dest = QgsCoordinateReferenceSystem('EPSG:4326')
            transform = QgsCoordinateTransform(
                rlayer.crs(),
                crs_dest,
                QgsProject.instance().transformContext()
            )
            try:
                ext_wgs = transform.transformBoundingBox(ext)
                bounds = [[ext_wgs.yMinimum(), ext_wgs.xMinimum()],
                          [ext_wgs.yMaximum(), ext_wgs.xMaximum()]]
            except QgsCsException:
                corners = [
                    QgsPointXY(ext.xMinimum(), ext.yMinimum()),
                    QgsPointXY(ext.xMinimum(), ext.yMaximum()),
                    QgsPointXY(ext.xMaximum(), ext.yMinimum()),
                    QgsPointXY(ext.xMaximum(), ext.yMaximum()),
                ]
                transformed = [transform.transform(pt) for pt in corners]
                xs = [pt.x() for pt in transformed]
                ys = [pt.y() for pt in transformed]
                bounds = [[min(ys), min(xs)], [max(ys), max(xs)]]

            folium.raster_layers.ImageOverlay(
                name=rlayer.name(),
                image=png_path,                 # caminho absoluto → Folium abre e embute (data URI)
                bounds=bounds,
                opacity=1.0,
                interactive=False,
                cross_origin=False
            ).add_to(m)

            lat_min, lon_min = min(lat_min, bounds[0][0]), min(lon_min, bounds[0][1])
            lat_max, lon_max = max(lat_max, bounds[1][0]), max(lon_max, bounds[1][1])

        # ===== VETORES =====
        for idx, layer in enumerate(vectors):
            cor_inicial = cores[idx % len(cores)]
            layer_var_name = re.sub(r'\W|^(?=\d)', '_', layer.name()) + "_layer"
            crs_dest = QgsCoordinateReferenceSystem('EPSG:4326')
            transform = QgsCoordinateTransform(
                layer.crs(),
                crs_dest,
                QgsProject.instance().transformContext()
            )

            if layer.geometryType() == 0:  # pontos
                mc = MarkerCluster(name=layer.name(), disableClusteringAtZoom=16, maxClusterRadius=30)
                for feat in layer.getFeatures():
                    geom = feat.geometry()
                    if not geom or geom.isEmpty():
                        continue
                    pontos = [geom.asPoint()] if not geom.isMultipart() else geom.asMultiPoint()
                    for pt in pontos:
                        pt_wgs = transform.transform(pt)
                        popup_html = self._popup_table(layer, feat)
                        folium.CircleMarker(
                            location=[pt_wgs.y(), pt_wgs.x()],
                            radius=2, color=cor_inicial,
                            fill=True, fill_color=cor_inicial, fill_opacity=1,
                            weight=30, opacity=0, popup=popup_html
                        ).add_to(mc)
                        lat_min, lon_min = min(lat_min, pt_wgs.y()), min(lon_min, pt_wgs.x())
                        lat_max, lon_max = max(lat_max, pt_wgs.y()), max(lon_max, pt_wgs.x())
                grupos_pontos.append(mc)
            else:  # linhas/polígonos
                features_geojson = []
                for feat in layer.getFeatures():
                    geom = feat.geometry()
                    if not geom or geom.isEmpty():
                        continue
                    geom.transform(transform)
                    attrs = {f.name(): self._qvariant_to_py(feat[f.name()]) for f in layer.fields()}
                    feat_json = {"type": "Feature", "properties": attrs, "geometry": json.loads(geom.asJson())}
                    features_geojson.append(feat_json)
                    for p in geom.vertices():
                        lat_min, lon_min = min(lat_min, p.y()), min(lon_min, p.x())
                        lat_max, lon_max = max(lat_max, p.y()), max(lon_max, p.x())

                if features_geojson:
                    geojson_data = {"type": "FeatureCollection", "features": features_geojson}
                    fg = folium.FeatureGroup(name=layer.name())

                    def style_function(feature, color=cor_inicial):
                        return {"color": color, "weight": 2,
                                "fillColor": color, "fillOpacity": 0.4 if layer.geometryType() == 2 else 0}

                    def popup_function(feature):
                        attrs = feature["properties"]
                        html = self._popup_table_dict(attrs)
                        html += (f"<br><label>Cor:</label>"
                                 f"<input type='color' value='{cor_inicial}' "
                                 f"onchange=\"window['{layer_var_name}'].setStyle({{color: this.value, fillColor: this.value}})\">"
                                 f"<br><label>Opacidade:</label>"
                                 f"<input type='range' min='0' max='1' step='0.1' value='0.6' "
                                 f"oninput=\"window['{layer_var_name}'].setStyle({{opacity: this.value, fillOpacity: this.value}})\">")
                        return folium.Popup(html, max_width=300)

                    gj = folium.GeoJson(geojson_data, name=layer.name(),
                                        style_function=style_function, popup=popup_function)
                    fg.add_child(gj)
                    if layer.geometryType() == 1:      # linhas
                        grupos_linhas.append((fg, layer_var_name, gj))
                    elif layer.geometryType() == 2:    # polígonos
                        grupos_poligonos.append((fg, layer_var_name, gj))

        for fg, var_name, gj in grupos_poligonos:
            gj.add_to(fg); fg.add_to(m)
            m.get_root().html.add_child(folium.Element(f"<script>window['{var_name}'] = {gj.get_name()};</script>"))
        for fg, var_name, gj in grupos_linhas:
            gj.add_to(fg); fg.add_to(m)
            m.get_root().html.add_child(folium.Element(f"<script>window['{var_name}'] = {gj.get_name()};</script>"))
        for mc in grupos_pontos:
            mc.add_to(m)

        if lat_min < lat_max and lon_min < lon_max:
            m.fit_bounds([[lat_min, lon_min], [lat_max, lon_max]])

        folium.FitOverlays(fly=True, fit_on_map_load=True).add_to(m)
        folium.LayerControl(collapsed=True).add_to(m)

        custom_css = "<style>.leaflet-control-layers{margin-top:30px!important;}</style>"
        m.get_root().html.add_child(folium.Element(custom_css))
        bump_js = """
        <script>
        (function(){function bump(){var note=document.getElementById('map-note');
        var ctrl=document.querySelector('.leaflet-top.leaflet-right'); if(!note||!ctrl)return;
        var h=note.getBoundingClientRect().height; ctrl.style.marginTop=(h+12)+'px';}
        window.addEventListener('load',bump); window.addEventListener('resize',bump);
        document.querySelectorAll('#map-note img').forEach(function(img){if(img.complete)return; img.addEventListener('load',bump);});
        setTimeout(bump,300);})();
        </script>"""
        m.get_root().html.add_child(folium.Element(bump_js))

        m.save(output_html)
        feedback.pushInfo(self.tr(f"Mapa exportado: {output_html}"))
        return {self.OUTPUT_HTML: output_html}

    # ---------- helpers ----------
    def _render_raster_to_png(self, rlayer, out_dir, width_px=2000):
        """Renderiza um QgsRasterLayer (com estilo do QGIS) para PNG com alfa.
           Retorna (png_path_absoluto, extent_original)."""
        safe = re.sub(r'\W|^(?=\d)', '_', rlayer.name())
        png_path = os.path.join(out_dir, f"{safe}.png")

        ext = rlayer.extent()
        w = max(1, int(width_px))
        h = max(1, int(round(w * (ext.height() / ext.width()))))

        image_format = getattr(QImage, "Format_ARGB32", None)
        if image_format is None and hasattr(QImage, "Format"):
            image_format = QImage.Format.Format_ARGB32
        img = QImage(w, h, image_format)
        img.fill(0)  # transparente

        ms = QgsMapSettings()
        ms.setLayers([rlayer])
        ms.setExtent(ext)
        ms.setOutputSize(QSize(w, h))

        p = QPainter(img)
        job = QgsMapRendererCustomPainterJob(ms, p)
        job.start(); job.waitForFinished(); p.end()
        img.save(png_path, "PNG")
        return png_path, ext

    def _popup_table(self, layer, feat):
        html = "<table style='border-collapse:collapse;width:100%;'><tr><th style='border:1px solid black;padding:4px;'>Campo</th><th style='border:1px solid black;padding:4px;'>Valor</th></tr>"
        for field in layer.fields():
            nome = field.name()
            valor = self._qvariant_to_py(feat[nome])
            if self._is_empty(valor): continue
            html += f"<tr><td style='border:1px solid black;padding:4px;'><b>{nome}</b></td><td style='border:1px solid black;padding:4px;'>{valor}</td></tr>"
        html += "</table>"
        return folium.Popup(html, max_width=300)

    def _popup_table_dict(self, attrs):
        html = "<table style='border-collapse:collapse;width:100%;'><tr><th style='border:1px solid black;padding:4px;'>Campo</th><th style='border:1px solid black;padding:4px;'>Valor</th></tr>"
        for nome, valor in attrs.items():
            valor = self._qvariant_to_py(valor)
            if self._is_empty(valor): continue
            html += f"<tr><td style='border:1px solid black;padding:4px;'><b>{nome}</b></td><td style='border:1px solid black;padding:4px;'>{valor}</td></tr>"
        html += "</table>"
        return html

    def _qvariant_to_py(self, value):
        if value is None or value is QGIS_NULL: return None
        if hasattr(value, 'toPyObject'): value = value.toPyObject()
        if isinstance(value, QDate):     return value.toString("dd/MM/yyyy")
        if isinstance(value, QDateTime): return value.toString("dd/MM/yyyy HH:mm:ss")
        return value if isinstance(value, (int, float, str, bool)) else str(value)

    def _is_empty(self, v):
        if v is None: return True
        if isinstance(v, float) and math.isnan(v): return True
        if isinstance(v, str):
            s = v.strip()
            if not s or s.upper() in {"NULL","NULO","NA","NAN","NONE"}: return True
        return False

    def name(self): return 'export_html_webmap'
    def displayName(self): return self.tr('Exportar WebMapa')
    def group(self): return 'WebGIS'
    def groupId(self): return 'webgis'
    def createInstance(self): return ExportFoliumMap()
    def shortHelpString(self): return self.tr("""Gera HTML interativo com Folium (vetores GeoJSON e rasters renderizados como ImageOverlay).""")
    def tr(self, string): return QCoreApplication.translate('Processing', string)
