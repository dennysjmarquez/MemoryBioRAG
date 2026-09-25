"""Constantes, flags de configuración y funciones puras del motor de memoria BioRAG."""

from __future__ import annotations

import os
import re
from core.stemmer_es import _quitar_acentos

# Auto-cargar .env.local al importar (antes de leer cualquier variable de entorno)
from config import _load_env_local
_load_env_local()

# =============================================================================
# Configuración de Usuario (Override con variables de entorno)
# =============================================================================

CANDIDATOS_SIMILITUD = int(os.environ.get('BIORAG_CANDIDATOS_SIMILITUD', '100'))
"""Cuántos nodos considerar como candidatos en similitud conceptual."""

MAX_SALTOS_CADENA = int(os.environ.get('BIORAG_MAX_SALTOS_CADENA', '3'))
"""Máximo de saltos (hops) en evocación por cadena."""

LIMITE_DEFAULT = int(os.environ.get('BIORAG_LIMITE_DEFAULT', '5'))
"""Límite de resultados por capa de búsqueda."""

UMBRAL_JACCARD = float(os.environ.get('BIORAG_UMBRAL_JACCARD', '0.15'))
"""Umbral Jaccard para similitud conceptual (0.0-1.0)."""

RAFTAGA_ACTIVA = os.environ.get('BIORAG_RAFTAGA_ACTIVA', 'true').lower() == 'true'
"""Activar/desactivar ráfaga de reminiscencia."""

THRESHOLD_RAFTAGA = float(os.environ.get('BIORAG_THRESHOLD_RAFTAGA', '0.5'))
"""Score mínimo para activar ráfaga automáticamente."""

LIMITE_RAFTAGA = int(os.environ.get('BIORAG_LIMITE_RAFTAGA', '5'))
"""Límite de resultados en búsqueda por ráfaga."""

LIMITE_EVOCACION = int(os.environ.get('BIORAG_LIMITE_EVOCACION', '5'))
"""Límite de resultados en evocación por cadena."""

JSD_WEIGHT = float(os.environ.get('BIORAG_JSD_WEIGHT', '0.0'))
"""Peso de JSD (señal #11) en la fórmula de scoring. 0.0=desactivado, 0.05=default activo.
Override: export BIORAG_JSD_WEIGHT=0.05"""

# E7: JSD adaptativo por Nt (tokens >=3). Default ON.
# Base 0.05 si JSD_WEIGHT==0 (JSD estatico sigue OFF en rafaga).
JSD_ADAPTATIVO = os.environ.get('BIORAG_JSD_ADAPTATIVO', '1').lower() in ('1', 'true', 'yes')
JSD_ADAPT_BASE = float(os.environ.get('BIORAG_JSD_ADAPT_BASE', '0.05'))
JSD_ADAPT_LARGO = float(os.environ.get('BIORAG_JSD_ADAPT_LARGO', '2.5'))
JSD_ADAPT_CORTO = float(os.environ.get('BIORAG_JSD_ADAPT_CORTO', '0.5'))
JSD_ADAPT_NT = int(os.environ.get('BIORAG_JSD_ADAPT_NT', '4'))

# E10: sinapsis de sintesis DMN (peso 0.30, tope por ciclo). Default ON hasta gate.
DMN_SINTESIS_ACTIVA = os.environ.get('BIORAG_DMN_SINTESIS_ACTIVA', '1').lower() in ('1', 'true', 'yes')
DMN_SINTESIS_MAX = int(os.environ.get('BIORAG_DMN_SINTESIS_MAX', '8'))
DMN_SINTESIS_PESO = float(os.environ.get('BIORAG_DMN_SINTESIS_PESO', '0.30'))

