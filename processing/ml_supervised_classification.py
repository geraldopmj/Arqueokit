# -*- coding: utf-8 -*-
"""
/***********************************************
 Arqueokit - QGIS Plugin
 Classificação Supervisionada
 Autor: Geraldo Pereira de Morais Júnior
 Email: geraldo.pmj@gmail.com
 ***********************************************/
"""
__author__ = 'Geraldo Pereira de Morais Júnior'
__date__ = '2025-06-07'
__copyright__ = '(C) 2025 by Geraldo Pereira de Morais Júnior'
__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField, QgsProcessingParameterString,
    QgsProcessingParameterNumber, QgsProcessingParameterFileDestination,
    QgsProcessingParameterFile, QgsProcessingParameterRasterDestination,
    QgsProcessingParameterBoolean,
    QgsProcessingException, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsProject, QgsPointXY, QgsGeometry
)

import os, json, numpy as np, rasterio, traceback
from rasterio.transform import rowcol
from joblib import dump, load

from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score, cohen_kappa_score

from scipy import ndimage as ndi

# -------------------- scikit-image: imports compatíveis -------------------- #
# view_as_windows é estável
try:
    from skimage.util import view_as_windows as sk_viewwin
except Exception as e:
    raise

# rank.entropy (para entropia local)
_HAS_SKIMAGE_RANK = False
try:
    from skimage.filters.rank import entropy as sk_entropy
    from skimage.morphology import square as sk_square
    _HAS_SKIMAGE_RANK = True
except Exception:
    _HAS_SKIMAGE_RANK = False

# -------------------- Utilidades -------------------- #

def tr(s): return QCoreApplication.translate('Processing', s)

def parse_band_mapping(text):
    m = {}
    if not text: return m
    for tok in text.split(','):
        k, v = tok.split('=')
        m[k.strip().upper()] = int(v.strip()) - 1  # 1-based -> 0-based
    return m

def safe_div(num, den):
    with np.errstate(divide='ignore', invalid='ignore'):
        out = num / den
        out[~np.isfinite(out)] = 0
    return out

def available_indices(keys):
    """Índices (gerados se houver bandas suficientes)."""
    defs = []
    has = {k: (k in keys) for k in ['R','G','B','NIR','SWIR1','SWIR2']}

    if has['NIR'] and has['R']:
        defs += [
            ('NDVI',   lambda B: safe_div(B['NIR'] - B['R'], B['NIR'] + B['R'])),
            ('EVI2',   lambda B: 2.5 * safe_div(B['NIR'] - B['R'], B['NIR'] + 2.4*B['R'] + 1)),
            ('SAVI',   lambda B: 1.7 * safe_div(B['NIR'] - B['R'], B['NIR'] + B['R'] + 0.7)),
            ('MSAVI2', lambda B: (2*B['NIR'] + 1 - np.sqrt((2*B['NIR'] + 1)**2 - 8*(B['NIR'] - B['R'])))/2),
            ('OSAVI',  lambda B: 1.16 * safe_div(B['NIR'] - B['R'], B['NIR'] + B['R'] + 0.16)),
        ]
    if has['SWIR2'] and has['SWIR1']:
        defs += [
            ('CAI',  lambda B: safe_div(B['SWIR2'], B['SWIR1'])),
            ('NBR2', lambda B: safe_div(B['SWIR1'] - B['SWIR2'], B['SWIR1'] + B['SWIR2'])),
        ]
    if has['NIR'] and has['SWIR1']:
        defs += [
            ('NDWI', lambda B: safe_div(B['NIR'] - B['SWIR1'], B['NIR'] + B['SWIR1'])),
            ('NDMI', lambda B: safe_div(B['NIR'] - B['SWIR1'], B['NIR'] + B['SWIR1'])),
            ('BSCI', lambda B: safe_div(B['SWIR1'] - B['NIR'], B['SWIR1'] + B['NIR'])),
        ]
    if has['NIR'] and has['G']:
        defs += [
            ('GCVI',  lambda B: safe_div(B['NIR'], B['G']) - 1),
            ('GNDVI', lambda B: safe_div(B['NIR'] - B['G'], B['NIR'] + B['G'])),
        ]
    if has['R'] and has['NIR'] and has['SWIR2']:
        defs.append(('HallCover', lambda B: (-0.017*B['R']) + (-0.007*B['NIR']) + (-0.079*B['SWIR2']) + 5.22))
    if has['B'] and has['G']:
        defs.append(('PRI',  lambda B: safe_div(B['B'] - B['G'], B['B'] + B['G'])))
    if has['G'] and has['R'] and has['B']:
        defs += [
            ('VARI', lambda B: safe_div(B['G'] - B['R'], B['G'] + B['R'] - B['B'])),
            ('EXG',  lambda B: 2*B['G'] - B['R'] - B['B']),
        ]
    if has['G'] and has['R']:
        defs += [
            ('GRVI', lambda B: safe_div(B['G'] - B['R'], B['G'] + B['R'])),
            ('NDTI', lambda B: safe_div(B['R'] - B['G'], B['R'] + B['G'])),
        ]
    # Não-colineares adicionais
    if all(k in keys for k in ('SWIR1','R','NIR','B')):
        defs.append(('BSI', lambda B: safe_div((B['SWIR1'] + B['R']) - (B['NIR'] + B['B']),
                                               (B['SWIR1'] + B['R']) + (B['NIR'] + B['B']))))
    if all(k in keys for k in ('NIR','R','B')):
        defs.append(('ARVI', lambda B: safe_div(B['NIR'] - (2*B['R'] - B['B']),
                                               B['NIR'] + (2*B['R'] - B['B']))))
    if all(k in keys for k in ('NIR','B','R')):
        defs.append(('SIPI', lambda B: safe_div(B['NIR'] - B['B'],
                                               B['NIR'] + B['R'])))
    if all(k in keys for k in ('NIR','SWIR2')):
        defs.append(('GVMI', lambda B: safe_div((B['NIR'] + 0.1) - (B['SWIR2'] + 0.02),
                                               (B['NIR'] + 0.1) + (B['SWIR2'] + 0.02))))
    if all(k in keys for k in ('NIR','SWIR1','SWIR2')):
        defs.append(('NMDI', lambda B: safe_div(B['NIR'] - (B['SWIR1'] - B['SWIR2']),
                                               B['NIR'] + (B['SWIR1'] - B['SWIR2']))))
    if has['G'] and has['NIR']:
        defs.append(('NDWI_McFeeters', lambda B: safe_div(B['G'] - B['NIR'], B['G'] + B['NIR'])))
    if has['NIR'] and has['SWIR2']:
        defs.append(('NBR', lambda B: safe_div(B['NIR'] - B['SWIR2'], B['NIR'] + B['SWIR2'])))
    if has['G'] and has['SWIR1']:
        defs.append(('NDSI', lambda B: safe_div(B['G'] - B['SWIR1'], B['G'] + B['SWIR1'])))
    if has['NIR'] and has['R'] and has['B']:
        defs.append(('EVI', lambda B: 2.5*((B['NIR'] - B['R'])/(B['NIR'] + 6*B['R'] - 7.5*B['B'] + 1))))
    return defs

