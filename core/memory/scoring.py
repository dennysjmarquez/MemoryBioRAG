"""core/memory/scoring.py - Módulo de cálculo de scores y similitudes multi-señal.

Este módulo concentra las funciones de scoring híbrido, JSD, NCD, BM25 Bayesiano,
IDF QCR, centralidad de tokens y re-ranking Jaccard.

Extraído de SQLiteMemoryBioRAG:
- Funciones de instancia con `self` como primer parámetro.
- Funciones estáticas sin `self` (_ncd_sim, _jsd_weight_adaptativo, _calcular_jsd, _calcular_bm25_bayesiano).
"""

import math
import re

from core.memory import constants


def _idf_tokens_qcr(self, tokens):
    """IDF de tokens de query para QCR. Cache por instancia. DF vía FTS5 MATCH (índice), no scan del corpus."""
    if not getattr(self, "_qcr_idf_cache", None):
        self._qcr_idf_cache = {}
    if getattr(self, "_qcr_n_docs", None) is None:
        try:
            self._qcr_n_docs = max(
                1, int(self.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0] or 1)
            )
        except Exception:
            self._qcr_n_docs = 1
    out = {}
    n = self._qcr_n_docs
    for t in tokens:
        if t in self._qcr_idf_cache:
            out[t] = self._qcr_idf_cache[t]
            continue
        df = 0
        try:
            safe = (t or "").replace('"', "")
            if safe:
                self.cursor.execute(
                    "SELECT COUNT(*) FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?",
                    (f'"{safe}"',),
                )
                df = int(self.cursor.fetchone()[0] or 0)
        except Exception:
            df = 0
        idf = math.log((n + 1) / (df + 1)) + 1.0
        self._qcr_idf_cache[t] = idf
        out[t] = idf
    return out


def _calcular_jaccard(self, str1, str2):
    """Calcula la similitud de Jaccard entre dos cadenas en base a sub-palabras de 3 caracteres (Trigramas)."""
    def obtener_trigramas(texto):
        clean = re.sub(r'[^a-z0-9]', '', texto.lower())
        return set(clean[i:i+3] for i in range(len(clean) - 2)) if len(clean) >= 3 else set([clean])

    set1, set2 = obtener_trigramas(str1), obtener_trigramas(str2)
    interseccion = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return interseccion / union if union > 0 else 0.0


def _agregar_prefix_wildcards(self, query):
    """Agrega '*' al final de cada término para prefix matching en FTS5 unicode61.

    Preserva frases entre comillas: "react native" -> "react* native*".
    No duplica wildcards si ya existen. Términos cortos (<3 chars) no reciben
    wildcard para evitar ruido (ej: "el*" matchearía demasiadas palabras).
    """
    terms = re.findall(r'"[^"]*"|\S+', query)
    result = []
    for t in terms:
        if t.startswith('"') and t.endswith('"'):
            inner = t[1:-1]
            if len(inner) < 3:
                result.append(t)
            else:
                result.append(f'"{inner}*"')
        elif len(t) < 3 or t.endswith('*'):
            result.append(t)
        else:
            result.append(t + '*')
    return ' '.join(result)


def _pesar_tokens_query(self, frase):
    """Calcula el peso de cada token según su centralidad en la red sináptica.
    
    Tokens con más conexiones en sinapsis y equivalencias en semántica
    obtienen mayor peso en el scoring. Peso base mínimo de 0.1 para que
    ningún término desaparezca del scoring.
    """
    import re
    tokens = re.findall(r'\w{3,}', frase.lower())
    if not tokens:
        return {}
    
    pesos = {}
    for token in set(tokens):
        # Buscar en concepto de sinapsis (origen/destino suelen ser nombres de nodo)
        # Usamos LIKE solo en sinapsis porque los nombres de nodo son compound
        self.cursor.execute(
            "SELECT COUNT(*) FROM sinapsis WHERE origen LIKE ? OR destino LIKE ?",
            (f'%{token}%', f'%{token}%')
        )
        conexiones = self.cursor.fetchone()[0] or 0
        
        pesos[token] = max(0.1, conexiones)
    
    total = sum(pesos.values()) or 1
    return {t: p / total for t, p in pesos.items()}


