# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Processing
 Dashboard de Pontos (Flet) — janela Flet (sem navegador)
 Autor: Geraldo Pereira de Morais Júnior
 Email: geraldo.pmj@gmail.com
 ***********************************************/
"""

__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-08-31'
__copyright__ = '(C) 2025'
__revision__ = '$Format:%H$'

import math
import re
import signal, threading
import datetime as dt
from collections import Counter, defaultdict
import io, base64  # <-- [NOVO] para fallback do gráfico

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterBoolean,
    QgsProcessingException,
    QgsVectorLayer,
    QgsFeatureRequest,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
)

class PointDashboardProcessing(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    DARK_THEME = 'DARK_THEME'

    # -------------------- Metadados / Parâmetros --------------------
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT, self.tr('Camada de pontos'), types=[QgsProcessing.TypeVectorPoint]
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DARK_THEME, self.tr('Iniciar em tema escuro'), defaultValue=False
        ))

    def tr(self, string): return QCoreApplication.translate('Processing', string)
    def name(self): return 'dashboard_de_prospeccao'
    def displayName(self): return self.tr('Dashboard de Prospecção')
    def group(self): return 'Dashboard'
    def groupId(self): return 'dashboard'
    def createInstance(self): return PointDashboardProcessing()
    def shortHelpString(self):
        return self.tr(
            "Abre um dashboard interativo em janela Flet para análise de prospecção. "
            "Esta ferramenta é interativa e não gera arquivo HTML de saída."
        )

    # ------------------------ Dependências --------------------------
    @staticmethod
    def _check_deps():
        try:
            import flet  # noqa
            import flet_desktop  # noqa
            from flet_map import Map  # noqa
            import matplotlib  # noqa
        except Exception as e:
            raise QgsProcessingException(
                "Dependências ausentes no Python do QGIS.\n"
                "Instale:\n  pip install flet flet-desktop flet-map matplotlib\n"
                f"Detalhes: {e}"
            )

    # ------------------------ Utilitários ---------------------------
    @staticmethod
    def _safe_get(feature, field_name, default=None):
        try:
            if field_name in feature.fields().names():
                v = feature[field_name]
                return v if v not in (None, "") else default
        except Exception:
            pass
        return default

    @staticmethod
    def _to_date(obj):
        if obj is None: return None
        try: return obj.toPyDate()  # QDate
        except Exception: pass
        if isinstance(obj, dt.date): return obj
        if isinstance(obj, str) and obj.strip():
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                try: return dt.datetime.strptime(obj.strip(), fmt).date()
                except ValueError: continue
        return None

    @staticmethod
    def _get_to_wgs84_transform(src_crs):
        tgt = QgsCoordinateReferenceSystem("EPSG:4326")
        if not src_crs or src_crs.authid() == tgt.authid(): return None
        return QgsCoordinateTransform(src_crs, tgt, QgsProject.instance())

    @classmethod
    def _layer_to_records(cls, layer: QgsVectorLayer):
        if layer is None: return []
        xform = cls._get_to_wgs84_transform(layer.crs())
        field_names = [
            "id", "Name", "Longitude", "Latitude", "Resp", "Data",
            "Veg", "Relevo", "Realizado", "Motivo",
        ] + [f"{p}{c}" for c in range(1, 6) for p in ("prof_C", "cor_C", "vstg_C", "type_vstgC", "qnt_vstgC")]
        present = set(layer.fields().names())
        recs = []
        for feat in layer.getFeatures(QgsFeatureRequest()):
            row = {n: (cls._safe_get(feat, n, None) if n in present else None) for n in field_names}
            try:
                pt = feat.geometry().asPoint()
                if xform: pt = xform.transform(pt)
                lon, lat = pt.x(), pt.y()
            except Exception:
                lon, lat = row.get("Longitude"), row.get("Latitude")
            row["Longitude"] = float(lon) if lon not in (None, "") else None
            row["Latitude"]  = float(lat) if lat not in (None, "") else None
            row["Data"] = cls._to_date(row.get("Data"))
            recs.append(row)
        return recs

    # ---------------------- App Flet (Janela) -----------------------
    @classmethod
    def _run_flet_app(cls, records, start_dark=False):
        import flet as ft
        # [ALTERADO] Import seguro do MatplotlibChart (pode não existir em certas versões)
        try:
            from flet.matplotlib_chart import MatplotlibChart
        except Exception:
            MatplotlibChart = None
        import matplotlib.pyplot as plt
        from flet_map import Map, MapLatitudeLongitude, TileLayer, MarkerLayer, Marker

        # [NOVO] Fallback para exibir figura Matplotlib como PNG base64 quando MatplotlibChart não existir
        def mpl_control(fig, *, height=360):
            if MatplotlibChart is not None:
                return MatplotlibChart(fig, expand=True)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", transparent=True)
            data = base64.b64encode(buf.getvalue()).decode("ascii")
            buf.close()
            return ft.Image(src=data, height=height, fit=ft.BoxFit.CONTAIN)

        def is_truthy(x):
            if x is None: return False
            return str(x).strip().lower() in {"sim","yes","true","1","feito","realizado"}

        def parse_num(v):
            if v is None or (isinstance(v,str) and not v.strip()): return None
            if isinstance(v,(int,float)):
                try: f=float(v); return f if math.isfinite(f) else None
                except Exception: return None
            try:
                f=float(str(v).strip().replace(",","."))
                return f if math.isfinite(f) else None
            except Exception: return None

        def deepest_depth(row):
            for c in range(5,0,-1):
                fval = parse_num(row.get(f"prof_C{c}"))
                if fval is not None and fval>0: return fval
            return None

        def row_vest_counts(row):
            per_layer, observed, has_any = {}, {}, False
            for k in range(1,6):
                q = row.get(f"qnt_vstgC{k}")
                t = row.get(f"vstg_C{k}") or row.get(f"type_vstgC{k}")
                n = parse_num(q)
                if n is None:
                    if t is not None and str(t).strip():
                        n=1.0; observed[k]=True
                    else:
                        n=0.0; observed[k]=False
                else:
                    observed[k]=True
                per_layer[k]=max(0.0,n)
                if per_layer[k]>0: has_any=True
            return per_layer, has_any, observed

        def has_vestigio(row):
            _,h,_ = row_vest_counts(row); return h

        def compute_vest_stats(rows):
            totals={k:0.0 for k in range(1,6)}; obs={k:0 for k in range(1,6)}; pts=0
            for r in rows:
                per,has_any,ob = row_vest_counts(r)
                if has_any: pts+=1
                for k in range(1,6):
                    totals[k]+=per[k]
                    if ob[k]: obs[k]+=1
            means={k:(totals[k]/obs[k]) if obs[k]>0 else None for k in range(1,6)}
            return {"total_vest": sum(totals.values()),
                    "totals_per_layer": totals,
                    "means_per_layer": means,
                    "pontos_com_vest": pts}

        def fmt_series_totals(d):
            return " | ".join([f"C{k}: {int(round(d.get(k,0.0)))}" for k in range(1,6)])

        def fmt_series_means(d):
            parts=[]
            for k in range(1,6):
                v=d.get(k,None); parts.append(f"C{k}: {'—' if v is None else f'{v:.2f}'}")
            return " | ".join(parts)

        def make_base_tile(dark: bool)->TileLayer:
            return TileLayer(url_template=(
                "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" if dark else
                "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"))

        def build_markers(rows):
            ms=[]
            for r in rows:
                lat=r.get("Latitude"); lon=r.get("Longitude")
                if lat is None or lon is None: continue
                realizado=is_truthy(r.get("Realizado"))
                color=ft.Colors.RED
                if realizado: color=ft.Colors.BLUE
                if has_vestigio(r): color=ft.Colors.GREEN
                per,has_any,_=row_vest_counts(r)
                vest_total=int(round(sum(per.values())))
                vest_txt=f"{'Sim' if has_any else 'Não'} ({vest_total})"
                motivo=r.get("Motivo")
                motivo_txt=f" | Motivo: {motivo}" if (not realizado and motivo) else ""
                tooltip=(f"{r.get('Name') or ''} | {r.get('Data') or ''}\n"
                         f"Relevo: {r.get('Relevo') or '—'} | Vegetação: {r.get('Veg') or '—'}\n"
                         f"Responsável: {r.get('Resp') or '—'}\n"
                         f"Realizado: {'Sim' if realizado else 'Não'}{motivo_txt}\n"
                         f"Vestígios: {vest_txt}")
                ms.append(Marker(
                    coordinates=MapLatitudeLongitude(latitude=float(lat), longitude=float(lon)),
                    content=ft.Container(width=4, height=4, bgcolor=color, border_radius=2, tooltip=tooltip),
                ))
            return ms

        def compute_bbox(rows):
            coords=[(r.get("Latitude"),r.get("Longitude")) for r in rows
                    if r.get("Latitude") is not None and r.get("Longitude") is not None]
            if not coords: return None
            lats,lons=zip(*coords)
            return (min(lats),min(lons),max(lats),max(lons))

        def aggregate_by_person(rows):
            b=defaultdict(lambda:{"total":0,"realizados":0,"datas":set(),"depth_sum":0.0,"depth_n":0})
            for r in rows:
                resp=r.get("Resp") or "—"
                bb=b[resp]; bb["total"]+=1
                if is_truthy(r.get("Realizado")): bb["realizados"]+=1
                d=r.get("Data")
                if isinstance(d, dt.date): bb["datas"].add(d)
                dd=deepest_depth(r)
                if dd is not None: bb["depth_sum"]+=dd; bb["depth_n"]+=1
            out={}
            for resp,bb in b.items():
                dias=max(1,len(bb["datas"]))
                prof_media=(bb["depth_sum"]/bb["depth_n"]) if bb["depth_n"]>0 else None
                out[resp]={"total":bb["total"],"realizados":bb["realizados"],
                           "pct": (bb["realizados"]/bb["total"]) if bb["total"] else 0.0,
                           "prof_media":prof_media,"media_pts_dia":bb["total"]/dias,
                           "dias_observados":dias}
            return out

        def figure_points_per_day(rows,*,dark=False):
            per=Counter()
            for r in rows:
                d=r.get("Data")
                if isinstance(d, dt.date): per[d]+=1
            import matplotlib.pyplot as plt
            fig,ax=plt.subplots(facecolor="none"); ax.set_facecolor("none")
            if not per:
                ax.text(0.5,0.5,"Sem dados de Data",ha="center",va="center",color=("white" if dark else "black"))
                ax.axis("off"); fig.tight_layout(); return fig
            days=sorted(per.keys()); xs=list(range(len(days))); ys=[per[d] for d in days]
            ax.plot(xs,ys,marker='o',markersize=4)
            fg="white" if dark else "black"
            ax.set_title("Pontos / Dia",fontsize=14,weight="bold",color=fg)
            ax.set_ylabel("Quantidade de Pontos",color=fg); ax.set_xlabel("Data",color=fg); ax.tick_params(colors=fg)
            for sp in ax.spines.values(): sp.set_color(fg)
            ax.set_xticks(xs); ax.set_xticklabels([d.strftime("%Y-%m-%d") for d in days],rotation=45,ha="right",color=fg)
            ax.grid(True,linestyle="--",linewidth=0.3); fig.tight_layout(); return fig

        def app(page: ft.Page):
            page.title="Dashboard"; page.padding=24
            page.theme_mode = ft.ThemeMode.DARK if start_dark else ft.ThemeMode.LIGHT
            page.scroll=None
            try: page.window.maximized=True
            except Exception: pass

            def toggle_theme(_):
                page.theme_mode = ft.ThemeMode.DARK if page.theme_mode==ft.ThemeMode.LIGHT else ft.ThemeMode.LIGHT
                update_basemap(); refresh()

            theme_btn=ft.IconButton(icon=ft.Icons.DARK_MODE, tooltip="Alternar tema", on_click=toggle_theme)
            page.appbar=ft.AppBar(leading=ft.Icon(ft.Icons.MAP), title=ft.Text("Dashboard"), center_title=True, actions=[theme_btn])

            filter_done=ft.Dropdown(label="Realizado", value="Todos",
                                    options=[ft.dropdown.Option(v) for v in ("Todos","Sim","Não")], width=160)
            PERIOD=["Todos","Hoje","Ontem","Últimos 7 dias","Últimos 30 dias","Este mês","Mês passado","Este ano","Ano passado"]
            filter_period=ft.Dropdown(label="Período", value="Todos",
                                      options=[ft.dropdown.Option(v) for v in PERIOD], width=220)
            filter_search=ft.TextField(label="Busca (Ponto/Responsável/Motivo)", width=400)

            def period_range(sel:str):
                today=dt.date.today()
                if sel=="Todos": return (None,None)
                if sel=="Hoje": return (today,today)
                if sel=="Ontem": d=today-dt.timedelta(days=1); return (d,d)
                if sel=="Últimos 7 dias": return (today-dt.timedelta(days=6),today)
                if sel=="Últimos 30 dias": return (today-dt.timedelta(days=29),today)
                if sel=="Este mês": d0=today.replace(day=1); return (d0,today)
                if sel=="Mês passado":
                    first_this=today.replace(day=1); last_prev=first_this-dt.timedelta(days=1)
                    first_prev=last_prev.replace(day=1); return (first_prev,last_prev)
                if sel=="Este ano": d0=today.replace(month=1,day=1); return (d0,today)
                if sel=="Ano passado":
                    d0=today.replace(year=today.year-1,month=1,day=1)
                    d1=today.replace(year=today.year-1,month=12,day=31); return (d0,d1)
                return (None,None)

            def apply_filters(rows):
                done_sel = filter_done.value
                term_raw = (filter_search.value or "").strip()
                pat = re.compile(rf"\b{re.escape(term_raw)}\b", re.IGNORECASE) if term_raw else None
                d0, d1 = period_range(filter_period.value)

                out = []
                for r in rows:
                    done_str = "Sim" if is_truthy(r.get("Realizado")) else "Não"
                    if done_sel != "Todos" and done_str != done_sel:
                        continue

                    hay = " ".join([str(r.get("Name") or ""), str(r.get("Resp") or ""), str(r.get("Motivo") or "")])

                    if pat and not pat.search(hay):
                        continue

                    d = r.get("Data")
                    if d0 and (not d or d < d0):
                        continue
                    if d1 and (not d or d > d1):
                        continue

                    out.append(r)
                return out

            aplicar_btn=ft.ElevatedButton("Aplicar", on_click=lambda _: refresh())

            def kcard(title, txt):
                return ft.Card(elevation=2, content=ft.Container(padding=12,
                    content=ft.Column([ft.Text(title,size=12,opacity=1), txt], spacing=4)))
            k_total_txt=ft.Text("—", size=24, weight=ft.FontWeight.W_600)
            k_done_txt =ft.Text("—", size=24, weight=ft.FontWeight.W_600)
            k_depth_txt=ft.Text("—", size=24, weight=ft.FontWeight.W_600)
            k_total=kcard("Total de pontos", k_total_txt)
            k_done =kcard("Realizados / Total", k_done_txt)
            k_depth=kcard("Profundidade média (m)", k_depth_txt)

            def chips_panel(title):
                return ft.Card(elevation=2, content=ft.Container(padding=12, content=ft.Column([
                    ft.Text(title,size=12,opacity=1),
                    ft.Container(content=ft.Column([ft.Row(controls=[], wrap=True, spacing=8, run_spacing=8)],
                                                   scroll=ft.ScrollMode.AUTO), height=40)
                ], spacing=8)))
            relief_panel=chips_panel("Pontos por Relevo")
            vegetation_panel=chips_panel("Pontos por Vegetação")

            markers_layer=MarkerLayer(markers=[])
            fmap=Map(initial_center=MapLatitudeLongitude(latitude=-14.2,longitude=-51.9),
                     initial_zoom=3, layers=[make_base_tile(False), markers_layer], height=360, expand=True)
            chart_ct=ft.Container(height=360, padding=ft.padding.only(top=8))

            cols=[ft.DataColumn(ft.Text(h)) for h in ["Name","Longitude","Latitude","Resp","Data","Relevo","Vegetação","Realizado","Motivo"]]
            table=ft.DataTable(columns=cols, rows=[], data_row_min_height=34, column_spacing=18, divider_thickness=0.3, show_checkbox_column=False)

            people_panel=ft.Container(expand=True)

            vest_cards_row = ft.ResponsiveRow([], columns=12, run_spacing=12)

            def update_basemap():
                dark=(page.theme_mode==ft.ThemeMode.DARK)
                try: fmap.layers[0]=make_base_tile(dark)
                except Exception: fmap.layers=[make_base_tile(dark), markers_layer]

            def update_kpis(rows):
                total=len(rows)
                done=sum(1 for r in rows if is_truthy(r.get("Realizado")))
                depths=[deepest_depth(r) for r in rows]
                depths=[d for d in depths if d is not None and d>0]
                avg=(sum(depths)/len(depths)) if depths else None
                k_total_txt.value=f"{total}"
                k_done_txt.value =f"{done} / {total} ({(100.0*done/total):.1f}% )" if total else "0 / 0 (—)"
                k_depth_txt.value=f"{avg:.2f}" if avg is not None else "—"
                rel=Counter((r.get("Relevo") or "—") for r in rows)
                veg=Counter((r.get("Veg") or "—") for r in rows)
                def build_chips(counter):
                    if not counter: return [ft.Chip(label=ft.Text("—"), bgcolor=ft.Colors.GREY_200)]
                    items=sorted(counter.items(), key=lambda x:(-x[1], str(x[0])))
                    return [ft.Chip(label=ft.Text(f"{k or '—'}: {v}")) for k,v in items]
                relief_panel.content.content.controls[1].content.controls[0].controls = build_chips(rel)
                vegetation_panel.content.content.controls[1].content.controls[0].controls = build_chips(veg)

            def update_vest(rows):
                vs=compute_vest_stats(rows)
                means_vals=[v for v in vs["means_per_layer"].values() if v is not None]
                mean_over=(sum(means_vals)/len(means_vals)) if means_vals else None
                cards=[
                    ("Total de vestígios", f"{int(round(vs['total_vest']))}", fmt_series_totals(vs["totals_per_layer"])),
                    ("Média de vestígios por camada", "—" if mean_over is None else f"{mean_over:.2f}", fmt_series_means(vs["means_per_layer"])),
                    ("Pontos com vestígio", f"{vs['pontos_com_vest']}", "qualquer camada C1..C5"),
                ]
                built=[]
                for title,val,sub in cards:
                    built.append(ft.Container(
                        col={"xs":12,"md":4},
                        content=ft.Card(elevation=2, content=ft.Container(
                            padding=12, content=ft.Column([
                                ft.Text(title,size=12,opacity=1),
                                ft.Text(val,size=22,weight=ft.FontWeight.W_700),
                                ft.Text(sub,size=11,color=ft.Colors.BLACK54) if sub else ft.Container()
                            ], spacing=6, tight=True)
                        ))
                    ))
                vest_cards_row.controls = built

            _last_bbox={"v":None}
            def update_map(rows):
                markers_layer.markers=build_markers(rows)
                bbox=compute_bbox(rows)
                if bbox and bbox!=_last_bbox["v"]:
                    s,w,n,e=bbox
                    try:
                        fmap.fit_bounds(MapLatitudeLongitude(latitude=s,longitude=w),
                                        MapLatitudeLongitude(latitude=n,longitude=e))
                    except Exception:
                        lat_c=(s+n)/2.0; lon_c=(w+e)/2.0
                        fmap.initial_center=MapLatitudeLongitude(latitude=lat_c,longitude=lon_c)
                        fmap.initial_zoom=11
                _last_bbox["v"]=bbox

            def update_chart(rows):
                dark=(page.theme_mode==ft.ThemeMode.DARK)
                fig=figure_points_per_day(rows, dark=dark)
                # [ALTERADO] usar controle resiliente (MatplotlibChart se existir; caso contrário, PNG base64)
                chart_ct.content = mpl_control(fig, height=360)
                plt.close(fig)

            def update_table(rows):
                def fmt(x):
                    if isinstance(x,float): return f"{x:.6f}"
                    return "" if x is None else str(x)
                rs=[]
                for r in rows:
                    rs.append(ft.DataRow(cells=[
                        ft.DataCell(ft.Text(fmt(r.get("Name")))),
                        ft.DataCell(ft.Text(fmt(r.get("Longitude")))),
                        ft.DataCell(ft.Text(fmt(r.get("Latitude")))),
                        ft.DataCell(ft.Text(fmt(r.get("Resp")))),
                        ft.DataCell(ft.Text(fmt(r.get("Data")))),
                        ft.DataCell(ft.Text(fmt(r.get("Relevo")))),
                        ft.DataCell(ft.Text(fmt(r.get("Veg")))),
                        ft.DataCell(ft.Text("Sim" if is_truthy(r.get("Realizado")) else "Não")),
                        ft.DataCell(ft.Text(fmt(r.get("Motivo")))),
                    ]))
                table.rows=rs

            def build_people_tab(rows):
                dados=aggregate_by_person(rows)
                if not dados: return ft.Container(ft.Text("Sem dados."), padding=16, expand=True)
                by_person=defaultdict(list)
                for r in rows: by_person[r.get("Resp") or "—"].append(r)
                cols=[]
                for pessoa,m in sorted(dados.items(), key=lambda kv: (str(kv[0]) or "—")):
                    def kcard(title,val):
                        return ft.Card(elevation=2, content=ft.Container(padding=12, content=ft.Column([
                            ft.Text(title,size=12,opacity=1),
                            ft.Text(val,size=22,weight=ft.FontWeight.W_700)
                        ], spacing=4)))
                    k1=kcard("Realizados / Total", f"{m['realizados']} / {m['total']} ({m['pct']*100:.1f}%)")
                    k2=kcard("Profundidade média (m)", "—" if m["prof_media"] is None else f"{m['prof_media']:.2f}")
                    k3=kcard("Média pontos/dia", f"{m['media_pts_dia']:.2f}")
                    vstats=compute_vest_stats(by_person[pessoa])
                    means=vstats["means_per_layer"]; means_vals=[v for v in means.values() if v is not None]
                    mean_over=(sum(means_vals)/len(means_vals)) if means_vals else None
                    v1=ft.Card(elevation=2, content=ft.Container(padding=12, content=ft.Column([
                        ft.Text("Total de vestígios",size=12,opacity=1),
                        ft.Text(f"{int(round(vstats['total_vest']))}",size=22,weight=ft.FontWeight.W_700),
                        ft.Text(fmt_series_totals(vstats["totals_per_layer"]),size=11,color=ft.Colors.BLACK54)
                    ], spacing=6, tight=True)))
                    v2=ft.Card(elevation=2, content=ft.Container(padding=12, content=ft.Column([
                        ft.Text("Média de vestígios por camada",size=12,opacity=1),
                        ft.Text("—" if mean_over is None else f"{mean_over:.2f}",size=22,weight=ft.FontWeight.W_700),
                        ft.Text(fmt_series_means(means),size=11,color=ft.Colors.BLACK54)
                    ], spacing=6, tight=True)))
                    v3=ft.Card(elevation=2, content=ft.Container(padding=12, content=ft.Column([
                        ft.Text("Pontos com vestígio",size=12,opacity=1),
                        ft.Text(f"{vstats['pontos_com_vest']}",size=22,weight=ft.FontWeight.W_700),
                        ft.Text("qualquer camada C1..C5",size=11,color=ft.Colors.BLACK54)
                    ], spacing=6, tight=True)))
                    cols.append(ft.Container(width=260, content=ft.Column([
                        ft.Text(str(pessoa), size=16, weight=ft.FontWeight.W_800),
                        k1,k2,k3,v1,v2,v3,
                        ft.Text(f"em {m['dias_observados']} dia(s) observado(s)", size=11, color=ft.Colors.BLACK54)
                    ], spacing=10, tight=True)))
                inner=ft.Row(controls=cols, spacing=16, vertical_alignment=ft.CrossAxisAlignment.START, scroll=ft.ScrollMode.AUTO)
                return ft.Container(padding=12, content=ft.Column(controls=[inner], scroll=ft.ScrollMode.AUTO, expand=True), expand=True)

            def refresh():
                rows=apply_filters(records)
                update_basemap()
                update_chart(rows)
                update_map(rows)
                update_kpis(rows)
                update_vest(rows)
                people_panel.content=build_people_tab(rows)
                update_table(rows)
                page.update()

            # ---- Layout raiz
            filters_row=ft.ResponsiveRow([
                ft.Container(filter_done,   col={"xs":12,"md":2}),
                ft.Container(filter_period, col={"xs":12,"md":3}),
                ft.Container(filter_search, col={"xs":12,"md":5}),
                ft.Container(aplicar_btn,   col={"xs":12,"md":1}),
            ], columns=12, run_spacing=12)
            filters_row=ft.Container(filters_row, margin=ft.margin.only(top=12,bottom=4), padding=ft.padding.only(top=4,bottom=4))

            metrics_top=ft.ResponsiveRow([
                ft.Container(k_total, col={"xs":12,"md":4}),
                ft.Container(k_done,  col={"xs":12,"md":4}),
                ft.Container(k_depth, col={"xs":12,"md":4}),
            ], columns=12, run_spacing=12)

            chips_right=ft.Container(col={"xs":12,"md":4}, content=ft.Column([relief_panel, vegetation_panel], spacing=12))
            metrics_left=ft.Container(col={"xs":12,"md":8}, content=ft.Column([metrics_top, vest_cards_row], spacing=12))
            kpis_block=ft.ResponsiveRow([metrics_left, chips_right], columns=12, run_spacing=12)

            main_panel=ft.ResponsiveRow([
                ft.Container(ft.Column([
                    filters_row, kpis_block,
                    ft.ResponsiveRow([
                        ft.Container(fmap,     col={"xs":12,"md":6}),
                        ft.Container(chart_ct, col={"xs":12,"md":6}),
                    ], columns=12, run_spacing=12)
                ], spacing=16), col={"xs":12})
            ], columns=12, run_spacing=12)

            table_panel=ft.Container(
                content=ft.Column([table], scroll=ft.ScrollMode.AUTO, expand=True),
                expand=True
            )
            tab_bar=ft.TabBar(
                tabs=[
                    ft.Tab(label="Visão geral", icon=ft.Icons.DASHBOARD),
                    ft.Tab(label="Pessoas", icon=ft.Icons.GROUP),
                    ft.Tab(label="Tabela", icon=ft.Icons.TABLE_CHART),
                ]
            )
            tab_view=ft.TabBarView(
                controls=[
                    main_panel,
                    people_panel,
                    table_panel,
                ],
                expand=True,
            )
            tabs=ft.Tabs(
                selected_index=0,
                animation_duration=300,
                expand=True,
                length=3,
                content=ft.Column(
                    controls=[
                        tab_bar,
                        ft.Container(content=tab_view, expand=True),
                    ],
                    spacing=0,
                    expand=True,
                ),
            )

            if not records:
                page.add(ft.Container(ft.Text("Nenhuma feição válida."), padding=8, bgcolor=ft.Colors.AMBER_100, border_radius=8))
            page.add(tabs)
            refresh()

        # --- Neutraliza signal.signal quando não estamos na main thread ---
        _original_signal = signal.signal
        def _safe_signal(sig, handler):
            if threading.current_thread() is threading.main_thread():
                return _original_signal(sig, handler)
            return None
        signal.signal = _safe_signal

        # Executa em janela Flet (bloqueante) — [ALTERADO] com try/finally para garantir restauração
        import flet as ft
        try:
            ft.app(target=app, view=ft.AppView.FLET_APP)
        finally:
            # (Restaurar handler original mesmo em caso de exceção)
            signal.signal = _original_signal

    # ---------------------- Execução Processing ----------------------
    def processAlgorithm(self, parameters, context, feedback):
        self._check_deps()

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if not layer or not isinstance(layer, QgsVectorLayer):
            raise QgsProcessingException(self.tr("Camada inválida."))

        feedback.pushInfo(self.tr("Lendo feições e normalizando para EPSG:4326..."))
        records = self._layer_to_records(layer)
        feedback.pushInfo(self.tr(f"{len(records)} registro(s) preparado(s)."))

        start_dark = self.parameterAsBool(parameters, self.DARK_THEME, context)
        feedback.pushInfo(self.tr("Abrindo dashboard (QGIS ficará bloqueado até você fechar a janela)..."))

        # BLOQUEANTE: roda Flet em janela (sem navegador)
        self._run_flet_app(records, start_dark=start_dark)

        return {}