def read_bands(ds, bandmap, feedback=None):
    arr, masks = {}, []
    for name, bidx in bandmap.items():
        if 0 <= bidx < ds.count:
            if feedback: feedback.pushInfo(f"[Abertura] Band {name} ← raster banda {bidx+1}")
            band = ds.read(bidx + 1).astype(np.float32)
            arr[name] = band
            m = ds.read_masks(bidx + 1) > 0
            if ds.nodatavals and ds.nodatavals[bidx] is not None:
                nod = ds.nodatavals[bidx]
                m &= band != nod
            masks.append(m)
        else:
            if feedback: feedback.pushInfo(f"[Aviso] Mapeamento '{name}={bidx+1}' ultrapassa nº de bandas ({ds.count}).")
    valid = np.logical_and.reduce(masks) if masks else None
    return arr, valid

def stack_features(arr_bands, feedback=None):
    feats, names = [], []
    # Bandas cruas
    for k in ['R','G','B','NIR','SWIR1','SWIR2']:
        if k in arr_bands:
            feats.append(arr_bands[k]); names.append(k)
    # Índices
    idx_defs = available_indices(arr_bands.keys())
    total = len(idx_defs)
    for i, (nm, fn) in enumerate(idx_defs, start=1):
        try:
            if feedback:
                feedback.setProgressText(f"Índice {nm} ({i}/{total})")
                feedback.pushInfo(f"[Índice] Computando {nm}…")
            feats.append(fn(arr_bands).astype(np.float32)); names.append(nm)
        except Exception as e:
            if feedback: feedback.pushInfo(f"[Índice] Falha em {nm}: {e}")
    X = np.stack(feats, axis=-1).astype(np.float32)
    if feedback: feedback.pushInfo(f"Bandas + Índices: {len(names)}")
    return X, names

def robust_fit_stats(X):
    stats = []
    r = X.reshape(-1, X.shape[-1])
    for j in range(r.shape[1]):
        col = r[:, j]; col = col[np.isfinite(col)]
        if col.size == 0: stats.append((0.0, 1.0)); continue
        q25, med, q75 = np.percentile(col, [25, 50, 75])
        iqr = max(q75 - q25, 1e-6)
        stats.append((float(med), float(iqr)))
    return stats