def _ncd_sim(a, b, level=None):
    """Sim_NCD = 1 - NCD(x,y) con zlib. C(s)=len(compress(utf-8))."""
    import zlib
    if level is None:
        level = constants.NCD_ZLIB_LEVEL
    xa = (a or "").encode("utf-8", errors="ignore")
    yb = (b or "").encode("utf-8", errors="ignore")
    if not xa or not yb:
        return 0.0
    def _c(blob):
        return max(1, len(zlib.compress(blob, level)))
    cx, cy = _c(xa), _c(yb)
    cxy = _c(xa + yb)
    ncd = (cxy - min(cx, cy)) / float(max(cx, cy))
    return max(0.0, min(1.0, 1.0 - ncd))


def _ncd_sims_pool(self, query, filas):
    """NCD query vs concepto+contenido de cada fila del pool. O(k)."""
    if not query or not filas:
        return {}
    q = (query or "").strip()
    out = {}
    for conc, texto in filas:
        if not conc:
            continue
        out[conc] = self._ncd_sim(q, f"{conc} {texto or ''}")
    return out


def _jsd_weight_adaptativo(query, n_tokens=None):
    """E7: constants.JSD_WEIGHT * 2.5 si Nt>=4, *0.5 si Nt<4. OFF: constants.JSD_WEIGHT estatico."""
    if not constants.JSD_ADAPTATIVO:
        return float(constants.JSD_WEIGHT)
    if n_tokens is None:
        n_tokens = len(re.findall(r"\w{3,}", query or ""))
    base = constants.JSD_WEIGHT if constants.JSD_WEIGHT > 0.0 else constants.JSD_ADAPT_BASE
    if n_tokens >= constants.JSD_ADAPT_NT:
        w = base * constants.JSD_ADAPT_LARGO
    else:
        w = base * constants.JSD_ADAPT_CORTO
    return max(0.0, min(0.20, w))


def _analogia_scores_pool(self, v_target, pool):
    """F3: coseno de cada candidato vs vector analogia v_target. O(k*d), clamp [0,1]."""
    if constants.ANALOGIA_PESO <= 0 or v_target is None or not pool:
        return {}
    try:
        import numpy as np
        vecs = (self._ppmi_index.vecs or {}) if self._ppmi_index else {}
        vt = np.asarray(v_target, dtype="float64")
        nvt = float(np.linalg.norm(vt))
        if nvt < 1e-10 or not vecs:
            return {}
        out = {}
        for c in pool:
            if not c:
                continue
            v = vecs.get(c)
            if v is None:
                out[c] = 0.0
                continue
            vv = np.asarray(v, dtype="float64")
            nv = float(np.linalg.norm(vv))
            s = float(np.dot(vt, vv) / (nvt * nv)) if nv > 1e-10 else 0.0
            out[c] = min(1.0, max(0.0, s))
        return out
    except Exception:
        return {}


def _calcular_jsd(query_text: str, node_text: str) -> float:
    """Jensen-Shannon Divergence como score de similitud [0,1].

    Calcula la divergencia entre las distribuciones de frecuencia de palabras
    del query y del contenido del nodo. A diferencia de BM25 (que mide
    relevancia por IDF), JSD mide solapamiento distribucional - cuanta
    informacion comparten dos textos.

    JSD = 1/2 * KL(P||M) + 1/2 * KL(Q||M)  donde M = 1/2(P+Q)
    Score = 1 - sqrt(JSD)  -> [0,1], mayor = mas similar.
    """
    if not query_text or not node_text:
        return 0.0

    from core.stopwords import STOPWORDS_ES
    from core.fallback_simbolico import _STOPWORDS_NORM

    def _word_freqs(text: str) -> dict[str, float]:
        text_norm = text.lower().replace('_', ' ').replace('-', ' ')
        words = re.findall(r'\w{2,}', text_norm)
        stopwords = STOPWORDS_ES | _STOPWORDS_NORM
        counts: dict[str, int] = {}
        for w in words:
            if w not in stopwords and len(w) >= 2:
                counts[w] = counts.get(w, 0) + 1
        total = sum(counts.values())
        if total == 0:
            return {}
        return {w: c / total for w, c in counts.items()}

    p_dist = _word_freqs(query_text)
    q_dist = _word_freqs(node_text)

    if not p_dist or not q_dist:
        return 0.0

    vocab = set(p_dist.keys()) | set(q_dist.keys())

    # Laplace smoothing: α=0.01 para evitar log(0)
    alpha = 0.01
    p_vec = [p_dist.get(w, 0.0) + alpha for w in vocab]
    q_vec = [q_dist.get(w, 0.0) + alpha for w in vocab]

    # Normalize to probability distributions
    p_sum = sum(p_vec)
    q_sum = sum(q_vec)
    p_vec = [x / p_sum for x in p_vec]
    q_vec = [x / q_sum for x in q_vec]

    # Mixture distribution M = ½(P+Q)
    m_vec = [(p + q) / 2.0 for p, q in zip(p_vec, q_vec)]

    def _kl(a: list[float], b: list[float]) -> float:
        return sum(x * math.log(x / y) for x, y in zip(a, b) if x > 0 and y > 0)

    jsd_div = 0.5 * _kl(p_vec, m_vec) + 0.5 * _kl(q_vec, m_vec)

    # Score: 1 - sqrt(JSD) → [0, 1], higher = more similar
    return round(1.0 - math.sqrt(min(jsd_div, 1.0)), 4)