# F2: episodio temporal. Peso 0 = OFF. Cap 0.08.
_ep_raw = float(os.environ.get('BIORAG_EPISODIO_TEMPORAL_PESO', '0.05'))
EPISODIO_TEMPORAL_PESO = 0.0 if _ep_raw <= 0 else min(_ep_raw, 0.08)
EPISODIO_TEMPORAL_ACTIVO = os.environ.get('BIORAG_EPISODIO_TEMPORAL', '0').lower() in ('1', 'true', 'yes')
EPISODIO_VENTANA_HORAS = float(os.environ.get('BIORAG_EPISODIO_VENTANA_HORAS', '24'))
EPISODIO_LIMITE = int(os.environ.get('BIORAG_EPISODIO_LIMITE', '5'))
EPISODIO_BUCKET_SEG = float(os.environ.get('BIORAG_EPISODIO_BUCKET_SEG', str(86400)))

# F3: analogia relacional simbolica sobre PPMI 100-dim. Peso 0 = OFF. Cap 0.08.
_an_raw = float(os.environ.get('BIORAG_ANALOGIA_PESO', '0'))
ANALOGIA_PESO = 0.0 if _an_raw <= 0 else min(_an_raw, 0.08)
ANALOGIA_DETECTAR = os.environ.get('BIORAG_ANALOGIA_DETECTAR', '0').lower() in ('1', 'true', 'yes')

# F5: campo semantico PPMI. Peso 0 = OFF. Cap 0.08.
_cp_raw = float(os.environ.get('BIORAG_CAMPO_POTENCIAL_PESO', '0.05'))
CAMPO_POTENCIAL_PESO = 0.0 if _cp_raw <= 0 else min(_cp_raw, 0.08)
CAMPO_SIGMA = float(os.environ.get('BIORAG_CAMPO_SIGMA', '1.0'))
CAMPO_K = int(os.environ.get('BIORAG_CAMPO_K', '64'))

# OPT-NUEVA-5: etiquetado epistemico. Solo metadatos via side-channel
# (last_estado_epistemico) + cola DMN. NUNCA toca ranking/pool (R9 vs E13).
EPISTEMICO_METADATA = os.environ.get('BIORAG_EPISTEMICO_METADATA', '1').lower() in ('1', 'true', 'yes')

# Multihop v1: expansion 1-salto en retrieval. Default OFF (gate decide).
# Detras del flag el path es byte-identico (estandar F3). Caps via env.
MULTIHOP_EXPANSION = os.environ.get('BIORAG_MULTIHOP_EXPANSION', '0').lower() in ('1', 'true', 'yes')
MULTIHOP_MAX_TOTAL = int(os.environ.get('BIORAG_MULTIHOP_MAX_TOTAL', '64'))
# HIPOTESIS v1: prior fijo atenuado; el ranking real lo aportan las demas senales.
MULTIHOP_PRIOR = float(os.environ.get('BIORAG_MULTIHOP_PRIOR', '0.05'))

BAYESIAN_BM25 = os.environ.get('BIORAG_BAYESIAN_BM25', 'false').lower() == 'true'
"""Activar calibración Bayesian BM25 (sigmoid) en vez de normalización fija x/(x+3).
Override: export BIORAG_BAYESIAN_BM25=true"""

BAYESIAN_BM25_ALPHA = float(os.environ.get('BIORAG_BAYESIAN_BM25_ALPHA', '1.0'))
"""Steepness de la sigmoid Bayesian BM25. Mayor = más sensible a diferencias de score.
Override: export BIORAG_BAYESIAN_BM25_ALPHA=0.5"""

# Fase C: re-ranking jaccard léxico como única señal de matching (v22.2)
# Validado por holdout el 2026-08-04 (config: alpha=0.25, gate=0.04, topk=20, protect-r0).
# OFF por defecto: activación gradual monitoreada contra el benchmark (lección PPR).
RERANKING_JACCARD_ACTIVO = os.environ.get('BIORAG_RERANKING_JACCARD_ENABLED', '0').lower() in ('1', 'true', 'yes')
"""Activar re-ranking jaccard en buscar_por_frase. Default OFF.
Override: export BIORAG_RERANKING_JACCARD_ENABLED=1"""

RERANKING_JACCARD_ALPHA = float(os.environ.get('BIORAG_RERANKING_JACCARD_ALPHA', '0.25'))
"""Peso del boost jaccard en el re-sort del top-k (score + alpha*(jaccard/max_j)).
Override: export BIORAG_RERANKING_JACCARD_ALPHA=0.25"""