def robust_transform_inplace(X, stats):
    for j, (med, iqr) in enumerate(stats):
        X[..., j] = (X[..., j] - med) / iqr
    return X

# ---------- Amostragem estratificada (PyQGIS puro) ----------

def random_points_in_geom_qgs(union_geom: QgsGeometry, n_points: int, rng, max_tries=10000):
    if (union_geom is None) or union_geom.isEmpty():
        return []
    bbox = union_geom.boundingBox()
    xmin, xmax = bbox.xMinimum(), bbox.xMaximum()
    ymin, ymax = bbox.yMinimum(), bbox.yMaximum()
    pts, tries = [], 0
    while len(pts) < n_points and tries < max_tries:
        x = float(rng.uniform(xmin, xmax)); y = float(rng.uniform(ymin, ymax))
        pgeom = QgsGeometry.fromPointXY(QgsPointXY(x, y))
        if union_geom.contains(pgeom):
            pts.append((x, y))
        tries += 1
    return pts

def stratified_points(src, class_field, n_per_class, raster_crs):
    buckets = {}
    for f in src.getFeatures():
        if class_field not in f.fields().names():
            raise QgsProcessingException(f"Campo de classe '{class_field}' inexistente na camada.")
        cls = f[class_field]
        if cls is None: continue
        g = f.geometry()
        if (g is None) or g.isEmpty(): continue
        buckets.setdefault(str(cls), []).append(g)
    if not buckets:
        raise QgsProcessingException("Nenhuma geometria válida nas amostras.")

    ct = QgsCoordinateTransform(src.sourceCrs(), raster_crs, QgsProject.instance().transformContext())
    rng = np.random.default_rng(42)
    pts = []
    for cls, geoms in buckets.items():
        try:
            union = QgsGeometry.unaryUnion(geoms)
        except Exception:
            union = geoms[0]
            for g in geoms[1:]:
                union = union.combine(g)
        if (union is None) or union.isEmpty(): continue
        raw = random_points_in_geom_qgs(union, int(n_per_class), rng, max_tries=max(1000, 50*int(n_per_class)))
        for x, y in raw:
            p = ct.transform(QgsPointXY(x, y))
            pts.append((p.x(), p.y(), cls))
    if not pts:
        raise QgsProcessingException("Falha ao gerar pontos de amostra (aumente N por classe ou verifique geometrias).")
    return pts

def sample_stack_at_points(ds, stack, samples):
    rows, cols, y = [], [], []
    for x, yc, cls in samples:
        r, c = rowcol(ds.transform, x, yc, op=lambda z: int(np.floor(z)))
        if 0 <= r < stack.shape[0] and 0 <= c < stack.shape[1]:
            rows.append(r); cols.append(c); y.append(cls)
    if not rows:
        raise QgsProcessingException("Amostragem vazia: pontos fora do raster.")
    X = stack[rows, cols, :]
    y = np.array(y)
    return X, y

def encode_labels(y):
    classes = sorted(set(y.tolist()))
    m = {c: i for i, c in enumerate(classes)}  # 0..K-1
    y_enc = np.array([m[v] for v in y], dtype=np.int32)
    return y_enc, m

# ---------- Modelo e classificação ----------

def train_rf(X, y, n_trees=300, max_feats='sqrt'):
    n = X.shape[0]
    min_leaf = 2 if n < 2000 else 0.0025
    clf = RandomForestClassifier(
        n_estimators=int(n_trees),
        criterion='gini',
        max_features=max_feats,
        min_samples_leaf=min_leaf,
        min_impurity_decrease=1e-7,
        bootstrap=True,
        max_samples=0.6,
        oob_score=True,
        class_weight='balanced_subsample',
        n_jobs=-1,
        random_state=42
    )
    clf.fit(X, y)
    return clf

def classify_blockwise(stack, model, valid_mask, block=1024):
    """0 = NoData; classes começam em 1 (offset aplicado aqui)."""
    nrows, ncols, nfeat = stack.shape
    out = np.zeros((nrows, ncols), dtype=np.uint16)
    for r0 in range(0, nrows, block):
        for c0 in range(0, ncols, block):
            r1, c1 = min(r0 + block, nrows), min(c0 + block, ncols)
            blk = stack[r0:r1, c0:c1, :]
            vm  = valid_mask[r0:r1, c0:c1]
            flat  = blk.reshape(-1, nfeat)
            vflat = vm.reshape(-1)
            preds = np.zeros(flat.shape[0], dtype=np.uint16)
            if vflat.any():
                yhat = model.predict(flat[vflat]).astype(np.uint16)  # 0..K-1
                yhat += 1
                preds[vflat] = yhat
            out[r0:r1, c0:c1] = preds.reshape(blk.shape[0], blk.shape[1])
    return out