def _calcular_bm25_bayesiano(raw_scores: dict, alpha: float = 1.0) -> dict:
    """Calibracion Bayesian BM25: convierte scores crudos FTS5 a probabilidades [0,1].

    Formula: sigmoid(alpha * (score - beta)) donde beta = mediana(scores) * 0.7
    (estimacion sin labels, basada en distribucion del corpus).

    A diferencia de x/(x+3), la sigmoid calibra probabilisticamente:
    - scores altos -> ~1.0 (alta probabilidad de relevancia)
    - scores bajos -> ~0.0 (baja probabilidad)
    - β se adapta a la distribución de scores de cada query

    Args:
        raw_scores: {concepto: raw_bm25_score} - scores crudos de FTS5
        alpha: steepness de la sigmoid (default 1.0)

    Returns:
        {concepto: probability} - probabilidades calibradas en [0, 1]
    """
    if not raw_scores:
        return {}

    scores = list(raw_scores.values())
    # β = mediana × 0.7 — estimación heurística sin labels
    # IMPORTANTE: BM25 de FTS5 es negativo (más negativo = mejor match)
    # La sigmoid se aplica directamente al score crudo (sin abs)
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    median = sorted_scores[n // 2] if n % 2 == 1 else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2.0
    beta = median * 0.7

    result = {}
    for concepto, raw in raw_scores.items():
        # sigmoid(α × (score - β))
        # BM25 scores son negativos: más negativo → más relevante
        # sigmoid(-large) ≈ 0.0 (mejor match), sigmoid(-small) ≈ 1.0 (peor match)
        z = alpha * (raw - beta)
        # Clamp to avoid overflow
        if z > 500:
            prob = 1.0
        elif z < -500:
            prob = 0.0
        else:
            prob = 1.0 / (1.0 + math.exp(-z))
        result[concepto] = round(prob, 4)

    return result


def _calcular_score_hibrido(self, bm25_norm=0.0, dim_score=0.0,
                            peso_sinaptico=0.0, concepto_ratio=0.0,
                            sinonimos_ratio=0.0, score_latente=0.0,
                            score_cadena=0.0, temporal=0.0,
                            asoc_count=0, match_exacto=False,
                            grupo_score=0.0, tematico_score=0.0,
                            jsd_score: float = 0.0,
                            jsd_weight: float = 0.0,
                            pred_score: float = 0.0,
                            ppmi_score: float = 0.0,
                            hub_match: float = 0.0,
                            ncd_score: float = 0.0,
                            episodio_score: float = 0.0,
                            analogia_score: float = 0.0,
                            campo_score: float = 0.0):
    """Score hibrido: senales + JSD + Predicados + PPMI + Hub.
    grupo_score: similitud por grupo semántico WordNet (coseno binario).
    tematico_score: similitud temática por ausencia/presencia de dimensiones (IDF).
    match_exacto: preserva precisión en búsquedas por nombre exacto (floor 0.5).
    jsd_score: Jensen-Shannon Divergence como similitud [0,1].
    jsd_weight: peso de JSD en la fórmula (0.0 = desactivado, 0.05 = default activo).
    pred_score: matching de query tokens contra predicados SRL [0,1].
    ppmi_score: similitud vectorial PPMI+SVD+Retrofitting normalizada [0,1]. Signal #13 (v26.0)."""
    asoc_norm = min(1.0, asoc_count / 20.0)
    peso_norm = min(1.0, peso_sinaptico)

    # Gate per-candidate: tematico_score solo si hay evidencia léxica real
    # (bm25_norm > 0.001 o concepto_ratio > 0.001). Sin evidencia léxica,
    # tematico_score no debe poder mover el score sola.
    tematico_score_gated = tematico_score if (bm25_norm > 0.001 or concepto_ratio > 0.001) else 0.0

    # Base weights (sum to 1.0 when jsd_weight=0, constants.PPMI_VECTOR_WEIGHT folded in)
    # Weights dict: bm25=0.25, dim=0.14, concepto=0.08, sinonimos=0.08,
    # peso=0.10, jaccard=0.10, grupo=0.10, tematico=0.08,
    # temporal=0.04, asoc=0.02, pred=0.20, hub=0.20 = 1.39
    # constants.PPMI_VECTOR_WEIGHT = 0.15 -> total 1.54
    # Re-normalizamos todos los pesos para que sumen 1.0 - jsd_weight
    # Derivamos la suma base del dict para evitar hardcoding
    _base_weights = {
        "bm25": 0.25, "dim": 0.14, "concepto": 0.08, "sinonimos": 0.08,
        "peso": 0.10, "jaccard": 0.10, "grupo": 0.10, "tematico": 0.08,
        "temporal": 0.04, "asoc": 0.02, "pred": 0.20, "hub": 0.20,
    }
    _base_sum = sum(_base_weights.values())  # 1.39
    # Pesos pool (E6/F2/F3/F5) entran en el denominador para no inflar el total.
    total_base = _base_sum + constants.PPMI_VECTOR_WEIGHT + constants.NCD_PESO + constants.EPISODIO_TEMPORAL_PESO + constants.ANALOGIA_PESO + constants.CAMPO_POTENCIAL_PESO
    base_weight = (1.0 - jsd_weight) / total_base if total_base > 0 else 0.0

    score = (
        base_weight * (
            0.25 * bm25_norm +          # FTS5 BM25
            0.14 * dim_score +           # Dimensiones semánticas
            0.08 * concepto_ratio +      # Match en concepto
            0.08 * sinonimos_ratio +     # Match en sinónimos
            0.10 * peso_norm +           # Peso sináptico
            0.10 * max(score_latente, score_cadena) +  # Jaccard/cadena
            0.10 * grupo_score +         # Grupo semántico WordNet
            0.08 * tematico_score_gated +      # Similitud temática (gate per-candidate)
            0.04 * temporal +            # Recencia
            0.02 * asoc_norm +           # Asociaciones
            0.20 * pred_score +          # Signal #12: Predicados SRL
            constants.PPMI_VECTOR_WEIGHT * ppmi_score +  # Signal #13: PPMI+SVD
            0.20 * hub_match +            # Signal #14: Concept Hub
            constants.NCD_PESO * ncd_score +  # E6: 1-NCD zlib, solo pool
            constants.EPISODIO_TEMPORAL_PESO * episodio_score +  # F2: afinidad temporal pool
            constants.ANALOGIA_PESO * analogia_score +  # F3: analogia relacional PPMI
            constants.CAMPO_POTENCIAL_PESO * campo_score  # F5: campo semantico PPMI
        ) +
        jsd_weight * jsd_score           # Signal #11: JSD distributional overlap
    )

    # Bonos en espacio logit (aditivos en log-odds) para preservar orden interno
    # match_exacto: bono ~logit(0.95) - logit(score_base) ≈ +2.94 log-odds
    # sinonimos_ratio >= 0.95: bono para llegar a ~0.70 + 0.10*ppmi
    if match_exacto:
        # Convertir a log-odds, sumar bono, volver a probabilidad
        p = max(1e-6, min(1-1e-6, score))
        logit = math.log(p / (1.0 - p)) + 2.94  # logit(0.95) ≈ 2.94
        score = 1.0 / (1.0 + math.exp(-logit))
    elif sinonimos_ratio >= 0.95:
        # Bono para alcanzar ~0.70 + 0.10*ppmi: bono aditivo en logit space
        target = 0.70 + 0.10 * ppmi_score
        p = max(1e-6, min(1-1e-6, score))
        logit = math.log(p / (1.0 - p))
        # Bono aditivo en espacio logit: diferencia entre target_logit y 0
        # Equivalente a añadir log(target/(1-target)) al logit
        target_logit = math.log(target / (1.0 - target))
        bonus = target_logit  # bono para llevar score base 0.5 -> target
        score = 1.0 / (1.0 + math.exp(-(logit + bonus)))

    return round(min(1.0, max(0.0, score)), 4)


def _rerank_jaccard_protect_r0(self, resultados, frase_limpia, preview_chars=1500):
    """Re-ranking jaccard léxico (Fase C) con protección de rank 0.

    Fiel a apply_rerank_protect_r0 de scripts/experimento_faseB_protect_r0.py,
    config ganadora del holdout 2026-08-04: elimina TODAS las regresiones R@1
    (variante, pregunta_natural, sinonimo, typo) manteniendo el +6 R@5 de por_tema.
    Gate por max jaccard del pool[:window]; re-sort del top-k por
    score + alpha*(jaccard/max_j); si el ítem que ocupaba la posición 0
    del pool original fue desplazado, se restaura a la primera posición.

    NOTA DE FIDELIDAD: el experimento calculó jaccard sobre el contenido YA
    truncado a preview_chars (default 1500) que retorna buscar_por_frase.
    Aquí el contenido aún está completo (el truncado ocurre después del
    re-ranking), por eso se trunca a min(preview_chars, 3000) para replicar
    el cálculo validado (71,306 jaccards reproducidos exactos).
    """
    if not resultados or len(resultados) < 2 or not frase_limpia.strip():
        return resultados

    preview_chars = min(int(preview_chars or 1500), 3000)

    import unicodedata
    from core.stopwords import _STOPWORDS_QUERY

    def strip_accents(text):
        return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))

    def tokens(text):
        t = re.sub(r'[^\w\s_-]', ' ', text.lower())
        out = []
        for w in t.split():
            wc = strip_accents(w)
            if wc not in _STOPWORDS_QUERY and len(w) >= 2:
                out.append(wc)
        return set(out)

    def jaccard(a, b):
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    q_tok = tokens(frase_limpia)
    if not q_tok:
        return resultados

    win = resultados[:constants.RERANKING_JACCARD_WINDOW]
    max_j = max(
        (jaccard(q_tok, tokens((r[1] or "")[:preview_chars])) for r in win),
        default=0.0,
    )
    if max_j < constants.RERANKING_JACCARD_GATE:
        return resultados

    original_r0 = resultados[0]
    head = resultados[:constants.RERANKING_JACCARD_TOPK]
    tail = resultados[constants.RERANKING_JACCARD_TOPK:]
    max_j_norm = max_j or 1e-9
    head = sorted(
        head,
        key=lambda r: r[4] + constants.RERANKING_JACCARD_ALPHA * (jaccard(q_tok, tokens((r[1] or "")[:preview_chars])) / max_j_norm),
        reverse=True,
    )
    if head and head[0] is not original_r0:
        head = [original_r0] + [it for it in head if it is not original_r0]
    return head + tail


def _generar_variaciones(self, query, historial_fallos=None):
    """Genera variaciones de la query basadas en el historial de fallos.

    Si "angular formularios" falló, probar:
    - Solo "angular" (más específico)
    - "angular" + sinónimos
    - Filtro por categoría probable
    """
    variaciones = []
    palabras = re.findall(r'\w{3,}', query.lower())

    # Excluir términos que ya fallaron
    palabras_filtradas = [p for p in palabras if p not in (historial_fallos or [])]

    # Solo la palabra más importante no fallida
    if palabras_filtradas:
        variaciones.append(palabras_filtradas[0])

    # ponytail: removed semantica table lookup — agent provides synonyms via parafrasis_list

    return variaciones[:3]