RERANKING_JACCARD_GATE = float(os.environ.get('BIORAG_RERANKING_JACCARD_GATE', '0.04'))
"""Gate: si max jaccard del pool[:window] < gate, no re-ordenar.
Override: export BIORAG_RERANKING_JACCARD_GATE=0.04"""

RERANKING_JACCARD_TOPK = int(os.environ.get('BIORAG_RERANKING_JACCARD_TOPK', '20'))
"""Tamaño del head sobre el que se aplica el re-sort jaccard.
Override: export BIORAG_RERANKING_JACCARD_TOPK=20"""

RERANKING_JACCARD_WINDOW = int(os.environ.get('BIORAG_RERANKING_JACCARD_WINDOW', '50'))

# E1: SDM Kanerva (2048 bits) como Fallback 2.5. Solo generación cuando el
# pool léxico es pobre. OFF con BIORAG_SDM_FALLBACK=0. No es señal de scoring
# (eso es E2, paso aparte).
SDM_FALLBACK_ACTIVO = os.environ.get('BIORAG_SDM_FALLBACK', '1').lower() in ('1', 'true', 'yes')
SDM_FALLBACK_K = int(os.environ.get('BIORAG_SDM_FALLBACK_K', '5'))

# E3: QCR ponderado por IDF. Default ON. Umbral 0.30–0.45 (default 0.40).
# OFF: BIORAG_QCR_IDF=0 vuelve al ratio no ponderado 0.50.
QCR_IDF_ACTIVO = os.environ.get('BIORAG_QCR_IDF', '1').lower() in ('1', 'true', 'yes')
QCR_IDF_UMBRAL = float(os.environ.get('BIORAG_QCR_IDF_UMBRAL', '0.40'))

# F-QCR-D4 (Fase 1): segunda oportunidad QCR tolerante a typos (all-near).
# Un candidato con score alto que falla cobertura exacta sobrevive si CADA
# token tiene hit exacto (substring) o near-match (lev<=DIST, len>=4).
# Calibrado 19/19 con tokens LIVE: rescata Clase-A 4/4, 0/14 distractores,
# 0738 a salvo. Piso 0.35: max negativo < 0.25 (separacion Paso 0).
# Default ON: gate Fase 1 pasado 2026-09-13 (R@5 98.06, 17 fallos, FP 0).
# Override: export BIORAG_QCR_TYPO=0
QCR_TYPO_ACTIVA = os.environ.get('BIORAG_QCR_TYPO', '1').lower() in ('1', 'true', 'yes')
DIM_RESONANCIA = os.environ.get('BIORAG_DIM_RESONANCIA', '0').lower() in ('1', 'true', 'yes')
DIM_RESONANCIA_K = int(os.environ.get('BIORAG_DIM_RESONANCIA_K', '50'))
DIM_ESCAPE = os.environ.get('BIORAG_DIM_ESCAPE', '0').lower() in ('1', 'true', 'yes')
DIM_ESCAPE_T = float(os.environ.get('BIORAG_DIM_ESCAPE_T', '0.45'))
QCR_TYPO_PISO = float(os.environ.get('BIORAG_QCR_TYPO_PISO', '0.35'))
QCR_TYPO_DIST = int(os.environ.get('BIORAG_QCR_TYPO_DIST', '2'))

# E6: NCD zlib (Li et al. 2004). Senal O(k) sobre el pool, no O(N).
# Default peso 0.05; 0 = OFF. Cap 0.08. Solo stdlib zlib.
_ncd_peso_raw = float(os.environ.get('BIORAG_NCD_PESO', '0.05'))
NCD_PESO = 0.0 if _ncd_peso_raw <= 0 else min(_ncd_peso_raw, 0.08)
NCD_ZLIB_LEVEL = int(os.environ.get('BIORAG_NCD_ZLIB_LEVEL', '6'))

GABA_ACTIVO = os.environ.get('BIORAG_GABA_ACTIVO', '1').lower() in ('1', 'true', 'yes')
"""Activar inhibición lateral GABA (Edelman 1987): atenúa competidores secundarios cuando top-1 es atractor fuerte.
Default ON. Ablación: export BIORAG_GABA_ACTIVO=0"""