def save_model_bundle(model, label_mapping, feat_names, stats, path_joblib, n_trees):
    dump(model, path_joblib)
    meta = {
        "label_mapping": label_mapping,  # {label->code0}
        "feature_names": feat_names,
        "scaler": {"type": "robust", "stats": stats},
        "model": {"kind": "rf_single", "n_estimators": int(n_trees), "oob_score": getattr(model, "oob_score_", None)},
        "raster_output_codes": {"nodata": 0, "classes_start_at": 1}
    }
    meta_path = os.path.splitext(path_joblib)[0] + "_meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta_path

def load_model_bundle(path_joblib):
    model = load(path_joblib)
    meta_path = os.path.splitext(path_joblib)[0] + "_meta.json"
    if not os.path.exists(meta_path):
        raise QgsProcessingException("Meta JSON do modelo não encontrado.")
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    return model, meta

# ---------- Pós-processamento (remoção de manchas pequenas) ----------

def parse_int_csv(s):
    if not s: return set()
    try:
        return set(int(x.strip()) for x in s.split(',') if x.strip() != '')
    except Exception:
        raise QgsProcessingException("EXCLUDE_CLASSES deve ser CSV de inteiros (ex.: '2' ou '2,3').")

def _parse_int_list_csv(s, name):
    try:
        return [int(x.strip()) for x in s.split(',') if x.strip()!='']
    except Exception:
        raise QgsProcessingException(f"{name} deve ser CSV de inteiros.")

def mode_filter(arr, radius, ignore_zero=True):
    size = 2*int(radius) + 1
    footprint = np.ones((size, size), dtype=bool)
    def _mode(win):
        win = win.astype(np.int32)
        if ignore_zero: win = win[win != 0]
        if win.size == 0: return 0
        return np.bincount(win).argmax()
    return ndi.generic_filter(arr, _mode, footprint=footprint, mode='nearest')

def remove_small_patches(ymap, min_size, exclude, mode_radius, ignore_zero=True, connectivity=2):
    if min_size <= 0: return ymap
    mode_map = mode_filter(ymap, mode_radius, ignore_zero=ignore_zero)
    out = ymap.copy()
    structure = np.ones((3,3), dtype=np.uint8) if connectivity != 1 else np.array([[0,1,0],[1,1,1],[0,1,0]], dtype=np.uint8)
    classes = np.unique(ymap); classes = classes[(classes != 0)]
    for k in classes:
        if k in exclude: continue
        mask = (ymap == k)
        if not mask.any(): continue
        labels, nlab = ndi.label(mask, structure=structure)
        if nlab == 0: continue
        sizes = np.bincount(labels.ravel())
        small = sizes < int(min_size); small[0] = False
        small_mask = small[labels]
        out[small_mask] = mode_map[small_mask]
    return out

# ---------- Entropia ----------

def _to_u8_band_auto(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.float32)
    finite = np.isfinite(a)
    if finite.any():
        amin, amax = np.nanmin(a[finite]), np.nanmax(a[finite])
    else:
        amin, amax = 0.0, 1.0
    if amin >= -0.2 and amax <= 1.2:
        u = a * 255.0
    else:
        p2, p98 = np.nanpercentile(a[finite], [2, 98]) if finite.any() else (0.0, 1.0)
        if not np.isfinite(p2) or not np.isfinite(p98) or p98 <= p2:
            p2, p98 = amin, max(amin + 1.0, amax)
        u = (a - p2) * (255.0 / max(p98 - p2, 1e-6))
    return np.clip(u, 0, 255).astype(np.uint8)

def _to_u8_index(a: np.ndarray) -> np.ndarray:
    u = (a + 1.0) * 127.5
    return np.clip(u, 0, 255).astype(np.uint8)

def _entropy_u8(u8: np.ndarray, radius: int) -> np.ndarray:
    r = int(radius)
    if _HAS_SKIMAGE_RANK:
        return sk_entropy(u8, sk_square(2*r + 1)).astype(np.float32)
    size = 2*r + 1
    footprint = np.ones((size, size), dtype=bool)
    def _ent(win):
        m = np.isfinite(win)
        if not m.any(): return 0.0
        w = np.rint(win[m]).astype(np.int64, copy=False)
        w = np.clip(w, 0, 255)
        cnt = np.bincount(w, minlength=256).astype(np.float32)
        s = float(cnt.sum())
        if s <= 0.0: return 0.0
        p = cnt / s
        p = p[p > 0]
        with np.errstate(divide='ignore', invalid='ignore'):
            return float(-(p * np.log2(p)).sum())
    return ndi.generic_filter(u8, _ent, footprint=footprint, mode='nearest').astype(np.float32)

def append_entropy_features_from_stack(stack: np.ndarray, names: list, radius: int,
                                       on_bands: bool, on_indices: bool, feedback=None):
    base = {'R','G','B','NIR','SWIR1','SWIR2'}
    idxs = [j for j,nm in enumerate(names)
            if ((nm in base and on_bands) or (nm not in base and on_indices))]
    ent_feats, ent_names = [], []
    total = len(idxs)
    for k, j in enumerate(idxs, start=1):
        nm = names[j]
        arr = stack[..., j]
        u8 = _to_u8_band_auto(arr) if nm in base else _to_u8_index(arr)
        if feedback:
            feedback.setProgressText(f"Entropia {nm} ({k}/{total})")
            feedback.pushInfo(f"[Entropia] {nm}…")
        ent = _entropy_u8(u8, radius)
        ent_feats.append(ent); ent_names.append(f'ENT_{nm}')
    if ent_feats:
        ent_stack = np.stack(ent_feats, axis=-1).astype(np.float32)
        stack = np.concatenate([stack, ent_stack], axis=-1)
        names = names + ent_names
        feedback.pushInfo(f"Bandas + Índices + Entropia: {len(names)}")
    return stack, names



# ---------- Métricas / Relatórios ----------

def invert_mapping(m):  # {label->code} → {code->label}
    return {v: k for k, v in m.items()}

def metrics_oob(model, y_enc, label_map_inv):
    rep = {}
    oob_acc = getattr(model, 'oob_score_', None)
    oob_df = getattr(model, 'oob_decision_function_', None)
    if oob_df is not None and oob_acc is not None:
        mask = np.isfinite(oob_df).sum(axis=1) > 0
        y_pred = np.argmax(oob_df[mask], axis=1)
        y_true = y_enc[mask]
        cm = confusion_matrix(y_true, y_pred, labels=sorted(label_map_inv.keys()))
        kappa = cohen_kappa_score(y_true, y_pred)
        rep = {
            "oob_accuracy": float(oob_acc),
            "oob_kappa": float(kappa),
            "oob_confusion_matrix": cm.tolist(),
        }
    return rep

def metrics_validation(model, Xv, yv_labels, labmap, label_map_inv):
    rep = {}
    idx_keep, yv = [], []
    for i, lbl in enumerate(yv_labels.tolist()):
        if lbl in labmap:
            idx_keep.append(i); yv.append(labmap[lbl])
    if not idx_keep:
        return {"validation_note": "classes da validação não presentes no treino; nada a avaliar."}
    Xv = Xv[idx_keep, :]
    yv = np.array(yv, dtype=np.int32)
    yhat = model.predict(Xv)
    acc = accuracy_score(yv, yhat)
    kap = cohen_kappa_score(yv, yhat)
    cm = confusion_matrix(yv, yhat, labels=sorted(label_map_inv.keys()))
    cls_names = [label_map_inv[k] for k in sorted(label_map_inv.keys())]
    cls_rep = classification_report(yv, yhat, labels=sorted(label_map_inv.keys()), target_names=cls_names, zero_division=0)
    rep = {
        "val_accuracy": float(acc),
        "val_kappa": float(kap),
        "val_confusion_matrix": cm.tolist(),
        "val_classification_report": cls_rep
    }
    return rep

def save_json_report(base_out_tif, payload, feedback=None):
    path = os.path.splitext(base_out_tif)[0] + "_report.json"
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        if feedback: feedback.pushInfo(f"[Relatório] Métricas salvas em: {path}")
    except Exception as e:
        if feedback: feedback.pushInfo(f"[Relatório] Falha ao salvar JSON: {e}")
    return path

# -------------------- Algoritmo Processing -------------------- #