# Signal #13: PPMI+SVD Vector Similarity (v26.0)
PPMI_VECTOR_WEIGHT = float(os.environ.get('BIORAG_PPMI_WEIGHT', '0.15'))
"""Peso de la señal PPMI+SVD en _calcular_score_hibrido. 0.15 = default (v26.0).
Override: export BIORAG_PPMI_WEIGHT=0.0 para volver al comportamiento v25.2"""

# Signal #14: ADN Conceptual (v29) como señal asociativa complementaria
ADN_RANKING_ENABLED = os.environ.get('BIORAG_ADN_RANKING_ENABLED', 'false').lower() in ('1', 'true', 'yes')
ADN_PESO = float(os.environ.get('BIORAG_ADN_PESO', '0.15'))
ADN_MAX_EXPANSION = int(os.environ.get('BIORAG_ADN_MAX_EXPANSION', '24'))
ADN_UMBRAL_ASOCIACION = float(os.environ.get('BIORAG_ADN_UMBRAL_ASOCIACION', '0.35'))


# =============================================================================
# Funciones puras de módulo
# =============================================================================

def _qcr_levenshtein(a, b, dist_max=2):
    """Levenshtein acotado: early-exit si excede dist_max. Solo stdlib."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > dist_max:
        return dist_max + 1
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ai = a[i - 1]
        row_min = cur[0]
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (0 if ai == b[j - 1] else 1))
            if cur[j] < row_min:
                row_min = cur[j]
        if row_min > dist_max:
            return dist_max + 1
        prev = cur
    return prev[lb]


def _qcr_todos_cercanos(q_tokens, text_target, dist_max=2, palabras_max=1500):
    """D4: True si CADA token tiene hit exacto o near-match en el texto.

    Hit exacto = substring (igual que QCR). Near-match = lev <= dist_max
    contra alguna palabra para tokens len>=4; tokens cortos solo exacto
    (evita colisiones espurias: 'moe'~'de'). Palabras = split [a-z]+
    (parte por '_' y digitos). Tope de palabras acota el peor caso."""
    if not q_tokens:
        return True
    pendientes = []
    for t in q_tokens:
        if t in text_target:
            continue
        if len(t) < 4:
            return False
        pendientes.append(t)
    if not pendientes:
        return True
    words = [w for w in re.findall(r'[a-záéíóúñü]+', text_target)
             if len(w) >= 3][:palabras_max]
    for t in pendientes:
        lt = len(t)
        ok = False
        for w in words:
            if abs(len(w) - lt) > dist_max:
                continue
            if _qcr_levenshtein(t, w, dist_max) <= dist_max:
                ok = True
                break
        if not ok:
            return False
    return True


def normalizar_sustantivos_clave(raw: str) -> str:
    """Normaliza sustantivos_clave: lowercase, quitar tildes, trim, dedup, colapsar comas.

    RF-10 (spec 001): normaliza a minúsculas, elimina espacios alrededor de comas,
    quita tildes (á→a, é→e, í→i, ó→o, ú→u) preservando la ñ. Colapsa comas
    múltiples (',,' → ',') y auto-dedup preservando el orden de primera aparición.

    Detalle empírico verificado (T1): `_quitar_acentos` de core/stemmer_es.py usa
    unicodedata NFKD, que DESCOMPONE también la ñ (U+00F1 → n + U+0303 tilde comb.)
    y la filtra. Para cumplir RF-10 ("preservando la ñ") se protege la ñ con un
    marcador de control (\x01) antes de `_quitar_acentos` y se restaura después.
    El marcador no es alfanumérico, así que jamás pasa la validación de formato (T3).
    """
    sk = [t.strip().lower() for t in raw.split(",") if t.strip()]
    sk = [t.replace("ñ", "\x01") for t in sk]
    sk = [_quitar_acentos(t).replace("\x01", "ñ") for t in sk]
    seen = set()
    unique = []
    for t in sk:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return ",".join(unique)