class RF_Ensemble_Classify(QgsProcessingAlgorithm):
    RASTER = 'RASTER'
    BANDMAP = 'BANDMAP'
    SAMPLES = 'SAMPLES'
    CLASS_FIELD = 'CLASS_FIELD'
    N_PER_CLASS = 'N_PER_CLASS'
    N_TREES = 'N_TREES'
    MODEL_IN = 'MODEL_IN'     # inferência direta (opcional)
    MODEL_OUT = 'MODEL_OUT'   # salvo se treinar (opcional)
    RASTER_OUT = 'RASTER_OUT' # RasterDestination

    # Pós-processamento
    MIN_PATCH = 'MIN_PATCH'
    MODE_RADIUS = 'MODE_RADIUS'
    EXCLUDE_CLASSES = 'EXCLUDE_CLASSES'
    MODE_IGNORE_NODATA = 'MODE_IGNORE_NODATA'

    # Entropia
    ENT_RADIUS = 'ENT_RADIUS'
    ENT_ON_BANDS = 'ENT_ON_BANDS'
    ENT_ON_INDICES = 'ENT_ON_INDICES'

    # Validação (opcional)
    VALID_SAMPLES = 'VALID_SAMPLES'
    VALID_CLASS_FIELD = 'VALID_CLASS_FIELD'
    VALID_N_PER_CLASS = 'VALID_N_PER_CLASS'

    def tr(self, s): return tr(s)
    def name(self): return 'rf_classify'
    def displayName(self): return self.tr('Classificação Supervisionada RF')
    def group(self): return self.tr('Machine Learning')
    def groupId(self): return 'machine_learning'
    def createInstance(self): return RF_Ensemble_Classify()

    def shortHelpString(self):
        return self.tr("""
Classificação de raster multibanda usando Random Forest (RF) com bandas, índices espectrais e entropia local. O resultado usa a convenção 0=NoData e classes iniciando em 1.

O que configurar:
- Raster multibanda: imagem de entrada que será classificada.
- Mapeamento de bandas: informa quais bandas do raster correspondem a R, G, B, NIR, SWIR1 e SWIR2. Exemplo: R=3,G=2,B=1,NIR=4.
- Polígonos de amostra (treino): camada poligonal com as áreas de treinamento.
- Campo de classe (treino): atributo que identifica a classe de cada polígono de treino.
- N amostras por classe (treino): quantidade de pontos amostrados aleatoriamente em cada classe para treinar o modelo.
- Número de árvores (RF): quantidade de árvores do Random Forest; valores maiores tendem a aumentar o custo de processamento.

Pós-processamento:
- Tamanho mínimo do patch (px): remove manchas muito pequenas no raster classificado.
- Raio (px) do filtro de modo: suaviza o resultado usando a vizinhança.
- Classes preservadas (CSV): classes que não devem ser suavizadas/removidas no pós-processamento.
- Ignorar NoData (0) no modo: evita que o valor 0 influencie o filtro de modo.

Entropia:
- Raio (px) da entropia local: tamanho da vizinhança usada para gerar feições de textura.
- Entropia nas bandas espectrais: calcula entropia nas bandas originais.
- Entropia nos índices: calcula entropia também nos índices espectrais.

Validação opcional:
- Polígonos de validação: camada separada para avaliar o modelo depois do treino.
- Campo de classe (validação): atributo de classe dos polígonos de validação.
- N amostras por classe (validação): quantidade de pontos por classe usados na avaliação.

Modelo e saídas:
- Modelo pré-treinado (.joblib): use quando quiser classificar diretamente sem treinar um novo modelo.
- Salvar modelo (.joblib): grava o modelo treinado para reutilização futura.
- Raster classificado: saída final do mapa de classes.

Fluxo de uso:
- Se você fornecer amostras de treino, o algoritmo treina o modelo e classifica o raster.
- Se você fornecer um modelo pré-treinado, o algoritmo pula o treino e executa apenas a inferência.
""")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.RASTER, self.tr('Raster multibanda')))
        self.addParameter(QgsProcessingParameterString(
            self.BANDMAP, self.tr('Mapeamento de bandas (ex.: R=3,G=2,B=1,NIR=4,SWIR1=5,SWIR2=6)'),
            defaultValue='R=3,G=2,B=1,NIR=4,SWIR1=5,SWIR2=6'
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.SAMPLES, self.tr('Polígonos de amostra (treino)'), [QgsProcessing.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterField(
            self.CLASS_FIELD, self.tr('Campo de classe (treino)'), parentLayerParameterName=self.SAMPLES
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.N_PER_CLASS, self.tr('N amostras por classe (treino)'),
            QgsProcessingParameterNumber.Integer, defaultValue=200, minValue=10
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.N_TREES, self.tr('Número de árvores (RF)'),
            QgsProcessingParameterNumber.Integer, defaultValue=100, minValue=10, maxValue=2000
        ))
        
        # Pós-processamento
        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_PATCH, self.tr('Tamanho mínimo do patch (px)'),
            QgsProcessingParameterNumber.Integer, defaultValue=5, minValue=0
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.MODE_RADIUS, self.tr('Raio (px) do filtro de modo'),
            QgsProcessingParameterNumber.Integer, defaultValue=15, minValue=1
        ))
        self.addParameter(QgsProcessingParameterString(
            self.EXCLUDE_CLASSES, self.tr('Classes preservadas (CSV, ex.: 1 ou 1,3)'),
            defaultValue='1'
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.MODE_IGNORE_NODATA, self.tr('Ignorar NoData (0) no modo'), defaultValue=True
        ))
        
        # Entropia
        self.addParameter(QgsProcessingParameterNumber(
            self.ENT_RADIUS, self.tr('Raio (px) da entropia local'),
            QgsProcessingParameterNumber.Integer, defaultValue=3, minValue=1, maxValue=15
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.ENT_ON_BANDS, self.tr('Entropia nas bandas espectrais'), defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.ENT_ON_INDICES, self.tr('Entropia nos índices'), defaultValue=False
        ))
        
        # Validação opcional
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.VALID_SAMPLES, self.tr('Polígonos de validação [opcional]'), [QgsProcessing.TypeVectorPolygon], optional=True
        ))
        self.addParameter(QgsProcessingParameterField(
            self.VALID_CLASS_FIELD, self.tr('Campo de classe (validação) [opcional]'),
            parentLayerParameterName=self.VALID_SAMPLES, optional=True
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.VALID_N_PER_CLASS, self.tr('N amostras por classe (validação) [opcional]'),
            QgsProcessingParameterNumber.Integer, defaultValue=150, minValue=10
        ))
        
        # Modelo + saída
        self.addParameter(QgsProcessingParameterFile(
            self.MODEL_IN, self.tr('Modelo pré-treinado (.joblib) [opcional]'),
            behavior=QgsProcessingParameterFile.File, optional=True, fileFilter='Joblib (*.joblib)'
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.MODEL_OUT, self.tr('Salvar modelo (.joblib) [opcional]'),
            fileFilter='Joblib (*.joblib)', optional=True
        ))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.RASTER_OUT, self.tr('Raster classificado')
        ))
        

    def processAlgorithm(self, p, context, feedback):
        def prog(x, txt=None):
            if txt: feedback.setProgressText(txt)
            feedback.setProgress(int(min(100, x)))

        rlyr = self.parameterAsRasterLayer(p, self.RASTER, context)
        if rlyr is None: raise QgsProcessingException("Raster inválido.")
        uri = rlyr.dataProvider().dataSourceUri()
        src_path = uri.split('|')[0]
        feedback.pushInfo(f"[Abertura] Raster: {src_path}")
        prog(3, "Abrindo raster…")

        # Parâmetros gerais
        bandmap = parse_band_mapping(self.parameterAsString(p, self.BANDMAP, context))
        samples = self.parameterAsSource(p, self.SAMPLES, context)
        class_field = self.parameterAsString(p, self.CLASS_FIELD, context)
        n_per = self.parameterAsInt(p, self.N_PER_CLASS, context)
        n_trees = self.parameterAsInt(p, self.N_TREES, context)

        min_patch = self.parameterAsInt(p, self.MIN_PATCH, context)
        mode_radius = self.parameterAsInt(p, self.MODE_RADIUS, context)
        exclude = parse_int_csv(self.parameterAsString(p, self.EXCLUDE_CLASSES, context))
        ignore_nodata = self.parameterAsBool(p, self.MODE_IGNORE_NODATA, context)

        model_in = self.parameterAsFile(p, self.MODEL_IN, context)
        model_out = self.parameterAsFileOutput(p, self.MODEL_OUT, context)
        out_tif = self.parameterAsOutputLayer(p, self.RASTER_OUT, context)

        # Entropia
        ent_radius = self.parameterAsInt(p, self.ENT_RADIUS, context)
        ent_on_bands = self.parameterAsBool(p, self.ENT_ON_BANDS, context)
        ent_on_indices = self.parameterAsBool(p, self.ENT_ON_INDICES, context)

        # Validação
        v_src = self.parameterAsSource(p, self.VALID_SAMPLES, context)
        v_class_field = self.parameterAsString(p, self.VALID_CLASS_FIELD, context) if v_src else None
        v_n = self.parameterAsInt(p, self.VALID_N_PER_CLASS, context) if v_src else None

        with rasterio.open(src_path) as ds:
            raster_crs = QgsCoordinateReferenceSystem.fromWkt(ds.crs.to_wkt()) if ds.crs else rlyr.crs()
            feedback.pushInfo(f"[Abertura] Dimensões: {ds.width}×{ds.height} px; bandas: {ds.count}")
            feedback.pushInfo(f"[Abertura] BANDMAP: {bandmap}")
            prog(8, "Lendo bandas…")

            # Leitura + máscara
            B, valid_mask = read_bands(ds, bandmap, feedback)
            if not B: raise QgsProcessingException("BANDMAP não corresponde a bandas existentes.")
            stack, feat_names = stack_features(B, feedback)

            # Entropia (opcional)
            if ent_radius and (ent_on_bands or ent_on_indices):
                feedback.pushInfo(f"[Entropia] Raio={ent_radius}px; bandas={ent_on_bands}; índices={ent_on_indices}")
                stack, feat_names = append_entropy_features_from_stack(
                    stack, feat_names, ent_radius, ent_on_bands, ent_on_indices, feedback
                )

            #  Inferência com modelo carregado
            if model_in and os.path.exists(model_in):
                feedback.pushInfo("[Modelo] Carregando modelo pré-treinado…")
                model, meta = load_model_bundle(model_in)
                want = meta['feature_names']; have = {n: i for i, n in enumerate(feat_names)}
                missing = [n for n in want if n not in have]
                if missing:
                    raise QgsProcessingException(f"Features exigidas pelo modelo ausentes: {missing}")
                stack = stack[..., [have[n] for n in want]]
                stats = meta['scaler']['stats']
                robust_transform_inplace(stack, stats)
                prog(55, "Normalizando…")

                feedback.pushInfo("[Inferência] Classificando…")
                ymap = classify_blockwise(stack, model, valid_mask)
                prog(80, "Pós-processando…")
                ymap = remove_small_patches(ymap, min_patch, exclude, mode_radius,
                                            ignore_zero=ignore_nodata, connectivity=2)

                # Salvar
                prof = ds.profile.copy()
                prof.update(count=1, dtype=str(ymap.dtype), nodata=0, compress='deflate', predictor=2)
                with rasterio.open(out_tif, 'w', **prof) as outds:
                    outds.write(ymap, 1)
                prog(100, "Concluído.")
                return {self.RASTER_OUT: out_tif}

            #Caminho B: Treino + criação de modelo
            if samples is None:
                raise QgsProcessingException("Amostras não fornecidas e nenhum MODEL_IN informado.")
            feedback.pushInfo("[Amostragem] Gerando pontos estratificados (treino)…")
            pts = stratified_points(samples, class_field, n_per, raster_crs)
            prog(45, "Extraindo amostras (treino)…")

            X, y_lbl = sample_stack_at_points(ds, stack, pts)
            good = np.all(np.isfinite(X), axis=1)
            X, y_lbl = X[good], y_lbl[good]
            if X.size == 0: raise QgsProcessingException("Amostras inválidas após máscara/NaN.")
            feedback.pushInfo(f"[Amostragem] Treino: {X.shape[0]} amostras; {X.shape[1]} features.")

            # Validação com outras amostras opcional
            Xv = yv = None
            if v_src:
                feedback.pushInfo("[Validação] Gerando pontos estratificados (validação)…")
                v_pts = stratified_points(v_src, v_class_field or class_field, v_n, raster_crs)
                Xv, yv = sample_stack_at_points(ds, stack, v_pts)
                goodv = np.all(np.isfinite(Xv), axis=1)
                Xv, yv = Xv[goodv], yv[goodv]
                feedback.pushInfo(f"[Validação] {Xv.shape[0]} amostras de validação.")

            # Escalonamento robusto (ajustar nos PREDITORES do raster)
            stats = robust_fit_stats(stack)
            robust_transform_inplace(stack, stats)
            robust_transform_inplace(X, stats)
            if Xv is not None: robust_transform_inplace(Xv, stats)
            prog(55, "Treinando RF…")

            y_enc, labmap = encode_labels(y_lbl)
            label_map_inv = invert_mapping(labmap)

            model = train_rf(X, y_enc, n_trees=n_trees)
            feedback.pushInfo(f"[Modelo] OOB accuracy: {getattr(model,'oob_score_', None)}")
            prog(70, "Classificando raster…")

            ymap = classify_blockwise(stack, model, valid_mask)  # 0=NoData; classes 1..K
            prog(85, "Pós-processando…")
            ymap = remove_small_patches(ymap, min_patch, exclude, mode_radius,
                                        ignore_zero=ignore_nodata, connectivity=2)

            # Salvar raster
            prof = ds.profile.copy()
            prof.update(count=1, dtype=str(ymap.dtype), nodata=0, compress='deflate', predictor=2)
            with rasterio.open(out_tif, 'w', **prof) as outds:
                outds.write(ymap, 1)

            prog(92, "Relatórios…")
            
            # Métricas
            report = {
                "labels": label_map_inv,  # code -> label
            }
            try:
                report.update(metrics_oob(model, y_enc, label_map_inv))
                if Xv is not None:
                    report.update(metrics_validation(model, Xv, yv, labmap, label_map_inv))
            except Exception as e:
                feedback.pushInfo(f"[Métricas] Aviso: {e}")

            if "oob_accuracy" in report:
                feedback.pushInfo(f"[OOB] acc={report['oob_accuracy']:.4f}; kappa={report.get('oob_kappa', float('nan')):.4f}")
            if "val_accuracy" in report:
                feedback.pushInfo(f"[VAL] acc={report['val_accuracy']:.4f}; kappa={report['val_kappa']:.4f}")
                feedback.pushInfo("[VAL] Relatório por classe:\n" + report.get("val_classification_report",""))

            save_json_report(out_tif, report, feedback)

            if model_out:
                save_model_bundle(model, labmap, list(feat_names), stats, model_out, n_trees)
                prog(100, "Concluído.")
                return {self.MODEL_OUT: model_out, self.RASTER_OUT: out_tif}
            else:
                prog(100, "Concluído.")
                return {self.RASTER_OUT: out_tif}
