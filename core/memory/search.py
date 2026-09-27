"""
Módulo de búsqueda, evocación y recall clásico (FTS5, semántico, asociativo, predicados y contenido).

Extraído de SQLiteMemoryBioRAG (Paso 3.4h - T19).
Excepción de límite de líneas por deuda técnica documentada: buscar_por_frase
se traslada intacta (2109 líneas) para preservar la integridad del pipeline de recuperación multiseñal.
"""

import os
import logging
import sqlite3
import json
import time
import re
import sys
import math
import unicodedata
from collections import deque
import numpy as np

from core.stemmer_es import _quitar_acentos
from core.memory import constants

logger = logging.getLogger("BioRAG.MemoryStore")

try:
    from core.calibracion import (zscore_por_query, fusion_rrf, FusionLogistica,
                                   CalibradorPlatt, calibracion_isotonica,
                                   UmbralConforme, mmr)
except ImportError:
    zscore_por_query = fusion_rrf = FusionLogistica = CalibradorPlatt = None
    calibracion_isotonica = UmbralConforme = mmr = None

def buscar_por_frase(self, frase, profundidad="activos", pagina=1, limite=None, categoria=None, preview_chars=1500, historial_fallos=None, context_window=0, dimensiones_dict=None, dimensiones_ids=None, parafrasis_list=None, desde_ts=None, hasta_ts=None, modo_estricto=False, usar_inferencia=True, buscar_por_rol=None, ignore_peso_sinaptico=False, ordenar_por="relevancia", permitir_expansion_empate=False, expandir_episodio=False, analogia=False, sustantivos_clave_boost=None):
    """Busqueda hibrida: FTS5 trigram + peso sinaptico + asociaciones + scoring dimensional.

    frase: texto en lenguaje natural. Trigrams nativos de FTS5 manejan
           typos, variaciones morfologicas y palabras parciales.
    profundidad: 'activos' | 'profundo'
    categoria: filtrar por tipo de memoria (ej: 'proyecto', 'leccion')
    preview_chars: longitud maxima del contenido retornado.
                   0 o None retorna el contenido completo.
                   El motor trunca en vez del CLI (ahorra RAM).
    historial_fallos: lista de queries anteriores que no dieron resultado.
                      Se usa para generar variaciones en caso de fallo.
    context_window: numero de vecinos por resultado a incluir como contexto.
                    0 = solo resultados principales (default).
                    Maximo 3. Vecinos se obtienen de sinapsis por peso.
    dimensiones_dict: dict de {eje: [ids]} para scoring dimensional.
                      Batch query post-merge → coseno binario → dim_score.
    dimensiones_ids: flat list de todos los IDs (para batch query SQL).
    desde_ts: timestamp Unix mínimo para filtro temporal PRE-hoc (creado_en).
    hasta_ts: timestamp Unix máximo para filtro temporal PRE-hoc (creado_en).
    buscar_por_rol: string con filtro por roles semánticos (ej: 'sujeto:Dennys')
    ordenar_por: 'relevancia' (default, orden por score híbrido), 'recencia' (creado_en DESC,
                 más recientes primero) o 'antiguedad' (creado_en ASC, más antiguos primero).
                 Post-hoc: reordena el conjunto ya filtrado por relevancia ANTES de paginar.
                 WARNER: solo responde intención temporal, no determina relevancia.
    permitir_expansion_empate: si True, amplía el límite cuando candidatos justo debajo
                 del corte tienen score >= 90% del último incluido (Dynamic Multiplicator).
                 Default False: `limite` es un contrato estricto, el motor nunca devuelve
                 más resultados de los pedidos.
    Retorna (resultados, total) donde resultados es lista de
    (concepto, contenido, peso, estado, score, asociaciones)
    """
    self.notificar_actividad_usuario()
    self.last_parent_map = {}  # Reset parent pointers for this search
    # SRL v16.0: Filtrado por roles semánticos (buscar_por_rol)
    conceptos_validos_rol = None
    if buscar_por_rol:
        filtros_rol = {}
        for parte in buscar_por_rol.split(","):
            if ":" in parte:
                k, v = parte.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                if k in ("sujeto", "accion", "objeto", "contexto"):
                    filtros_rol[k] = v
        if filtros_rol:
            conceptos_validos_rol = set()
            # Consultar predicados en largo plazo
            sql_rol = "SELECT DISTINCT concepto FROM predicados WHERE 1=1"
            params_rol = []
            for col, val in filtros_rol.items():
                sql_rol += f" AND {col} = ?"
                params_rol.append(val)
            self.cursor.execute(sql_rol, tuple(params_rol))
            for row in self.cursor.fetchall():
                conceptos_validos_rol.add(row[0].lower().strip())
            # Consultar predicados en corto plazo
            sql_rol_cp = "SELECT DISTINCT concepto FROM corto_plazo_predicados WHERE 1=1"
            for col in filtros_rol.keys():
                sql_rol_cp += f" AND {col} = ?"
            self.cursor.execute(sql_rol_cp, tuple(params_rol))
            for row in self.cursor.fetchall():
                conceptos_validos_rol.add(row[0].lower().strip())

    if pagina < 1:
        pagina = 1
    if limite is None:
        limite = constants.LIMITE_DEFAULT
    # Si no hay frase Y no hay dimensiones Y no hay rol, retornar vacío
    # PERO si hay dimensiones o rol (aunque no haya frase), continuar
    if not frase.strip() and not dimensiones_ids and not buscar_por_rol:
        if constants.EPISTEMICO_METADATA:
            self._epistemico_publicar_sin_consulta()
        return [], 0

    # Parsear términos entre comillas dobles ("CV", "IA") para bypass de trigram
    protected_terms = re.findall(r'"([^"]+)"', frase)
    frase_limpia = re.sub(r'"[^"]+"', '', frase).strip()
    frase_limpia = re.sub(r'\s+', ' ', frase_limpia).strip()
    solo_protegidos = bool(protected_terms) and not frase_limpia

    # Filtrar stopwords de la frase_limpia
    from core.stopwords import _STOPWORDS_QUERY
    import unicodedata

    def strip_accents(text):
        return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))

    stopwords_normalized = {strip_accents(w) for w in _STOPWORDS_QUERY}

    clean_phrase_tokens = []
    if frase_limpia.strip():
        clean_p = re.sub(r'[^\w\s_-]', ' ', frase_limpia.lower())
        for w in clean_p.split():
            w_clean = strip_accents(w)
            if w_clean not in stopwords_normalized and len(w) >= 2:
                clean_phrase_tokens.append(w)

    if clean_phrase_tokens:
        frase_limpia_filtrada = " ".join(clean_phrase_tokens)
    else:
        frase_limpia_filtrada = re.sub(r'[^\w\s_-]', ' ', frase_limpia.lower()).strip()

    frase = frase_limpia_filtrada
    query = frase_limpia_filtrada if not solo_protegidos else ""

    # ── GUARD: solo expandir si la búsqueda normal (sin expandir) no alcanza ──
    # Medido esta sesión: expandir SIEMPRE (Concept Hub + WordNet + Domain Dict)
    # regresionó 'literal' de ~100%→73% y Spreading Activation de 6%→1.4% —
    # el ruido de los términos inyectados competía con queries que ya
    # matcheaban limpio. Probe barato: ¿la query CRUDA ya encuentra >=3 por
    # FTS5 AND? Si sí, no expandir — ya no hace falta y solo mete ruido.
    _necesita_expansion = True
    if frase.strip() and len(frase.split()) >= 1:
        try:
            # Escape simple e independiente — _fts_safe_phrase se define más
            # abajo en esta misma función, no está disponible aquí todavía
            # (bug real detectado: la primera versión de este guard llamaba
            # a _fts_safe_phrase antes de su definición, NameError silencioso
            # por el except Exception, y el guard nunca bloqueaba nada).
            _tokens_probe = [
                re.sub(r'["\x00]', '', t) for t in frase.split() if t.strip()
            ]
            _tokens_probe = [t for t in _tokens_probe if t]
            if _tokens_probe:
                _fts_and_probe = " AND ".join(f'"{t}"' for t in _tokens_probe)
                _cnt_probe = self.cursor.execute(
                    "SELECT COUNT(*) FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?",
                    (_fts_and_probe,)
                ).fetchone()[0]
                _necesita_expansion = _cnt_probe == 0
        except Exception as exc:
            logger.debug(f"[BioRAG.Probe] Excepción en probe FTS5 AND (fallback a expandir=True): {exc}")
            _necesita_expansion = True  # si el probe falla, más seguro expandir

    # ── CONCEPT HUB: Expansión semántica pre-FTS5 (condicional, igual que WordNet y DomainDict)
    # El hub resuelve el "abismo léxico": queries que no tienen ningún overlap léxico con el
    # nodo correcto. Pero si FTS5 ya encontró candidatos (probe AND), inyectar hub_terms
    # contamina el score BM25: los términos expandidos tienen IDF bajo y dilluyen el peso de
    # los tokens originales (vocabulary drift), empujando el nodo correcto fuera del top-5.
    #
    # Guard invariante al tamaño del corpus:
    #   _necesita_expansion = True  si el probe FTS5 AND retorna 0 resultados
    #   _necesita_expansion = False si ya hay al menos 1 hit léxico directo
    # Este check es relativo a la query, no al corpus — no cambia si el corpus crece.
    # Alineado con WordNet (L4260) y DomainDict (L4303) que usan el mismo guard.
    #
    # La promoción del nodo canónico (post-ranking, L5568+) sigue activa siempre,
    # independientemente de este guard — el Hub sigue rescatando abismos léxicos
    # via hub_val en score híbrido y canonical insertion directa desde DB.
    hub_expansion = None
    # BIORAG_HUB_ENABLED (default "1"): apaga TANTO la expansión de términos
    # COMO la promoción del nodo canónico post-ranking, para ablación limpia.
    if os.environ.get("BIORAG_HUB_ENABLED", "1") != "0":
        try:
            from core.concept_hub import expandir_query_con_hub
            hub_expansion = expandir_query_con_hub(frase_limpia, self.conn, threshold=0.40)
            if hub_expansion and hub_expansion.get("expanded_terms") and _necesita_expansion:
                hub_terms = " ".join(hub_expansion["expanded_terms"])
                frase = frase + " " + hub_terms
                # NOTA: NUNCA sobreescribir 'query = frase'.
                # 'query' debe conservar los términos originales del usuario para
                # evitar explosión combinatoria O(N*M) en el scoring simbólico (Levenshtein).
        except Exception as exc:
            logger.warning(f"[BioRAG.ConceptHub] Excepción en expandir_query_con_hub: {exc}")
            hub_expansion = None

    # ── WORDNET EXPANDIDO: Expansión automática por sinónimos+hiperonimios ──
    # Solo para palabras genuinamente en inglés (WordNet en inglés).
    # Evitar palabras en español que pasen por ser ASCII puro (sin tildes ni ñ).
    # BIORAG_WORDNET_ENABLED (default "1"): apaga la expansión léxica y la Capa 5 de scoring.
    if _necesita_expansion and os.environ.get("BIORAG_WORDNET_ENABLED", "1") != "0":
      try:
        from core.stopwords import STOPWORDS_ES
        from nltk.corpus import wordnet as _wn
        tokens_frase_orig = [w for w in frase_limpia_filtrada.split() if len(w) >= 3]

        wordnet_terms = []
        for token in tokens_frase_orig[:6]:  # máx 6 tokens originales
            token_l = token.lower()
            if token_l in STOPWORDS_ES:
                continue
            # Si la palabra tiene synsets en español (OMW), es palabra española -> no expandir con inglés
            try:
                spa_synsets = _wn.synsets(token_l, lang='spa')
                if spa_synsets:
                    continue
            except Exception:
                pass

            # Solo si es ASCII y parece término técnico en inglés
            import re as _re
            if _re.match(r'^[a-zA-Z]{3,}$', token):
                try:
                    synsets = _wn.synsets(token)
                    for s in synsets[:2]:
                        for l in s.lemmas():
                            name = l.name().replace('_', ' ')
                            if name.lower() != token.lower() and name not in wordnet_terms:
                                wordnet_terms.append(name)
                                if len(wordnet_terms) >= 8:
                                    break
                        if len(wordnet_terms) >= 8:
                            break
                except Exception:
                    pass
        if wordnet_terms:
            frase = frase + " " + " ".join(wordnet_terms)
      except Exception:
        pass  # WordNet no disponible — fallback silencioso

    # ── DOMAIN DICT: Expansión por diccionario de dominio técnico ──
    # Cache: carga el diccionario una vez por instancia de cerebro.
    # Solo expande sobre los tokens ORIGINALES de la query, no sobre lo ya expandido.
    if _necesita_expansion:
      try:
        if not hasattr(self, '_domain_dict_cache'):
            cursor_dict = self.conn.execute(
                "SELECT term, synonyms FROM concept_hub_domain_dict"
            )
            self._domain_dict_cache = {row[0]: row[1] for row in cursor_dict.fetchall()}
        tokens_originales = frase_limpia_filtrada.split()
        domain_terms = []
        for token in tokens_originales:
            token_lower = token.lower()
            if token_lower in self._domain_dict_cache and self._domain_dict_cache[token_lower]:
                synonyms = self._domain_dict_cache[token_lower].split(',')
                domain_terms.extend(synonyms[:3])  # máx 3 sinónimos por término
        if domain_terms:
            frase = frase + " " + " ".join(domain_terms)
      except Exception:
        pass  # Tabla domain_dict no existe aún — fallback silencioso

    # Filtrar stopwords de la lista de paráfrasis
    parafrasis_filtradas = []
    if parafrasis_list:
        for p in parafrasis_list:
            p_clean = re.sub(r'[^\w\s_-]', ' ', p.lower())
            p_words = [w for w in p_clean.split() if strip_accents(w) not in stopwords_normalized and len(w) >= 2]
            if p_words:
                parafrasis_filtradas.append(" ".join(p_words))

    # EARLY-EXIT: Detectar queries adversarias/basura que cascadearían por todos los fallbacks
    # Si la query limpia no tiene tokens válidos (>=2 chars, no stopwords) Y no hay términos protegidos,
    # NO entrar en la cascada de fallbacks costosos → retornar vacío inmediato
    tokens_validos = [w for w in frase.split() if len(w) >= 2 and strip_accents(w) not in stopwords_normalized]
    tiene_parafrasis_validas = any(len(p.split()) > 0 for p in parafrasis_filtradas)

    # Query es basura si: no tiene tokens válidos, no tiene términos protegidos, no tiene paráfrasis válidas
    # Y es muy larga (>200 chars) o tiene alta entropía (solo ruido) → evita DoS por cascada
    es_basura = (
        not tokens_validos and 
        not protected_terms and 
        not tiene_parafrasis_validas and
        (len(frase) > 200 or len(set(frase.lower())) > 50)  # largo o alta diversidad de chars = ruido
    )

    if es_basura:
        # Log para auditoría
        # print(f"[EARLY-EXIT] Query basura detectada, saltando cascada fallbacks: '{frase[:50]}...'")
        if constants.EPISTEMICO_METADATA:
            self._epistemico_publicar_sin_consulta()
        return [], 0

    # Calcular pesos diferenciales de tokens por centralidad en la red
    pesos_tokens = self._pesar_tokens_query(frase)

    # Build filter clauses
    filtros = []
    temporal_params = []
    if profundidad != "profundo":
        filtros.append("l.estado = 'activo'")
    if categoria:
        cat_id = self._resolver_categoria_id(categoria)
        filtros.append(f"l.categoria = {cat_id}")
    # v13: filtro temporal PRE-hoc (aplicar en SQL, no post-hoc)
    if desde_ts is not None:
        filtros.append("l.creado_en >= ?")
        temporal_params.append(desde_ts)
    if hasta_ts is not None:
        filtros.append("l.creado_en <= ?")
        temporal_params.append(hasta_ts)
    clause = (" AND " + " AND ".join(filtros)) if filtros else ""

    def _fts_safe_term(term):
        """Split hyphenated tokens so FTS5 doesn't parse '-' as NOT operator.
        'fin-aprendizaje-creerse' -> 'fin aprendizaje creerse'"""
        import re as _re
        parts = _re.split(r'[-]+', term)
        return " ".join(p for p in parts if p)

    def _fts_safe_phrase(phrase):
        """Apply _fts_safe_term to each whitespace-separated token in a phrase."""
        return " ".join(_fts_safe_term(t) for t in phrase.split())

    # RF-18 (spec 001): simetría de acentos con la columna sustantivos_clave.
    # Evidencia empírica T7 (2026-09-17): FTS5 trigram es accent-SENSITIVE en
    # ambos lados; el contenido/concepto/sinónimos del corpus conserva tildes
    # originales. Normalizar la query general aquí ROMPE el matching contra ese
    # contenido (MATCH 'metodologia' -> 0 hits vs contenido "metodología"), lo que
    # regresionó por_tema en evaluar_qa (89.23% -> 81.54%). La simetría real se
    # resuelve SOLO en el boost de sustantivos_clave (columna que siempre se
    # almacena sin tildes) — ver bloque RF-19 abajo. La query principal se envía
    # tal cual al fts_match.
    frase_fts = frase
    parafrasis_fts = parafrasis_list

    # ponytail: no semantic expansion table — agent passes synonyms as parafrasis_list directly
    if modo_estricto:
        if parafrasis_fts:
            fts_match = " OR ".join(f"({' AND '.join(_fts_safe_phrase(v).split())})" for v in [frase_fts] + parafrasis_fts)
        elif len(frase_fts.split()) > 1:
            fts_match = " AND ".join(_fts_safe_phrase(frase_fts).split())
        else:
            fts_match = _fts_safe_phrase(frase_fts)
    elif parafrasis_fts:
        fts_variantes = [f'"{_fts_safe_phrase(frase_fts)}"'] + [f'"{_fts_safe_phrase(p)}"' for p in parafrasis_fts]
        fts_match = " OR ".join(fts_variantes)
    elif len(frase_fts.split()) > 1:
        fts_match = " OR ".join(_fts_safe_phrase(frase_fts).split())
    else:
        fts_match = _fts_safe_phrase(frase_fts)

    # RF-19 (spec 001): boost por sustantivos_clave — condición MATCH adicional en la
    # columna dedicada (peso BM25 4.0x según RF-5). Solo en modo no estricto (path
    # default): en estricto un OR debilitaría la semántica AND. Solo se construye cuando
    # se provee, porque el FTS de snapshots legacy (3 columnas) no tiene la columna.
    if sustantivos_clave_boost and not modo_estricto:
        sk_tokens = [t for t in _quitar_acentos(str(sustantivos_clave_boost)).split(",") if t]
        if sk_tokens:
            sk_fts = " OR ".join(f'"{_fts_safe_term(t)}"' for t in sk_tokens)
            boost_match = f"sustantivos_clave:({sk_fts})"
            fts_match = f"({fts_match}) OR {boost_match}" if fts_match else boost_match
    sql = """
        SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
               l.estado, l.asociaciones,
               bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) AS bm25_val
        FROM largo_plazo_fts f
        CROSS JOIN largo_plazo l ON l.rowid = f.rowid
        WHERE largo_plazo_fts MATCH ?{filtro}
        ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) * (0.5 + 0.5 * l.peso_sinaptico)
    """.format(filtro=clause)

    todos = []
    bm25_raw = {}  # concepto -> raw BM25 from FTS5
    # Split hyphenated tokens for FTS5 safety and better matching
    palabras_raw = [w for w in frase.split() if len(w) >= 2]
    palabras = []
    for w in palabras_raw:
        partes = re.split(r'[-]+', w)
        palabras.extend(p for p in partes if p and len(p) >= 2)
    if not palabras:
        palabras = palabras_raw
    origen_scores = {}  # Side channel: rastrea origen de cada nodo para Dynamic Multiplicator

    # SRL v16.0: si no hay frase pero hay roles, popular todos directamente
    if not frase.strip() and conceptos_validos_rol:
        placeholders = ",".join(["?" for _ in conceptos_validos_rol])
        sql_rol_all = f"""
            SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones
            FROM largo_plazo
            WHERE concepto IN ({placeholders})
        """
        fb_rol_filtros = []
        fb_rol_params = list(conceptos_validos_rol)
        if profundidad != "profundo":
            fb_rol_filtros.append("estado = 'activo'")
        if categoria:
            cat_id = self._resolver_categoria_id(categoria)
            fb_rol_filtros.append(f"categoria = {cat_id}")
        if fb_rol_filtros:
            sql_rol_all += " AND " + " AND ".join(fb_rol_filtros)

        try:
            self.cursor.execute(sql_rol_all, tuple(fb_rol_params))
            for row in self.cursor.fetchall():
                todos.append(row)
                origen_scores[row[1]] = ("literal", 0.0)
        except sqlite3.OperationalError:
            pass

    # ─── Capa 2: LIKE en concepto (siempre activa) ───
    # Busca coincidencia por substring en el nombre del concepto.
    # Complementa a FTS5: maneja guiones, puntos y caracteres especiales
    # que FTS5 trigram no tokeniza bien como palabras completas.
    # Split hyphenated tokens for better substring matching.
    palabras_like = []
    for w in frase.split():
        if len(w) >= 2:
            partes = re.split(r'[-]+', w)
            palabras_like.extend(p for p in partes if p and len(p) >= 2)
    if not palabras_like:
        palabras_like = [w for w in frase.split() if len(w) >= 2]
    resultados_concepto = {}
    if palabras_like:
        like_clauses = []
        like_params = []
        for w in palabras_like:
            like_clauses.append(
                "(l.concepto LIKE '%' || ? || '%' AND "
                "(PALABRA_COMPLETA(?, l.concepto) = 1 OR length(?) >= 5))"
            )
            like_params.extend([w, w, w])
        like_where = " AND ".join(like_clauses)
        clause_like = clause.replace("l.", "") if clause else ""
        sql_like = f"""
            SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
                   l.estado, l.asociaciones
            FROM largo_plazo l
            WHERE {like_where}{clause_like}
        """
        try:
            self.cursor.execute(sql_like, like_params + temporal_params)
            for r in self.cursor.fetchall():
                match_ratio = sum(1 for w in palabras_like if w.lower() in r[1].lower()) / len(palabras_like)
                resultados_concepto[r[1]] = match_ratio
                origen_scores[r[1]] = ("concepto", match_ratio)
        except sqlite3.OperationalError:
            pass

    # Filtro DB-side PALABRA_COMPLETA: previene falsos positivos de FTS5 trigram
    # ("culo" no debe matchear "artículos"). Aplica a contenido+concepto+sinonimos.
    # Exige que AL MENOS UNA palabra aparezca como palabra completa en alguno.
    # Relajación: solo se exige PALABRA_COMPLETA para palabras cortas (longitud <= 4).
    palabras_pc = [w for w in palabras if len(w) <= 4]
    pc_clause = ""
    pc_params = []
    if palabras_pc:
        pc_clauses = []
        for p in palabras_pc:
            pc_clauses.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)")
            pc_params.extend([p, p, p])
        pc_clause = " AND (" + " OR ".join(pc_clauses) + ")"
    # v30.2: Generación FTS desacoplada (B2) — sql_con_pc = sql (sin pc_clause en NEAR+AND+OR).
    # El filtrado destructivo de FTS se reemplaza por el Quality Gate de Fallback 2.1 (B3).
    sql_con_pc = sql
    pc_params = []

    # Intentar NEAR query primero (palabras cercanas entre sí)
    # Split hyphenated tokens so FTS5 doesn't parse '-' as NOT operator
    palabras_safe = []
    for w in palabras:
        partes = re.split(r'[-]+', w)
        palabras_safe.extend(p for p in partes if p and len(p) >= 2)
    if not solo_protegidos and len(palabras_safe) > 1:
        near_query = f'NEAR({" ".join(palabras_safe)}, 15)'
        try:
            self.cursor.execute(sql_con_pc, tuple([near_query]) + tuple(temporal_params) + tuple(pc_params))
            _raw = self.cursor.fetchall()
            todos = []
            for r in _raw:
                todos.append(r[:6])
                bm25_raw[r[1]] = r[6]
                origen_scores[r[1]] = ("literal", 0.0)
        except sqlite3.OperationalError:
            pass

    # Fallback 1.0: FTS5 AND exacto (usar fts_match si hay paráfrasis)
    if not solo_protegidos and not todos:
        try:
            self.cursor.execute(sql_con_pc, (fts_match,) + tuple(temporal_params) + tuple(pc_params))
            _raw = self.cursor.fetchall()
            todos = []
            for r in _raw:
                todos.append(r[:6])
                bm25_raw[r[1]] = r[6]
                origen_scores[r[1]] = ("literal", 0.0)
        except sqlite3.OperationalError:
            pass

    # NEAR early-exit fix: si NEAR devolvió candidatos pero con pool pequeño (3 <= len(todos) < limite),
    # merge con los mejores candidatos de BM25 OR en vez de bloquear el fallback (caso 0497)
    if not solo_protegidos and 3 <= len(todos) < limite and fts_match:
        try:
            self.cursor.execute(sql_con_pc, (fts_match,) + tuple(temporal_params) + tuple(pc_params))
            _raw = self.cursor.fetchall()
            seen_rowids = {r[0] for r in todos}
            for r in _raw:
                if r[0] not in seen_rowids:
                    todos.append(r[:6])
                    bm25_raw[r[1]] = r[6]
                    if r[1] not in origen_scores:
                        origen_scores[r[1]] = ("literal", 0.0)
                    seen_rowids.add(r[0])
        except sqlite3.OperationalError:
            pass

    # Store FTS5-only concepts for pseudo-relevance feedback (before content expansion)
    fts5_conceptos = [r[1] for r in todos if r[1]]

    # ─── Términos protegidos: búsqueda exacta contra unicode61 + PALABRA_COMPLETA ───
    # Los términos entre comillas dobles ("CV", "IA") bypassan trigram y se buscan
    # como palabras completas en el índice unicode61.
    if protected_terms:
        pc_prot_conds = []
        pc_prot_params = []
        for pt in protected_terms:
            pc_prot_conds.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)")
            pc_prot_params.extend([pt, pt, pt])
        pc_prot_clause = " AND (" + " OR ".join(pc_prot_conds) + ")"
        fts_protected = " OR ".join(f'"{t}"' for t in protected_terms)
        try:
            self.cursor.execute(
                f"SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
                f"l.estado, l.asociaciones, "
                f"bm25(largo_plazo_fts_unicode) AS bm25_val "
                f"FROM largo_plazo_fts_unicode f "
                f"CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
                f"WHERE largo_plazo_fts_unicode MATCH ?"
                f"{clause}{pc_prot_clause} "
                f"ORDER BY bm25(largo_plazo_fts_unicode) "
                f"LIMIT ?",
                (fts_protected,) + tuple(temporal_params) + tuple(pc_prot_params) + (limite * 3,)
            )
            prot_results = self.cursor.fetchall()
            seen_rowids = {r[0] for r in todos}
            for r in prot_results:
                if r[0] not in seen_rowids:
                    todos.append(r[:6])
                    bm25_raw[r[1]] = r[6]
                    origen_scores[r[1]] = ("protegido", 1.0)
                    seen_rowids.add(r[0])
        except sqlite3.OperationalError:
            pass

    # OR fallback: si AND devolvió pocos resultados (o ninguno), probar OR
    # Usar fts_match directamente cuando hay paráfrasis (ya es una expresión OR válida)
    # SIEMPRE usar sql_con_pc (con PALABRA_COMPLETA) para evitar falsos positivos.
    if not modo_estricto and (not todos or len(todos) < max(limite * 2, 5)) and len(frase.split()) > 1:
        if not todos and fts_match != frase:
            # Si hay paráfrasis y no se encontró nada, usar fts_match directamente
            try:
                self.cursor.execute(sql_con_pc, (fts_match,) + tuple(temporal_params) + tuple(pc_params))
                or_results = self.cursor.fetchall()
                seen_rowids = {r[0] for r in todos}
                for r in or_results:
                    if r[0] not in seen_rowids:
                        origen_scores[r[1]] = ("parafrasis", 0.0)
                        todos.append(r[:6])
                        bm25_raw[r[1]] = r[6]
            except sqlite3.OperationalError:
                pass

    # Fallback 1.4: FTS5 unicode61 con prefix wildcards
    # Mejora recall para palabras que comparten prefijo (react -> reactive, forms -> formularios).
    # Último recurso: corre si la búsqueda literal arrojó menos de 3 resultados.
    if not modo_estricto and len(todos) < 3:
        try:
            query_wild = self._agregar_prefix_wildcards(query)
            sql_unicode = """
                SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
                       l.estado, l.asociaciones,
                       bm25(largo_plazo_fts_unicode) AS bm25_val
                FROM largo_plazo_fts_unicode f
                CROSS JOIN largo_plazo l ON l.rowid = f.rowid
                WHERE largo_plazo_fts_unicode MATCH ?{filtro}
                ORDER BY bm25(largo_plazo_fts_unicode)
                LIMIT ?
            """.format(filtro=clause)
            self.cursor.execute(sql_unicode, (query_wild,) + tuple(temporal_params) + (max(limite * 3, 10),))
            uni_results = self.cursor.fetchall()
            seen_rowids = {r[0] for r in todos}
            for r in uni_results:
                if r[0] not in seen_rowids:
                    todos.append(r[:6])
                    bm25_raw[r[1]] = r[6]
                    origen_scores[r[1]] = ("unicode", 0.0)
        except sqlite3.OperationalError:
            pass

    # ponytail: removed semantic expansion fallback — agent passes synonyms directly

    # Fallback 1.7: best-word trigram similarity (typo + word-match tolerance)
    # Filtro PC: solo aplica a palabras CORTAS (<=5 chars) donde el trigrama no
    # es discriminante (ej: "culo" como substring de "artículos"). Para palabras
    # largas (>=6 chars), el trigrama ya es tolerante a typos sin generar FPs.
    if not modo_estricto and len(todos) < 3 and len(query) >= 3:
        sql_limit = max(200, limite * 10)
        filtros_fb = []
        if profundidad != "profundo":
            filtros_fb.append("estado = 'activo'")
        if categoria:
            cat_id_fb2 = self._resolver_categoria_id(categoria)
            filtros_fb.append(f"categoria = {cat_id_fb2}")
        where_fb = ("WHERE " + " AND ".join(filtros_fb)) if filtros_fb else ""
        try:
            self.cursor.execute(
                f"SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo {where_fb} ORDER BY rowid LIMIT {sql_limit}"
            )
            filas = self.cursor.fetchall()
            query_words = re.findall(r'\w{3,}', query.lower())
            query_words_filtradas = [w for w in query_words if len(w) >= 4]
            if not query_words_filtradas:
                query_words_filtradas = [w for w in query_words if len(w) >= 4]
            qw_cortas = [w for w in query_words_filtradas if len(w) <= 5]
            candidatos = []
            for row in filas:
                texto = f"{row[1]} {row[2]}".lower()
                text_words = re.findall(r'\w{3,}', texto)
                total_score = 0.0
                for qw in query_words_filtradas:
                    qt = set(qw[i:i+3] for i in range(len(qw) - 2))
                    if not qt:
                        continue
                    best = max(
                        (len(qt & set(tw[i:i+3] for i in range(len(tw) - 2))) / len(qt)
                         for tw in text_words if len(tw) >= 3),
                        default=0.0
                    )
                    total_score += best
                avg_score = total_score / len(query_words_filtradas) if query_words_filtradas else 0.0
                if avg_score >= 0.7:
                    texto_full = f"{row[1]} {row[2] or ''}".replace('_', ' ').replace('-', ' ')
                    if qw_cortas:
                        match_legitimo = any(
                            re.search(r'\b' + re.escape(qw) + r'\b', texto_full, re.IGNORECASE)
                            for qw in qw_cortas
                        )
                        if not match_legitimo:
                            continue
                    candidatos.append((avg_score, row))
            candidatos.sort(key=lambda x: x[0], reverse=True)
            seen_rowids = {r[0] for r in todos}
            for score_typo, row in candidatos[:max(limite * 3, 10)]:
                if row[0] not in seen_rowids:
                    todos.append(row)
                    if row[1] not in origen_scores:
                        origen_scores[row[1]] = ("typo", score_typo)
        except sqlite3.OperationalError:
            pass

    # Fallback 1.8: Similitud conceptual latente (Jaccard vecinos + contenido)
    # Usa Jaccard sobre tokens, no requiere match literal. No aplicar PALABRA_COMPLETA.
    # Dynamic Multiplicator: registrar como "latente" con score Jaccard real
    # OPTIMIZACIÓN: Pre-cargar puentes FTS5 una vez (reduce N queries a 1)
    # PROTECCIÓN DoS: Early-exit para queries adversarias + subgraph bounding
    if not modo_estricto and len(todos) < 3 and len(query) >= 2:
        # Early-exit: queries muy largas o con alta entropía (probablemente basura/adversarial)
        # no justifican el costo O(N^1.6) de similitud latente
        if len(query) > 200:
            pass  # Skip latent similarity for adversarial-length queries
        else:
            from core.similitud_conceptual import _tokenizar_query, score_similitud_latente, LIMITE_SIMILITUD, _cargar_grafo, _limpiar_cache
            query_tokens = _tokenizar_query(query)
            if query_tokens:
                try:
                    try:
                        grafo = _cargar_grafo(self.cursor)
                        # Batch: pre-fetch puentes FTS5 una vez (1 query SQL)
                        # En vez de N queries FTS5 separadas en _similitud_red
                        filtrar = [t for t in query_tokens if len(t) >= 2]
                        nodos_cache = None
                        if filtrar:
                            fts_tokens = [f'"{t}"' for t in filtrar]
                            fts_q = " OR ".join(fts_tokens)
                            # Filtro PALABRA_COMPLETA en puentes: evita falsos positivos de trigram
                            # Relajación: solo se exige PALABRA_COMPLETA para palabras cortas (longitud <= 4)
                            pc_bridge_conds = []
                            pc_bridge_params_list = []
                            for t in filtrar:
                                if len(t) <= 4:
                                    pc_bridge_conds.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)")
                                    pc_bridge_params_list.extend([t, t, t])
                                else:
                                    pc_bridge_conds.append("(1 = 1)")
                            pc_bridge_clause = " AND (" + " AND ".join(pc_bridge_conds) + ")"
                            pc_bridge_params = tuple(pc_bridge_params_list)
                            try:
                                bridge_filter = " AND l.estado = 'activo'"
                                self.cursor.execute(
                                    "SELECT DISTINCT l.concepto FROM largo_plazo_fts f "
                                    "CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
                                    "WHERE largo_plazo_fts MATCH ? " + bridge_filter
                                    + pc_bridge_clause + " LIMIT 50",
                                    (fts_q,) + pc_bridge_params
                                )
                                nodos_cache = {row[0] for row in self.cursor.fetchall()}
                            except sqlite3.OperationalError:
                                nodos_cache = None
                        fts_tokens = [f'"{t}"' for t in query_tokens if len(t) >= 2]
                        if fts_tokens:
                            fts_q = " OR ".join(fts_tokens)
                            lat_clause = " AND l.estado = 'activo'"
                            # Filtro PALABRA_COMPLETA en candidatos: evita falsos positivos de trigram
                            # Relajación: solo se exige PALABRA_COMPLETA para palabras cortas (longitud <= 4)
                            pc_lat_clause = ""
                            pc_lat_params = ()
                            filtrar_lat = [t for t in query_tokens if len(t) >= 2]
                            if filtrar_lat:
                                pc_lat_conds = []
                                pc_lat_params_list = []
                                for t in filtrar_lat:
                                    if len(t) <= 4:
                                        pc_lat_conds.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1 OR PALABRA_COMPLETA(?, COALESCE(l.sinonimos, '')) = 1)")
                                        pc_lat_params_list.extend([t, t, t])
                                    else:
                                        pc_lat_conds.append("(1 = 1)")
                                pc_lat_clause = " AND (" + " AND ".join(pc_lat_conds) + ")"
                                pc_lat_params = tuple(pc_lat_params_list)
                            self.cursor.execute(
                                "SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, "
                                "l.estado, l.asociaciones "
                                "FROM largo_plazo_fts f CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
                                "WHERE largo_plazo_fts MATCH ?" + lat_clause + pc_lat_clause + " LIMIT ?",
                                (fts_q,) + pc_lat_params + (constants.CANDIDATOS_SIMILITUD,)
                            )
                            candidatos_lat = self.cursor.fetchall()

                            # SUBGRAPH BOUNDING: Solo procesar candidatos con grado mínimo en el grafo
                            # Evita recorrer nodos aislados que solo añaden ruido y costo
                            if grafo:
                                candidatos_lat = [
                                    c for c in candidatos_lat
                                    if len(grafo.get(c[1], {})) >= 2  # min degree = 2
                                ]

                            scored = []
                            seen_rowids = {r[0] for r in todos}
                            for rowid, concepto, contenido, peso, estado, asoc in candidatos_lat:
                                if rowid in seen_rowids:
                                    continue
                                s = score_similitud_latente(self.cursor, query_tokens, concepto, contenido, grafo=grafo, nodos_cache=nodos_cache, cerebro=self)
                                if s >= 0.15:
                                    scored.append((s, (rowid, concepto, contenido, peso, estado, asoc or "")))
                            scored.sort(key=lambda x: x[0], reverse=True)
                            for jaccard_score, row in scored[:LIMITE_SIMILITUD]:
                                todos.append(row)
                                # Solo registrar si no fue encontrado por capa literal (FTS5 tiene prioridad)
                                if row[1] not in origen_scores:
                                    origen_scores[row[1]] = ("latente", jaccard_score)
                    finally:
                        _limpiar_cache()
                except sqlite3.OperationalError:
                    pass
    # Fallback 2.0: substring match con word boundary via PALABRA_COMPLETA
    if not modo_estricto and len(todos) < 3 and len(query) >= 2:
        filtros_fb = []
        if profundidad != "profundo":
            filtros_fb.append("estado = 'activo'")
        if categoria:
            cat_id_fb = self._resolver_categoria_id(categoria)
            filtros_fb.append(f"categoria = {cat_id_fb}")
        # PALABRA_COMPLETA filtra en DB: "culo" no matchea "artículo"
        filtros_fb.append("PALABRA_COMPLETA(?, contenido) = 1")
        where_fb = "WHERE " + " AND ".join(filtros_fb)
        try:
            self.cursor.execute(
                f"SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo {where_fb}",
                (query.lower(),)
            )
            filas = self.cursor.fetchall()
            seen_rowids = {r[0] for r in todos}
            for row in filas:
                if row[0] not in seen_rowids:
                    todos.append(row)
            todos = todos[:50]
        except sqlite3.OperationalError:
            pass

    # Fallback 1.8: Snap reciente (últimos 7 días)
    if not modo_estricto and len(todos) < 3 and len(query) >= 2:
        limite_tiempo = time.time() - (7 * 86400)
        # sql_con_pc ya incluye el filtro PALABRA_COMPLETA — previene falsos positivos
        sql_snap = sql_con_pc.replace("ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) * (0.5 + 0.5 * l.peso_sinaptico)",
                                      "AND l.ultimo_acceso > ? ORDER BY bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) * (0.5 + 0.5 * l.peso_sinaptico) LIMIT 5")
        try:
            self.cursor.execute(sql_snap, (query,) + tuple(temporal_params) + tuple(pc_params) + (limite_tiempo,))
            snap_r = self.cursor.fetchall()
            if snap_r:
                print(f"[TRACE] 1.8 Snap: {len(snap_r)} → {[r[1] for r in snap_r[:3]]}")
            seen_rowids = {r[0] for r in todos}
            for r in snap_r:
                if r[0] not in seen_rowids:
                    todos.append(r[:6])
                    bm25_raw[r[1]] = r[6]
        except sqlite3.OperationalError:
            pass

    # Fallback 1.9: Evocación por cadena (multi-hop con decay logarítmico)
    # Dynamic Multiplicator: registrar como "cadena" con score de decay
    if not modo_estricto and len(todos) < 3 and len(query) >= 2:
        tokens_query = re.findall(r'\w{3,}', query.lower())
        if tokens_query:
            fts_tokens = [f'"{t}"' for t in tokens_query if len(t) >= 3]
            if fts_tokens:
                fts_q = " OR ".join(fts_tokens)
                # Filtro PALABRA_COMPLETA en semillas: evita que la cadena evoque desde
                # falsos positivos de trigram. Relajación: longitud <= 4.
                pc_seed_conds = []
                pc_seed_params_list = []
                for t in fts_tokens:
                    clean_t = t.strip('"')
                    if len(clean_t) <= 4:
                        pc_seed_conds.append("(PALABRA_COMPLETA(?, l.contenido) = 1 OR PALABRA_COMPLETA(?, l.concepto) = 1)")
                        pc_seed_params_list.extend([clean_t, clean_t])
                    else:
                        pc_seed_conds.append("(1 = 1)")
                pc_seed_clause = " AND (" + " AND ".join(pc_seed_conds) + ")"
                pc_seed_params = tuple(pc_seed_params_list)
                try:
                    self.cursor.execute(
                        "SELECT l.concepto FROM largo_plazo_fts f "
                        "CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
                        "WHERE largo_plazo_fts MATCH ? AND l.estado = 'activo' "
                        + pc_seed_clause + " LIMIT 5",
                        (fts_q,) + pc_seed_params
                    )
                    semillas = [row[0] for row in self.cursor.fetchall()]
                    if semillas:
                        evocados, parent_map = self._evocacion_por_cadena(semillas)
                        self.last_parent_map = parent_map
                        for concepto_ev, decay_score, _ in evocados:
                            ev_sql = (
                                "SELECT rowid, concepto, contenido, peso_sinaptico, "
                                "estado, asociaciones FROM largo_plazo "
                                "WHERE concepto = ? AND estado = 'activo'"
                            )
                            self.cursor.execute(ev_sql, (concepto_ev,))
                            row = self.cursor.fetchone()
                            if row and row[1] not in {r[1] for r in todos} and row[2]:
                                # Filtro PALABRA_COMPLETA: el nodo evocado debe contener
                                # al menos 2 palabras de la query como palabras completas.
                                # Previene que la cadena traiga nodos no relacionados
                                # (ej: "receta de paella" → nodo con solo "receta" en contenido).
                                _contenido_ev = (row[2] or "").lower().replace('_', ' ').replace('-', ' ')
                                _concepto_ev = row[1].lower().replace('_', ' ').replace('-', ' ')
                                _matches_ev = 0
                                for _pw in palabras:
                                    _patron_ev = r'\b' + re.escape(_pw.lower()) + r'\b'
                                    if re.search(_patron_ev, _contenido_ev) or re.search(_patron_ev, _concepto_ev):
                                        _matches_ev += 1
                                        if _matches_ev >= 2:
                                            break
                                if _matches_ev < 2:
                                    continue
                                todos.append(row)
                                if row[1] not in origen_scores:
                                    origen_scores[row[1]] = ("cadena", decay_score)
                except sqlite3.OperationalError:
                    pass

    # ─── Fallback 2.1: Simbólico (Levenshtein + WordNet + Traducción) ───
    # v30.2 (B3): Fallback Quality Gate desacoplado del tamaño de pool.
    # Se activa si len(todos) < 3 O si ningún candidato FTS alcanza max_cov >= 0.60.
    # Usa _tokenizar_normalizado de core.fallback_simbolico (Strict Real: sin subcadenas espurias).
    from core.fallback_simbolico import _tokenizar_normalizado as _fb_tok
    _q_toks_fb = _fb_tok(query)
    def _calc_strict_cov(_r):
        _d_toks = _fb_tok(f"{_r[1]} {_r[2] or ''}")
        return len(_q_toks_fb & _d_toks) / len(_q_toks_fb) if _q_toks_fb else 0.0
    _max_cov_fb = max((_calc_strict_cov(_r) for _r in todos), default=0.0) if _q_toks_fb else 0.0
    _fb_activo = len(todos) < 3 or (len(_q_toks_fb) >= 2 and _max_cov_fb < 0.60)

    if not modo_estricto and _fb_activo and len(query) >= 3:
        try:
            from core.fallback_simbolico import buscar_fallback_simbolico
            estado_filter = "WHERE estado = 'activo'" if profundidad != "profundo" else ""
            cat_filter = ""
            if categoria:
                cat_id_fb = self._resolver_categoria_id(categoria)
                cat_filter = f" AND categoria = {cat_id_fb}" if estado_filter else f"WHERE categoria = {cat_id_fb}"

            self.cursor.execute(
                f"SELECT rowid, concepto, contenido, peso_sinaptico, "
                f"estado, asociaciones, sinonimos "
                f"FROM largo_plazo {estado_filter}{cat_filter} "
                f"LIMIT 1000"
            )
            candidatos_fb = self.cursor.fetchall()
            if candidatos_fb:
                fb_results = buscar_fallback_simbolico(
                    query,
                    candidatos_fb,
                    umbral=0.60,
                    top_k=10
                )
                seen_rowids = {r[0] for r in todos}
                for score_fb, rowid, conc, cont, peso, est, asoc in fb_results:
                    if rowid not in seen_rowids:
                        todos.append((rowid, conc, cont, peso, est, asoc or ""))
                        seen_rowids.add(rowid)
                    # Promover origen_scores a "simbolico" si la puntuación simbólica es superior
                    prev_origen, prev_sc = origen_scores.get(conc, (None, 0.0))
                    if prev_origen != "simbolico" or score_fb > prev_sc:
                        origen_scores[conc] = ("simbolico", score_fb)
        except ImportError:
            pass
        except Exception:
            pass

    # ─── Fallback 2.2: Expansión Sináptica (spreading activation) ───
    # Cuando todas las capas devuelven < 3 resultados, usar el grafo de sinapsis
    # para encontrar nodos conectados a las semillas (nodos que SÍ matchean).
    # Automático — no requiere configuración.
    if not modo_estricto and len(todos) < 3 and len(query) >= 2:
        try:
            from core.similitud_conceptual import buscar_por_similitud_latente
            latente_results = buscar_por_similitud_latente(
                self.cursor, query, limite=max(limite, 5), umbral=0.3, cerebro=self
            )
            seen_rowids = {r[0] for r in todos}
            for lat_score, row in latente_results:
                if row[0] not in seen_rowids:
                    todos.append(row[:6])
                    seen_rowids.add(row[0])
                    # Opción B: no usar lat_score para score_latente.
                    # Los nodos latentes ya tienen sus señales (BM25, dims, PPMI)
                    # computadas en el loop principal; _calcular_score_hibrido
                    # calcula score_latente desde sus señales base.
                    if row[1] not in origen_scores:
                        origen_scores[row[1]] = ("latente", 0.0)
        except ImportError:
            pass
        except Exception:
            pass

    # ─── Fallback 2.5 (E1): SDM binario 2048 bits ───
    # POR QUÉ aquí y no en scoring: el gold ausente del pool no se recupera
    # reordenando. Solo se activa si FTS+fallbacks dejaron < 3 candidatos y
    # la consulta tiene ≥ 3 tokens (consultas negativas cortas no disparan).
    # No toca layout SDM. No fusiona nodos. QCR sigue activo (FP).
    if (
        constants.SDM_FALLBACK_ACTIVO
        and not modo_estricto
        and len(todos) < 3
        and len(re.findall(r"\w{2,}", query or "")) >= 3
    ):
        try:
            from core.sdm import rescatar_fallback_sdm
            _sdm_hits = rescatar_fallback_sdm(
                self, query, limite=max(constants.SDM_FALLBACK_K, limite or 5)
            )
            _seen_sdm = {r[1] for r in todos}
            for hit in _sdm_hits:
                conc = hit["concepto"]
                if conc in _seen_sdm:
                    if conc not in origen_scores:
                        origen_scores[conc] = ("sdm", float(hit["similitud"]))
                    continue
                self.cursor.execute(
                    "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                    "FROM largo_plazo WHERE concepto = ?",
                    (conc,),
                )
                row = self.cursor.fetchone()
                if row and (profundidad == "profundo" or row[4] == "activo"):
                    todos.append(row)
                    _seen_sdm.add(conc)
                    origen_scores[conc] = ("sdm", float(hit["similitud"]))
        except Exception:
            pass

    # ─── Merge: inyectar resultados de concepto no encontrados por FTS5 ───

    if resultados_concepto:
        seen = {r[1] for r in todos}
        for concepto, match_ratio in resultados_concepto.items():
            umbral_ratio = 1.0 if modo_estricto else 0.3
            if concepto not in seen and match_ratio >= umbral_ratio:
                merge_sql = (
                    "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                    "FROM largo_plazo WHERE concepto = ?"
                )
                self.cursor.execute(merge_sql, (concepto,))
                row = self.cursor.fetchone()
                if row and (profundidad == "profundo" or row[4] == "activo"):
                    todos.append(row)

    # ─── Capa 4: inyectar resultados de sinónimos no encontrados por capas anteriores ───
    resultados_semantica = {}
    if palabras_like:
        palabras_sin = [w for w in palabras_like]
        if len(palabras_sin) <= 3:
            try:
                from core.fallback_simbolico import expandir_query_wordnet
                syn_wn = expandir_query_wordnet(set(palabras_sin))
                palabras_sin.extend([w for w in syn_wn if len(w) >= 3][:5])
            except Exception:
                pass
        if palabras_sin:
            sin_conds = " OR ".join(["l.sinonimos LIKE '%' || ? || '%'" for _ in palabras_sin])
            sin_params = list(palabras_sin)
        try:
            sin_where = f"l.sinonimos IS NOT NULL AND l.sinonimos != '' AND l.estado = 'activo' AND ({sin_conds})"
            self.cursor.execute(
                f"SELECT l.concepto, l.sinonimos, l.peso_sinaptico "
                f"FROM largo_plazo l "
                f"WHERE {sin_where}",
                sin_params
            )
            for conc, sin_text, _ in self.cursor.fetchall():
                if conc not in {r[1] for r in todos}:
                    match_ratio = sum(1 for w in palabras_like if w.lower() in (sin_text or "").lower()) / len(palabras_like)
                    umbral_sin = 1.0 if modo_estricto else 0.1
                    if match_ratio >= umbral_sin:
                        resultados_semantica[conc] = match_ratio
        except (sqlite3.OperationalError, sqlite3.ProgrammingError):
            pass
    if resultados_semantica:
        seen = {r[1] for r in todos}
        for concepto, match_ratio in resultados_semantica.items():
            if concepto not in seen:
                merge_sql = (
                    "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                    "FROM largo_plazo WHERE concepto = ?"
                )
                self.cursor.execute(merge_sql, (concepto,))
                row = self.cursor.fetchone()
                if row and (profundidad == "profundo" or row[4] == "activo"):
                    todos.append(row)
                    origen_scores[concepto] = ("semantica", match_ratio)

    # ── Fase C: índice invertido de formas aprendidas (GENERACIÓN, no ranking).
    # POR QUÉ aquí: el gold debe entrar al pool ANTES de _calcular_score_hibrido.
    # No toca FTS ni pesos. Solo inyecta nodos canónicos de episodios explicit/consolidated.
    try:
        from core.lexical_learning import resolver_formas_aprendidas
        _lex_hits = resolver_formas_aprendidas(self, frase_limpia or query or frase)
        if _lex_hits:
            _seen_lex = {r[1] for r in todos}
            for hit in _lex_hits:
                conc = hit["canonical_concept"]
                if conc in _seen_lex:
                    origen_scores[conc] = ("lexico_aprendido", hit["confidence"])
                    continue
                self.cursor.execute(
                    "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                    "FROM largo_plazo WHERE concepto = ?",
                    (conc,),
                )
                row = self.cursor.fetchone()
                if row and (profundidad == "profundo" or row[4] == "activo"):
                    todos.append(row)
                    _seen_lex.add(conc)
                    origen_scores[conc] = ("lexico_aprendido", hit["confidence"])
    except Exception:
        pass

        # v22.1: Content-based expansion for por_tema queries ───
    # Find nodes where query words appear in content, but ONLY when FTS returns
    # few results (indicates the query is thematic, not literal).
    # This ensures thematically relevant nodes are in the candidate pool.
    # Key: requires >= 2 word matches (not just 1) to avoid noise.
    # Results are prepended (not appended) to ensure they appear in top-N for thematic scoring.
    # Also: compute content_match_count for ALL nodes (not just new ones) so
    # FTS-found nodes that also match content get boosted.
    content_match_counts = {}
    if not modo_estricto and len(palabras) >= 2:
        # Compute match count for ALL current candidates
        match_count_clause = " + ".join(
            f"CASE WHEN LOWER(l.contenido) LIKE '%' || ? || '%' THEN 1 ELSE 0 END"
            for _ in palabras
        )
        match_params = [w.lower() for w in palabras]
        all_conceptos = [r[1] for r in todos if r[1]]
        if all_conceptos:
            ph = ",".join(["?" for _ in all_conceptos])
            try:
                self.cursor.execute(
                    f"SELECT concepto, ({match_count_clause}) AS match_count "
                    f"FROM largo_plazo WHERE concepto IN ({ph})",
                    match_params + all_conceptos
                )
                for conc, mc in self.cursor.fetchall():
                    content_match_counts[conc] = mc
            except sqlite3.OperationalError:
                pass

        # Only expand candidate pool when FTS returned few results
        if len(todos) < 3:
            seen_ids = {r[0] for r in todos}
            seen_conceptos = {r[1] for r in todos}
            min_matches = min(2, len(palabras))
            content_sql = f"""
                SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico,
                       l.estado, l.asociaciones,
                       ({match_count_clause}) AS match_count
                FROM largo_plazo l
                WHERE l.estado = 'activo'
                  AND ({match_count_clause}) >= ?
                ORDER BY match_count DESC, l.peso_sinaptico DESC
                LIMIT ?
            """
            try:
                self.cursor.execute(content_sql, match_params + match_params + [min_matches, max(limite * 3, 20)])
                content_new = []
                for row in self.cursor.fetchall():
                    if row[0] not in seen_ids and row[1] not in seen_conceptos:
                        content_new.append(row[:6])
                        seen_ids.add(row[0])
                        seen_conceptos.add(row[1])
                        if row[1] not in origen_scores:
                            origen_scores[row[1]] = ("contenido", min(1.0, row[6] / len(palabras) * 1.5))
                        content_match_counts[row[1]] = row[6]
                if content_new:
                    todos = content_new + todos
            except sqlite3.OperationalError:
                pass

    # Multihop v1: expansion 1-salto (flag OFF default; gate decide).
    # Solo activos+activos: jamas inyecta en dormido/profundo/negativo-921.
    if constants.MULTIHOP_EXPANSION and profundidad == "activos" and todos:
        try:
            _mh_nuevos = self._multihop_vecinos(
                [r[1] for r in todos if r[1]],
                {r[1] for r in todos if r[1]},
                constants.MULTIHOP_MAX_TOTAL,
            )
            if _mh_nuevos:
                _mh_nombres = [c for c, _ in _mh_nuevos]
                _mh_ph = ",".join("?" * len(_mh_nombres))
                _mh_rows = {
                    row[1]: row
                    for row in self.cursor.execute(
                        "SELECT rowid, concepto, contenido, peso_sinaptico,"
                        " estado, asociaciones FROM largo_plazo"
                        " WHERE concepto IN (%s) AND estado='activo'" % _mh_ph,
                        tuple(_mh_nombres),
                    )
                }
                for _c in _mh_nombres:
                    _row = _mh_rows.get(_c)
                    if _row is None:
                        continue
                    todos.append(_row)
                    if _c not in origen_scores:
                        origen_scores[_c] = ("expansion", constants.MULTIHOP_PRIOR)
        except Exception as e:
            logger.warning("multihop: expansion fallo (%s: %s)", type(e).__name__, e)

    # [AUDIT #15 — PPMI Vector Retrieval: DESCARTADO tras 3 iteraciones]
    # Iteración 1 (pool < 3, antes de SA): mató SA (27→1 queries). Revertido.
    # Iteración 2 (pool < 3, después de SA): neutral, 0 rescates (pool siempre >= 3).
    # Iteración 3 (always-on, cos > 0.55): +6 regresiones por ruido PPMI.
    # Causa raíz: FTS5 OR con trigram infla pool a 200+ nodos → bloquea fallbacks.
    # La solución correcta no es inyectar vía PPMI, es reducir ruido FTS5.

    # ─── Capa 3: Pseudo-relevance feedback for query dimensions ───
    # If no explicit dimensiones_ids but there's a query and FTS5 results,
    # use top-K FTS5 results' dimensions as pseudo-query dimensions.
    # Only trigger if FTS5 returned ≥3 results (semantic query, not noise).
    # This captures domain-specific dims (identidad_artificial, intencion_documentar)
    # that WordNet cannot classify from surface words.
    if not dimensiones_ids and frase.strip() and len(fts5_conceptos) >= 3:
        try:
            top_fts5_conceptos = fts5_conceptos[:5]
            if top_fts5_conceptos:
                placeholders = ",".join(["?" for _ in top_fts5_conceptos])
                dim_sql = f"""
                    SELECT DISTINCT dimension_id
                    FROM largo_plazo_dimensiones
                    WHERE concepto IN ({placeholders})
                """
                self.cursor.execute(dim_sql, top_fts5_conceptos)
                pseudo_dims = [row[0] for row in self.cursor.fetchall()]
                if pseudo_dims:
                    dimensiones_ids = pseudo_dims
        except Exception:
            pass  # Silently skip

    # ─── Batch query: dimensiones de todos los conceptos ───
    # Una sola query en vez de N queries individuales (rendimiento)
    dim_scores_map = {}
    if dimensiones_ids and len(dimensiones_ids) > 0:
        conceptos_todos = [r[1] for r in todos if r[1]]
        if conceptos_todos:
            placeholders = ",".join(["?" for _ in conceptos_todos])
            dim_ids_str = ",".join([str(d) for d in dimensiones_ids])
            dim_sql = f"""
                SELECT concepto, dimension_id
                FROM largo_plazo_dimensiones
                WHERE concepto IN ({placeholders})
                AND dimension_id IN ({dim_ids_str})
            """
            try:
                self.cursor.execute(dim_sql, conceptos_todos)
                # Agrupar IDs por concepto
                concepto_dim_ids = {}
                for concepto, dim_id in self.cursor.fetchall():
                    if concepto not in concepto_dim_ids:
                        concepto_dim_ids[concepto] = []
                    concepto_dim_ids[concepto].append(dim_id)
                # Coseno binario / ponderado (v16.0 auto-clustering)
                import math
                query_dim_set = set(dimensiones_ids)

                # Cargar pesos (confianzas) de las dimensiones de la query
                w_map = {}
                try:
                    self.cursor.execute(f"SELECT id, auto_generada, confianza FROM dimensiones_semanticas WHERE id IN ({dim_ids_str})")
                    for d_id, auto_gen, conf in self.cursor.fetchall():
                        w_map[d_id] = float(conf if auto_gen else 1.0)
                except Exception:
                    pass
                for d_id in query_dim_set:
                    if d_id not in w_map:
                        w_map[d_id] = float(1.0)

                sum_q2 = sum(w_map[d_id]**2 for d_id in query_dim_set)
                for concepto, doc_ids in concepto_dim_ids.items():
                    doc_set = set(doc_ids)
                    sum_d2 = sum(w_map[d_id]**2 for d_id in doc_set if d_id in w_map)
                    if sum_d2 > 0 and sum_q2 > 0:
                        dim_scores_map[concepto] = math.sqrt(sum_d2) / math.sqrt(sum_q2)
            except sqlite3.OperationalError:
                dim_scores_map = {}

    # ─── Fallback dimensional CON UMBRAL: dimensiones empujan solo si hay conexión real ───
    # "Buscar sin palabras": si FTS5 no encontró nada pero hay dimensiones,
    # traer nodos que compartan AL MENOS UMBRAL_DIMENSIONES dimensiones.
    # Umbral 3: si 3 de 7 dimensiones coinciden, hay conexión semántica real.
    # PERO: si NO hay resultados de texto (todos vacío), bajar umbral a 1 para permitir "buscar solo por dimensión"
    UMBRAL_DIMENSIONES = 3
    umbral_efectivo = 1 if len(todos) == 0 else UMBRAL_DIMENSIONES
    if dimensiones_ids and len(dimensiones_ids) >= umbral_efectivo:
        conceptos_existentes = {r[1] for r in todos if r[1]}
        dim_ids_str = ",".join([str(d) for d in dimensiones_ids])
        fb_filtros_extra = []
        fb_filtros_params = []
        if categoria:
            cat_id_fb = self._resolver_categoria_id(categoria)
            fb_filtros_extra.append("l.categoria = ?")
            fb_filtros_params.append(cat_id_fb)
        if profundidad != "profundo":
            fb_filtros_extra.append("l.estado = 'activo'")
        fb_where_extra = (" AND " + " AND ".join(fb_filtros_extra)) if fb_filtros_extra else ""
        if constants.DIM_RESONANCIA:
            # Fase A (resonancia dimensional): candidatura por merito
            # (shared DESC), sin sesgo rowid del LIMIT-500. EXP-Q: los 3
            # golds pasaban el umbral pero caian fuera de la ventana.
            fallback_sql = f"""
                SELECT d.concepto, GROUP_CONCAT(d.dimension_id)
                FROM largo_plazo_dimensiones d
                JOIN largo_plazo l ON l.concepto = d.concepto
                WHERE d.dimension_id IN ({dim_ids_str}){fb_where_extra}
                GROUP BY d.concepto
                HAVING COUNT(*) >= ?
                ORDER BY COUNT(*) DESC, l.peso_sinaptico DESC, d.concepto ASC
                LIMIT ?
            """
        else:
            fallback_sql = f"""
                SELECT d.concepto, d.dimension_id
                FROM largo_plazo_dimensiones d
                JOIN largo_plazo l ON l.concepto = d.concepto
                WHERE d.dimension_id IN ({dim_ids_str}){fb_where_extra}
                LIMIT 500
            """
        try:
            if constants.DIM_RESONANCIA:
                self.cursor.execute(fallback_sql, tuple(fb_filtros_params) + (umbral_efectivo, constants.DIM_RESONANCIA_K))
                concepto_fb_ids = {}
                for concepto, dims_csv in self.cursor.fetchall():
                    concepto_fb_ids[concepto] = [int(x) for x in (dims_csv or "").split(",") if x]
            else:
                self.cursor.execute(fallback_sql, tuple(fb_filtros_params))
                concepto_fb_ids = {}
                for concepto, dim_id in self.cursor.fetchall():
                    if concepto not in concepto_fb_ids:
                        concepto_fb_ids[concepto] = []
                    concepto_fb_ids[concepto].append(dim_id)
            if not constants.DIM_RESONANCIA and len(concepto_fb_ids) > 50:
                # Ordenar por cantidad de dimensiones compartidas (top 50)
                from collections import Counter
                dim_counts = Counter({c: len(ds) for c, ds in concepto_fb_ids.items()})
                top = dict(dim_counts.most_common(50))
                concepto_fb_ids = {c: concepto_fb_ids[c] for c in top}
            # Calcular coseno ponderado y agregar nodos nuevos SOLO si superan umbral
            import math
            query_dim_set = set(dimensiones_ids)

            # Cargar pesos para fallback
            w_map_fb = {}
            try:
                self.cursor.execute(f"SELECT id, auto_generada, confianza FROM dimensiones_semanticas WHERE id IN ({dim_ids_str})")
                for d_id, auto_gen, conf in self.cursor.fetchall():
                    w_map_fb[d_id] = float(conf if auto_gen else 1.0)
            except Exception:
                pass
            for d_id in query_dim_set:
                if d_id not in w_map_fb:
                    w_map_fb[d_id] = float(1.0)
            sum_q2_fb = sum(w_map_fb[d_id]**2 for d_id in query_dim_set)

            for concepto, doc_ids in concepto_fb_ids.items():
                if concepto in conceptos_existentes:
                    continue
                doc_set = set(doc_ids)
                shared = len(query_dim_set & doc_set)
                if shared >= umbral_efectivo:
                    sum_d2 = sum(w_map_fb[d_id]**2 for d_id in doc_set if d_id in w_map_fb)
                    coseno = math.sqrt(sum_d2) / math.sqrt(sum_q2_fb) if sum_q2_fb > 0 else 0.0
                    try:
                        self.cursor.execute(
                            "SELECT rowid, concepto, contenido, peso_sinaptico, estado, asociaciones "
                            "FROM largo_plazo WHERE concepto = ?",
                            (concepto,)
                        )
                        row = self.cursor.fetchone()
                        if row and (profundidad == "profundo" or row[4] == "activo"):
                            todos.append(row)
                            origen_scores[concepto] = ("dimensional_fallback", coseno)
                            dim_scores_map[concepto] = coseno
                            conceptos_existentes.add(concepto)
                    except sqlite3.OperationalError:
                        pass
        except sqlite3.OperationalError:
            pass

    # Normalización BM25 relativa intra-query (invariante a escala del corpus N).
    # Reemplaza la constante fija 3.0 que saturaba y comprimía scores al crecer el corpus.
    # Calcula min/max sobre los candidatos de la query actual para preservar discriminación.
    # Aplica escala = min(1.0, hi) para evitar inflar ruido en queries sin match fuerte (typos).
    # Guarda _last_bm25_bounds para que buscar_por_rafaga comparta la misma escala en biorag_recordar.
    raw_vals = [abs(v) for v in bm25_raw.values()]
    if raw_vals:
        lo, hi = min(raw_vals), max(raw_vals)
        rango = hi - lo if hi > lo else 1.0
        escala = min(1.0, hi) if hi > 0 else 1.0
        if hi > lo:
            bm25_norm_map = {c: ((abs(v) - lo) / rango) * escala for c, v in bm25_raw.items()}
        elif len(bm25_raw) == 1 and hi >= 3.0:
            bm25_norm_map = {c: escala for c, v in bm25_raw.items()}
        else:
            bm25_norm_map = {c: 0.0 for c, v in bm25_raw.items()}
        self._last_bm25_bounds = (lo, hi, escala)
    else:
        bm25_norm_map = {}
        self._last_bm25_bounds = None

    # Asignar BM25 sintético a candidatos de rescate (typo, simbólico, dimensional_fallback, concepto)
    # para que no compitan con bm25=0 frente a matches parciales débiles,
    # preservando la escala intra-query para mantener 0% falsos positivos en ruido.
    escala_activa = self._last_bm25_bounds[2] if (self._last_bm25_bounds and self._last_bm25_bounds[2] > 0.3) else 0.8
    for conc, (origen, sc_capa) in origen_scores.items():
        if conc not in bm25_norm_map and origen in ("typo", "simbolico", "dimensional_fallback", "concepto", "lexico_aprendido"):
            bm25_norm_map[conc] = min(1.0, escala_activa * float(sc_capa or 0.5))

    # ─── Capa 4.5: Precompute predicate data for scoring ───
    # Fetch predicate contexto (keywords) for all candidates
    conceptos_todos = [r[1] for r in todos if r[1]]
    pred_contexto_map = {}  # concepto -> set of predicate tokens
    if conceptos_todos:
        ph_conceptos = ",".join(["?" for _ in conceptos_todos])
        try:
            self.cursor.execute(
                f"SELECT concepto, COALESCE(contexto, '') FROM predicados WHERE concepto IN ({ph_conceptos})",
                conceptos_todos
            )
            for conc, ctx in self.cursor.fetchall():
                if conc not in pred_contexto_map:
                    pred_contexto_map[conc] = set()
                if ctx:
                    pred_contexto_map[conc].update(
                        t for t in re.findall(r'\w{3,}', ctx.lower()) if len(t) >= 3
                    )
        except Exception:
            pass

    # ─── Capa 5: Score por grupo semántico (WordNet lexnames) ───
    grupo_scores_map = {}
    # Skip WordNet for very short queries (< 3 chars) or very long (> 100 chars, likely garbage/adversarial)
    # NLTK load takes ~3s on first run, and long queries are not legitimate semantic queries
    if 3 <= len(frase) <= 100 and os.environ.get("BIORAG_WORDNET_ENABLED", "1") != "0":
        try:
            from core.clasificador_wordnet import obtener_lexnames_query
            query_lexnames = obtener_lexnames_query(frase, parafrasis_list)
            if query_lexnames:
                # Obtener IDs de los grupos del query
                placeholders_ln = ",".join("?" * len(query_lexnames))
                self.cursor.execute(
                    f"SELECT id FROM grupos_semanticos WHERE nombre IN ({placeholders_ln})",
                    tuple(query_lexnames)
                )
                query_grupo_ids = set(r[0] for r in self.cursor.fetchall())

                if query_grupo_ids:
                    conceptos_todos = [r[1] for r in todos if r[1]]
                    if conceptos_todos:
                        ph_conceptos = ",".join("?" * len(conceptos_todos))
                        ph_grupos = ",".join(str(g) for g in query_grupo_ids)
                        self.cursor.execute(
                            f"SELECT concepto, grupo_id FROM nodo_grupos_semanticos "
                            f"WHERE concepto IN ({ph_conceptos}) "
                            f"AND grupo_id IN ({ph_grupos})",
                            tuple(conceptos_todos)
                        )
                        # Coseno binario: shared / sqrt(|query| × |doc|)
                        import math
                        concepto_grupo_ids = {}
                        for concepto, gid in self.cursor.fetchall():
                            concepto_grupo_ids.setdefault(concepto, set()).add(gid)

                        q_len = len(query_grupo_ids)
                        for concepto, doc_gids in concepto_grupo_ids.items():
                            shared = len(query_grupo_ids & doc_gids)
                            if shared > 0:
                                grupo_scores_map[concepto] = shared / math.sqrt(
                                    q_len * len(doc_gids)
                                )
        except ImportError:
            pass  # WordNet no disponible

    # SRL v16.0: Filtrar todos los candidatos por roles semánticos si se especificó buscar_por_rol
    if conceptos_validos_rol is not None:
        todos = [r for r in todos if r[1].lower().strip() in conceptos_validos_rol]

    # Batch fetch synonyms for all retrieved candidates before the final scoring loop
    conceptos_todos = [r[1] for r in todos if r[1]]
    concepto_sinonimos_map = {}
    if conceptos_todos:
        placeholders = ",".join(["?" for _ in conceptos_todos])
        try:
            self.cursor.execute(
                f"SELECT concepto, sinonimos FROM largo_plazo WHERE concepto IN ({placeholders})",
                conceptos_todos
            )
            for conc, sinonimos in self.cursor.fetchall():
                concepto_sinonimos_map[conc] = sinonimos or ""
        except Exception:
            pass

    # Prepare normalized query tokens for symbolic scoring
    from core.fallback_simbolico import _tokenizar_normalizado, score_simbolico_concepto, score_simbolico_sinonimos
    tokens_query = _tokenizar_normalizado(query)

    # ── Precompute PPMI Query Vector ONCE before candidate loop ──
    _ppmi_vq = None
    _ppmi_q_set = set(tokens_query) if tokens_query else set()
    _ppmi_es_corta = len(_ppmi_q_set) <= 2
    _ppmi_pool_set = {r[1] for r in todos}
    if constants.PPMI_VECTOR_WEIGHT > 0.0 and self._ppmi_index and tokens_query:
        try:
            _ppmi_vq = self._ppmi_index.vector_query(list(tokens_query))
        except Exception:
            _ppmi_vq = None

    # v22.1: Pre-compute thematic profiles and lazy-cache pairwise scores
    # On-demand calculation per candidate pair (O(K^2) for K=50 top candidates instead of O(N^2) for N=800 all nodes)
    _perfiles_tematicos = {}
    _idf_tematico = {}
    _todas_dims = None
    try:
        from core.tematica import calcular_perfiles_presencia, calcular_idf_dims, similitud_tematica
        if self._thematic_profiles_cache is not None:
            _perfiles_tematicos = self._thematic_profiles_cache
            _idf_tematico = self._thematic_idf_cache
        else:
            _perfiles_tematicos = calcular_perfiles_presencia(self)
            _idf_tematico = calcular_idf_dims(self)
            self._thematic_profiles_cache = _perfiles_tematicos
            self._thematic_idf_cache = _idf_tematico
            self._thematic_scores_cache = {}
        if self._thematic_scores_cache is None:
            self._thematic_scores_cache = {}
        _todas_dims = set(_idf_tematico.keys())
    except Exception:
        pass

    # ─── Precompute Spreading Activation (cadena) scores from top seeds ───
    cadena_scores_map = {}
    if not modo_estricto and todos:
        try:
            semillas_top = [r[1] for r in todos[:5] if r[1]]
            if semillas_top:
                evocados, _ = self._evocacion_por_cadena(semillas_top)
                for conc_ev, decay_score, _ in evocados:
                    cadena_scores_map[conc_ev] = max(cadena_scores_map.get(conc_ev, 0.0), decay_score)
        except Exception:
            pass

    # E6: NCD zlib O(k) sobre el pool (query vs concepto+contenido).
    ncd_map = {}
    if constants.NCD_PESO > 0.0 and todos:
        try:
            ncd_map = self._ncd_sims_pool(
                query,
                [(r[1], r[2]) for r in todos if r[1]],
            )
        except Exception:
            ncd_map = {}

    # E7: JSD adaptativo una vez por query (Nt tokens >=3).
    _jsd_w_e7 = self._jsd_weight_adaptativo(query)

    episodio_map = {}
    if constants.EPISODIO_TEMPORAL_PESO > 0.0 and todos:
        try:
            episodio_map = self._afinidad_temporal_pool([r[1] for r in todos if r[1]])
        except Exception:
            episodio_map = {}

    # F3: analogia relacional. Con flags 0 ni regex ni coseno (byte-identico).
    analogia_map = {}
    if (analogia or constants.ANALOGIA_DETECTAR) and constants.ANALOGIA_PESO > 0.0 and todos:
        try:
            from core.ppmi_hybrid_search import detectar_analogia, _vec_concepto
            _abc = detectar_analogia(query)
            if _abc and self._ppmi_index is not None:
                _vecs = self._ppmi_index.vecs or {}
                _va = _vec_concepto(_vecs, _abc[0])
                _vb = _vec_concepto(_vecs, _abc[1])
                _vc = _vec_concepto(_vecs, _abc[2])
                if _va is not None and _vb is not None and _vc is not None:
                    import numpy as _np
                    _vt = _np.asarray(_vc, dtype="float64") + (
                        _np.asarray(_vb, dtype="float64") - _np.asarray(_va, dtype="float64")
                    )
                    analogia_map = self._analogia_scores_pool(
                        _vt, [r[1] for r in todos if r[1]]
                    )
        except Exception:
            analogia_map = {}

    # F5: campo semantico. Peso 0 -> dict vacio, ni gauss ni matmul.
    campo_map = {}
    if constants.CAMPO_POTENCIAL_PESO > 0.0 and todos and _ppmi_vq is not None:
        try:
            from core.ppmi_hybrid_search import calcular_campo_potencial_ppmi
            _pool_c = [r[1] for r in todos if r[1]][:constants.CAMPO_K if constants.CAMPO_K > 0 else 0]
            if _pool_c:
                campo_map = calcular_campo_potencial_ppmi(
                    self, _ppmi_vq, _pool_c, sigma=constants.CAMPO_SIGMA
                )
        except Exception:
            campo_map = {}

    # Calcular score hibrido para cada resultado (fórmula única 9 señales)
    total = len(todos)
    resultados_con_hibrido = []
    for _, (rowid, concepto, contenido, peso, estado, asociaciones) in enumerate(todos):
        origen, score_capa = origen_scores.get(concepto, ("literal", 0.0))
        dim_score = dim_scores_map.get(concepto, 0.0)
        _q_norm = query.lower().replace(" ", "_").replace("-", "_")
        _c_norm = (concepto or "").lower().replace(" ", "_").replace("-", "_")
        match_exacto = (_q_norm == _c_norm) or (bool(tokens_query) and tokens_query == _tokenizar_normalizado(concepto))
        # v22.1: Content-expanded nodes get a boost (they matched on content, not just FTS)
        score_latente = score_capa if origen in ("latente", "expansion", "contenido") else 0.0
        # v16.0: Boost por inferencia transitiva (sinapsis latentes)
        if usar_inferencia:
            try:
                self.cursor.execute("""
                    SELECT MAX(peso_atenuado) FROM sinapsis_latentes
                    WHERE (origen = ? OR destino = ?)
                """, (concepto, concepto))
                row_lat = self.cursor.fetchone()
                if row_lat and row_lat[0] and row_lat[0] > score_latente:
                    score_latente = max(score_latente, row_lat[0])
            except Exception:
                pass
        score_cadena = max(score_capa if origen == "cadena" else 0.0, cadena_scores_map.get(concepto, 0.0))

        # Calculate symbolic similarity for concept name and synonyms, and update ratios
        concepto_s_score = score_simbolico_concepto(tokens_query, concepto)
        concepto_ratio = max(resultados_concepto.get(concepto, 0.0), concepto_s_score)

        sinonimos_str = concepto_sinonimos_map.get(concepto, "")
        sinonimos_s_score = score_simbolico_sinonimos(tokens_query, sinonimos_str)
        sinonimos_ratio = max(resultados_semantica.get(concepto, 0.0), sinonimos_s_score)

        # Fix Grupo C v2 (2026-08-13): el piso de sinónimos (memory_store.py:3170,
        # sinonimos_ratio >= 0.95) no disparaba cuando la query es 100% stopword
        # (ej. "buscar") — score_simbolico_sinonimos recibe tokens_query vacío
        # (fallback_simbolico.py:47 elimina stopwords) y devuelve 0.0, y Capa 4
        # (memory_store.py:4066, condición `if conc not in todos`) nunca llena
        # resultados_semantica para nodos que entraron por otra capa (ej. FTS
        # literal). Resultado: sinonimos_ratio = max(0,0) = 0 aunque la palabra SÍ
        # esté en el campo sinonimos del nodo. Fix v2 RESTRICTIVO: el substring
        # solo aplica cuando tokens_query está vacío (query 100% stopword). Fue
        # necesario restringirlo tras medir que la versión amplia (criterio
        # substring para toda query) elevaba nodos ruidosos al piso y regresaba
        # los casos 0532 y 0781 del benchmark. Con esta condición, "boost" y
        # "falso positivo" (con tokens reales) no se ven afectados, y solo se
        # rescata el caso exacto del bug: query sin tokens simbólicos cuyo
        # sinónimo está en el campo sinonimos del nodo, mismo criterio LIKE de
        # Capa 4 (memory_store.py:4067).
        sinonimos_substring = 0.0
        if not tokens_query and sinonimos_str and palabras_like:
            sinonimos_substring = sum(
                1 for w in palabras_like if w.lower() in sinonimos_str.lower()
            ) / len(palabras_like)
        sinonimos_ratio = max(sinonimos_ratio, sinonimos_substring)

        # v22.1: Compute thematic score (presence + absence of dimensions)
        # On-demand pairwise calculation over top-15 candidates with memoization (O(1) cached)
        # Fix: per-candidate gate — tematico_score solo si hay evidencia léxica real
        # (bm25 > 0.001 o concepto_ratio > 0.001) Y no hay señal fuerte de sinónimo
        tematico_score = 0.0
        bm25_val = bm25_norm_map.get(concepto, 0.0)
        if _perfiles_tematicos and _todas_dims and (bm25_val > 0.001 or concepto_ratio > 0.001) and sinonimos_ratio < 0.5:
            sims = []
            for _, (other_concepto, _, _, _, _, _) in enumerate(todos[:15]):
                if other_concepto != concepto and concepto and other_concepto:
                    c1, c2 = str(concepto), str(other_concepto)
                    pair_key = (c1, c2) if c1 <= c2 else (c2, c1)
                    if pair_key not in self._thematic_scores_cache:
                        s = similitud_tematica(concepto, other_concepto, self, _perfiles_tematicos, _idf_tematico)
                        self._thematic_scores_cache[pair_key] = s
                    else:
                        s = self._thematic_scores_cache[pair_key]
                    if s > 0.02:  # umbral estable
                        sims.append(s)
            if sims:
                tematico_score = min(1.0, sum(sims) / len(sims) * 3.0)  # multiplicador óptimo 3.0

        # Signal #11: Jensen-Shannon Divergence (distributional overlap)
        jsd_val = 0.0
        if _jsd_w_e7 > 0.0:
            node_text = f"{concepto} {contenido or ''}"
            jsd_val = self._calcular_jsd(query, node_text)

        # Signal #12: Predicate matching (query tokens vs predicate keywords)
        # ⚠️ CANIBALIZACIÓN DEMOSTRADA 2026-08-04: si se re-corre el backfill de
        # predicados (scripts/backfill_predicados.py), re-verificar contra el
        # re-ranking jaccard (Fase C). El backfill restaura recuperación perdida
        # pero canibaliza la señal #12 con jaccard activo. Capacidad disponible,
        # NO enganchada. Ver nodo biorag: backfill_predicados_restaura_parcial_no_84_62_y_canibaliza_con_jaccard.
        pred_val = 0.0
        pred_tokens = pred_contexto_map.get(concepto, set())
        if pred_tokens and tokens_query:
            matches = sum(1 for t in tokens_query if t in pred_tokens)
            pred_val = min(1.0, matches / max(1, len(tokens_query)))

        # Signal #13: PPMI+SVD vector similarity (v26.0)
        # ON por defecto (constants.PPMI_VECTOR_WEIGHT=0.15). Apagar con: export BIORAG_PPMI_WEIGHT=0.0
        ppmi_val = 0.0
        if _ppmi_vq is not None:
            try:
                from core.ppmi_hybrid_search import score_candidato
                q_toks_list = list(tokens_query)
                q_set = set(q_toks_list)
                es_corta = len(q_set) <= 2
                pool_set = {r[1] for r in todos}
                vq = self._ppmi_index.vector_query(q_toks_list)
                _raw_ppmi, _ = score_candidato(self._ppmi_index, vq, q_set, es_corta, concepto, pool_set)
                # Normalizar: el score bruto de score_candidato ronda 0-2 para query corta (dividir por 2.0), 0-1 para larga
                ppmi_val = min(1.0, max(0.0, _raw_ppmi / (2.0 if es_corta else 1.0)))

            except Exception:
                ppmi_val = 0.0

        # Signal #14: Concept Hub match
        hub_val = 0.0
        if hub_expansion:
            canonical_nodes = hub_expansion.get("canonical_nodes", [])
            hub_conf = hub_expansion.get("hub_confidence", 0.0)
            if concepto in canonical_nodes:
                # Nodo canónico: boost fuerte (garantiza aparición en TOP)
                hub_val = min(1.0, hub_conf * 2.0)
            elif any(concepto in cn for cn in canonical_nodes):
                # Nodo vinculado al hub: boost medio
                hub_val = min(0.8, hub_conf * 1.5)
            else:
                # Nodo no relacionado: sin boost
                hub_val = 0.0

        score_hibrido = self._calcular_score_hibrido(
            bm25_norm=bm25_norm_map.get(concepto, 0.0),
            dim_score=dim_score,
            peso_sinaptico=0.0 if ignore_peso_sinaptico else peso,
            concepto_ratio=concepto_ratio,
            sinonimos_ratio=sinonimos_ratio,
            score_latente=score_latente,
            score_cadena=score_cadena,
            asoc_count=len([v for v in (asociaciones or "").split(",") if v.strip()]),
            match_exacto=match_exacto,
            grupo_score=grupo_scores_map.get(concepto, 0.0),
            tematico_score=tematico_score,
            jsd_score=jsd_val,
            jsd_weight=_jsd_w_e7,
            pred_score=pred_val,
            ppmi_score=ppmi_val,
            hub_match=hub_val,
            ncd_score=ncd_map.get(concepto, 0.0),
            episodio_score=episodio_map.get(concepto, 0.0),
            analogia_score=analogia_map.get(concepto, 0.0),
            campo_score=campo_map.get(concepto, 0.0),
        )

        resultados_con_hibrido.append(
            (concepto, contenido, peso, estado, score_hibrido, asociaciones or "")
        )

    # Reordenar por score hibrido descendente
    resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)

    # Promoción de candidatos generados por episodio léxico explícito.
    # POR QUÉ: el gold entra al pool (generación) pero el ranker híbrido no
    # conoce la enseñanza. No es un ranker genérico (EXP-N9); es el contrato
    # de «A significa B» con evidencia explicit/consolidated.
    if resultados_con_hibrido:
        _prom = []
        for conc, cont, peso, est, sc, asoc in resultados_con_hibrido:
            orig, conf_l = origen_scores.get(conc, ("", 0.0))
            if orig == "lexico_aprendido":
                sc = max(sc, min(0.99, 0.88 + 0.10 * float(conf_l or 0.0)))
            _prom.append((conc, cont, peso, est, sc, asoc))
        resultados_con_hibrido = _prom
        resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)

    # v26.2: Puerta QCR (Query Coverage Ratio) para consultas compuestas (>= 2 palabras)
    # Exige que al menos el 50% de los tokens de la consulta coincidan en el nodo/sinónimos/metadatos
    # para prevenir que 1 sola palabra accidental en textos largos genere Falsos Positivos.
    # Desactivable con export BIORAG_QCR_ACTIVO=0
    QCR_ACTIVO = os.getenv("BIORAG_QCR_ACTIVO", "1") == "1"
    # v26.4: El escape de capa ya no es binario — exige score_capa >= umbral (0.60).
    # Motivo: los orígenes semantica/dimensional_fallback sin piso generaban FPs (ratio bajo,
    # capa 0.25-0.33). Los orígenes simbolico nacen con capa >= 0.60 por construcción (fallback
    # simbolico umbral=0.60), así que este umbral preserva los rescates de typo/variante.
    # Costo residual conocido y documentado: 2 FP (capa 0.667/1.0) aceptados tras análisis
    # 921 casos (2026-08-11) — no existe señal (tokens ni capa) que los separe de los TP.
    QCR_ESCAPE_CAPA_MIN = float(os.getenv("BIORAG_QCR_ESCAPE_CAPA_MIN", "0.60"))
    # Concept Hub: nodos canónicos bypass QCR cuando el hub tiene alta confianza
    hub_canonical_set = set()
    if hub_expansion and hub_expansion.get("hub_confidence", 0) >= 0.4:
        hub_canonical_set = set(hub_expansion.get("canonical_nodes", []))
    q_tokens_qcr = [t.lower() for t in re.findall(r'\w{3,}', query)]
    _qcr_idf_map = {}
    if QCR_ACTIVO and constants.QCR_IDF_ACTIVO and q_tokens_qcr:
        try:
            _qcr_idf_map = self._idf_tokens_qcr(q_tokens_qcr)
        except Exception:
            _qcr_idf_map = {}
    _qcr_umbral = constants.QCR_IDF_UMBRAL if (constants.QCR_IDF_ACTIVO and _qcr_idf_map) else 0.50
    if QCR_ACTIVO and len(q_tokens_qcr) >= 2 and resultados_con_hibrido:
        filtrados_qcr = []
        _idf_den = sum(_qcr_idf_map.get(t, 1.0) for t in q_tokens_qcr) if _qcr_idf_map else float(len(q_tokens_qcr))
        for conc, cont, peso, est, sc, asoc in resultados_con_hibrido:
            # Bypass QCR para nodos canónicos del hub
            if conc in hub_canonical_set:
                filtrados_qcr.append((conc, cont, peso, est, sc, asoc))
                continue
            text_target = f"{conc} {cont} {concepto_sinonimos_map.get(conc, '')}".lower()
            if _qcr_idf_map:
                _num = sum(_qcr_idf_map.get(t, 1.0) for t in q_tokens_qcr if t in text_target)
                ratio_qcr = (_num / _idf_den) if _idf_den > 0 else 0.0
            else:
                matches_qcr = sum(1 for t in q_tokens_qcr if t in text_target)
                ratio_qcr = matches_qcr / len(q_tokens_qcr)
            origen_tipo, score_capa = origen_scores.get(conc, ("literal", 0.0))
            if ratio_qcr >= _qcr_umbral or (
                origen_tipo in (
                    "semantica", "simbolico", "expansion", "dimensional_fallback",
                    "typo", "concepto", "lexico_aprendido",
                )
                and score_capa >= QCR_ESCAPE_CAPA_MIN
            ) or (
                # Fase B (resonancia dimensional): escape calibrado T=0.45
                # (40 neg max 0.0; Q-01 0.488). OFF = cortocircuito.
                constants.DIM_ESCAPE and origen_tipo == "dimensional_fallback"
                and score_capa >= constants.DIM_ESCAPE_T
            ):
                filtrados_qcr.append((conc, cont, peso, est, sc, asoc))
            elif (constants.QCR_TYPO_ACTIVA and sc >= constants.QCR_TYPO_PISO
                    and constants._qcr_todos_cercanos(q_tokens_qcr, text_target, constants.QCR_TYPO_DIST)):
                # F-QCR-D4: segunda oportunidad por typos (ver flags). Flag OFF:
                # cortocircuito, path byte-identico.
                filtrados_qcr.append((conc, cont, peso, est, sc, asoc))
        if filtrados_qcr:
            resultados_con_hibrido = filtrados_qcr

    # ── CONCEPT HUB: Post-procesamiento — promoción competitiva del nodo canónico ──
    # El canónico compite contra el mejor candidato léxico en vez de forzarse
    # incondicionalmente a TOP1. Esto evita que un Hub falso positivo (confianza
    # mínima 0.40 → score 0.38) desplace un match léxico perfecto (score 0.80).
    #
    # Regla:
    #   hub_gana = score_forzado >= mejor_score_lexico
    #   → True:  canónico va a TOP1 (semántica supera léxico)
    #   → False: canónico se inserta en su posición natural por score
    #             (presencia garantizada, no TOP1 garantizado)
    #
    # Para matches de alta confianza (1.0 → score 0.95) el hub siempre gana
    # porque el scoring híbrido máximo real es ~0.948 (TEST 3, invariante scoring).
    # Para matches de baja confianza (0.40 → score 0.38) el léxico gana si hay
    # cualquier candidato decente, que es el comportamiento correcto.
    if hub_expansion and hub_expansion.get("hub_confidence", 0) >= 0.4:
        primary_canonical = hub_expansion.get("canonical_nodes", [None])[0]
        if primary_canonical:
            score_forzado = min(0.95, hub_expansion["hub_confidence"] * 0.95)
            mejor_score_lexico = resultados_con_hibrido[0][4] if resultados_con_hibrido else 0.0
            hub_gana = score_forzado >= mejor_score_lexico

            # v30.1 — PISO DE PROMOCIÓN (fix de orden no monotónico).
            # Antes: cuando el hub ganaba se hacía insert(0, ...) con score_forzado,
            # que puede ser MENOR que el mejor score léxico (ej. confianza 0.467 →
            # 0.444 colocado encima de un léxico de 0.513). El resultado devuelto
            # quedaba con scores no ordenados descendente, rompiendo el contrato de
            # buscar_por_frase para todo consumidor que corte por score en vez de por
            # posición (mcp_server.py reordena los pools frase/ráfaga por r[4]).
            # Ahora: la promoción se expresa EN EL SCORE. Si el canónico va a TOP1,
            # su score se eleva al mejor léxico + 1 tick (0.0001, la resolución de
            # round(...,4)), así posición y score dicen lo mismo y el orden sobrevive
            # a cualquier re-sort posterior. La semántica de promoción no cambia: el
            # canónico sigue yendo a TOP1 cuando hub_gana.
            score_promocion = (
                round(min(1.0, max(score_forzado, mejor_score_lexico + 0.0001)), 4)
                if hub_gana else score_forzado
            )

            ya_existe = any(r[0] == primary_canonical for r in resultados_con_hibrido)
            if not ya_existe:
                # Canónico ausente → traer desde DB
                try:
                    self.cursor.execute(
                        "SELECT concepto, contenido, peso_sinaptico, estado, asociaciones "
                        "FROM largo_plazo WHERE concepto = ? AND estado = 'activo'",
                        (primary_canonical,)
                    )
                    row = self.cursor.fetchone()
                    if row:
                        entrada = (row[0], row[1], row[2], row[3], score_promocion, row[4] or "")
                        if hub_gana:
                            # Hub supera al mejor léxico → TOP1
                            resultados_con_hibrido.insert(0, entrada)
                            origen_scores[primary_canonical] = ("concept_hub", hub_expansion["hub_confidence"])
                        else:
                            # Léxico supera al hub → insertar en posición que
                            # preserve orden por score (presencia garantizada)
                            pos = next(
                                (i for i, r in enumerate(resultados_con_hibrido) if r[4] < score_promocion),
                                len(resultados_con_hibrido)
                            )
                            resultados_con_hibrido.insert(pos, entrada)
                            origen_scores[primary_canonical] = ("concept_hub", hub_expansion["hub_confidence"])
                except Exception as exc:
                    logger.warning(f"[BioRAG.ConceptHub] Error recuperando canónico '{primary_canonical}' de DB: {exc}")
            else:
                # Canónico ya existe en resultados
                idx = next(i for i, r in enumerate(resultados_con_hibrido) if r[0] == primary_canonical)
                if hub_gana:
                    if idx > 0:
                        # Hub supera al mejor léxico → mover a TOP1
                        nodo = resultados_con_hibrido.pop(idx)
                        nodo_mod = list(nodo)
                        nodo_mod[4] = score_promocion
                        resultados_con_hibrido.insert(0, tuple(nodo_mod))
                    origen_scores[primary_canonical] = ("concept_hub", hub_expansion["hub_confidence"])
                    # Si no hub_gana: el canónico ya está en su posición natural,
                    # no lo movemos — el léxico merece el TOP1

    # Fase C (v22.2): Re-ranking jaccard léxico condicional.
    # OFF por defecto (BIORAG_RERANKING_JACCARD_ENABLED=0) — activación gradual
    # monitoreada contra el benchmark. Config ganadora del holdout 2026-08-04.
    if constants.RERANKING_JACCARD_ACTIVO:
        resultados_con_hibrido = self._rerank_jaccard_protect_r0(
            resultados_con_hibrido, frase_limpia, preview_chars=preview_chars
        )

    # v20.0 Inhibición Lateral GABA en Tiempo Real (Edelman 1987)
    # Si el candidato Top-1 es un atractor fuerte (score >= 0.80),
    # atenúa activamente a los competidores secundarios del mismo nicho (x0.60)
    # Ablación: export BIORAG_GABA_ACTIVO=0
    if constants.GABA_ACTIVO and resultados_con_hibrido and resultados_con_hibrido[0][4] >= 0.80:
        top_score = resultados_con_hibrido[0][4]
        gaba_resultados = [resultados_con_hibrido[0]]
        for conc, cont, peso, est, sc, asoc in resultados_con_hibrido[1:]:
            if sc < top_score * 0.70:
                sc = round(sc * 0.60, 4)
            gaba_resultados.append((conc, cont, peso, est, sc, asoc))
        gaba_resultados.sort(key=lambda r: r[4], reverse=True)
        resultados_con_hibrido = gaba_resultados

    # Filtro final con PALABRA_PREFIJO: para queries de una palabra,
    # exigir que aparezca como prefijo de palabra en contenido (del lado de la DB).
    # Esto permite "react" -> "reactive" mientras sigue bloqueando falsos positivos de substring
    # ("culo" no es prefijo de "artículos").
    # Solo aplica a resultados de capas literales (AND/OR/NEAR/unicode/snap/substring).
    # Resultados de capas no literales se preservan para no romper tolerancia a typos,
    # búsqueda semántica/conceptual, ni el fallback simbólico (que normaliza acentos).
    # RF-19 (spec 001): incluye la columna sustantivos_clave — un nodo boosteado por esa
    # columna dedicada (match en FTS con peso BM25 4.0x) no debe ser descartado aquí por no
    # ser prefijo del contenido/concepto/sinónimos.
    _ORIGENES_NO_LITERALES = {"typo", "expansion", "latente", "cadena", "simbolico", "dimensional_fallback", "semantica", "unicode", "lexico_aprendido", "sdm"}
    query_words = re.findall(r'\w{3,}', query.lower())
    if len(query_words) == 1 and resultados_con_hibrido:
        token = query_words[0]
        literal_results = [
            r for r in resultados_con_hibrido
            if origen_scores.get(r[0], ("literal", 0.0))[0] not in _ORIGENES_NO_LITERALES
        ]
        non_literal_results = [r for r in resultados_con_hibrido if r not in literal_results]
        if literal_results:
            conceptos_literal = [r[0] for r in literal_results if r[0] is not None]
            placeholders = ",".join("?" * len(conceptos_literal))
            self.cursor.execute(
                f"SELECT concepto FROM largo_plazo WHERE "
                f"(PALABRA_PREFIJO(?, concepto) = 1 OR PALABRA_PREFIJO(?, contenido) = 1 OR PALABRA_PREFIJO(?, COALESCE(sinonimos, '')) = 1 "
                f"OR PALABRA_PREFIJO(?, COALESCE(sustantivos_clave, '')) = 1) "
                f"AND concepto IN ({placeholders})",
                (token, token, token, token) + tuple(conceptos_literal)
            )
            validos = {row[0] for row in self.cursor.fetchall()}
            resultados_con_hibrido = [r for r in literal_results if r[0] in validos] + non_literal_results

    # ── v30.1: GUARDIA DE ORDEN MONOTÓNICO (antes de paginar) ──────────
    # Los post-procesos (promoción del Concept Hub, filtro PALABRA_PREFIJO de una
    # palabra, re-ranking jaccard) reconstruyen la lista por posición, no por score.
    # El filtro PALABRA_PREFIJO concatenaba `literales_validos + no_literales` sin
    # reordenar, y cada bloque conservaba el orden previo: de ahí salían resultados
    # con scores NO descendentes (9 casos en casos_fallidos.jsonl del 2026-09-02,
    # ej. 'perfil' → [0.7562, 0.6780, 0.7523]).
    #
    # Un ranking que no está ordenado por el score que él mismo reporta rompe a todo
    # consumidor que corte por score en vez de por posición (mcp_server.py combina y
    # reordena los pools de buscar_por_frase y buscar_por_rafaga por r[4], así que
    # frase y ráfaga podían devolver órdenes distintos para la misma consulta).
    #
    # Este re-sort es la última palabra sobre relevancia: solo aplica cuando
    # ordenar_por == "relevancia" (el bloque siguiente de recencia/antiguedad
    # reordena a propósito por fecha y debe respetarse). O(n log n) sobre el pool ya
    # filtrado, sin coste medible. Desactivable: export BIORAG_ORDEN_MONOTONICO=0
    if (
        ordenar_por == "relevancia"
        and resultados_con_hibrido
        and os.getenv("BIORAG_ORDEN_MONOTONICO", "1") == "1"
    ):
        resultados_con_hibrido.sort(key=lambda r: r[4], reverse=True)

    # ── Ordenamiento post-hoc por fecha (antes de paginar) ──────────
    # Solo responde intención temporal: "qué pasó hace X", "cuál fue lo último".
    # NO reemplaza relevancia — reordena el conjunto ya filtrado por relevancia.
    if ordenar_por in ("recencia", "antiguedad") and resultados_con_hibrido:
        conceptos_todo = [r[0] for r in resultados_con_hibrido]
        ph_todo = ",".join("?" * len(conceptos_todo))
        try:
            self.cursor.execute(
                f"SELECT concepto, creado_en FROM largo_plazo WHERE concepto IN ({ph_todo})",
                tuple(conceptos_todo),
            )
            creado_map = {row[0]: row[1] or 0 for row in self.cursor.fetchall()}
        except Exception:
            creado_map = {}
        reverse = (ordenar_por == "recencia")
        resultados_con_hibrido.sort(
            key=lambda r: creado_map.get(r[0], 0),
            reverse=reverse,
        )

    # Dynamic Multiplicator (opt-in): ampliación por empate en el corte,
    # solo para queries cortas (≤2 palabras). Evidencia real (EXPERIMENTS.md,
    # 18-ago-2026): para queries de una palabra, el concepto correcto a veces
    # cae justo debajo de `limite` compitiendo con candidatos igual de plausibles.
    # Solo se activa con permitir_expansion_empate=True — por defecto, limite es
    # un contrato estricto que el motor no rompe.
    if permitir_expansion_empate:
        query_words_ambiguedad = re.findall(r"\w+", frase.lower())
        if (pagina == 1 and limite and len(query_words_ambiguedad) <= 2
                and len(resultados_con_hibrido) > limite):
            score_corte = resultados_con_hibrido[limite - 1][4]
            tope = min(limite + 10, len(resultados_con_hibrido))
            limite_ampliado = limite
            for idx in range(limite, tope):
                if resultados_con_hibrido[idx][4] >= score_corte * 0.90:
                    limite_ampliado = idx + 1
                else:
                    break
            limite = limite_ampliado

    # Paginar (sin truncar aun; se necesita contenido completo para context window)
    inicio = (pagina - 1) * limite
    pagina_resultados = resultados_con_hibrido[inicio:inicio + limite]

    if profundidad == "profundo":
        pagina_resultados_actualizada = []
        for r in pagina_resultados:
            if r[3] == "dormido":
                nuevo_peso = min(1.0, r[2] + 0.15)
                self.cursor.execute(
                    "UPDATE largo_plazo SET estado = 'activo', peso_sinaptico = ?, ultimo_acceso = ? WHERE concepto = ?",
                    (nuevo_peso, time.time(), r[0]),
                )
                score_nuevo = round(min(1.0, r[4] + 0.10 * (nuevo_peso - r[2])), 4)
                pagina_resultados_actualizada.append(
                    (r[0], r[1], nuevo_peso, "activo", score_nuevo, r[5])
                )
            else:
                pagina_resultados_actualizada.append(r)
        pagina_resultados = pagina_resultados_actualizada
        self.conn.commit()
        if ordenar_por == "relevancia":
            pagina_resultados.sort(key=lambda r: r[4], reverse=True)

    # Context window: expandir cada resultado con vecinos por sinapsis
    if context_window and context_window > 0 and pagina_resultados:
        primarios_ctx, vecinos_ctx = self.expandir_contexto_vecinos(
            pagina_resultados,
            depth=context_window,
            profundidad=profundidad,
            preview_chars=preview_chars
        )
        pagina_resultados = primarios_ctx + vecinos_ctx

    # Truncar preview a nivel de motor (ahorra RAM en CLI/MCP)
    if preview_chars and preview_chars > 0:
        pagina_resultados = [
            (r[0], (r[1] or "")[:preview_chars] + ("..." if len(r[1] or "") > preview_chars else ""), r[2], r[3], r[4], r[5])
            for r in pagina_resultados
        ]

    # Búsqueda iterativa: si no hay resultados y hay historial, generar variaciones
    if not pagina_resultados and historial_fallos is not None:
        variaciones = self._generar_variaciones(query, historial_fallos)
        for var in variaciones:
            resultados_var, total_var = self.buscar_por_frase(
                var, profundidad, pagina, limite, categoria, preview_chars,
                historial_fallos=None, context_window=context_window
            )
            if resultados_var:
                return resultados_var, total_var

    # Fallback Causal SRL: únicamente si la búsqueda tradicional por 8 señales devolvió 0 resultados Y no hay filtro estricto de rol
    if not pagina_resultados and not buscar_por_rol:
        res_srl = self._fallback_busqueda_predicados(query, limite=limite)
        if res_srl:
            pagina_resultados = res_srl
            total = len(res_srl)

    # Guardar trazabilidad para mcp_server.py y auditoría causal
    self.last_todos = todos
    self.last_origen_scores = origen_scores
    self.last_query = query
    self.last_hub_expansion = hub_expansion

    _exp_ep = expandir_episodio or constants.EPISODIO_TEMPORAL_ACTIVO
    if _exp_ep and pagina_resultados:
        try:
            _ancla = pagina_resultados[0][0]
            _eps = self._expandir_episodio_temporal(_ancla)
            _seen = {r[0] for r in pagina_resultados}
            for hit in _eps:
                if hit["concepto"] in _seen:
                    continue
                sc = min(0.45, float(pagina_resultados[0][4] or 0.0) * 0.85)
                pagina_resultados.append((
                    hit["concepto"], hit["contenido"], hit["peso"],
                    hit["estado"], sc, hit["asociaciones"],
                ))
                _seen.add(hit["concepto"])
                origen_scores[hit["concepto"]] = ("episodio_temporal", 1.0)
            total = max(total, len(pagina_resultados))
        except Exception:
            pass

    # Signal #14 (v29): Enriquecer candidatos con ADN Conceptual bajo flag.
    # Flag OFF por defecto → esta rama no altera la ruta del baseline.
    # Con flag ON aplica el contrato de degradación asociativa (§3 del plan):
    # nunca silencio vacío, etiqueta directo/asociativo, sin barridos globales.
    if constants.ADN_RANKING_ENABLED and pagina_resultados:
        pagina_resultados, metadatos_epi = self._enriquecer_con_adn(query, pagina_resultados, limite)
        self.last_estado_epistemico = metadatos_epi
        total = len(pagina_resultados)

    # =====================================================================
    # TECNOLOGÍA COGNITIVA: Registro de Acceso ACT-R (Anderson & Lebiere, 1998)
    # Alimenta el cálculo de Base-Level Activation para la Ley de Potencia.
    # Solo opera fuera del entorno de benchmarking o telemetría silenciada.
    # =====================================================================
    if pagina_resultados and os.environ.get("BIORAG_NO_LOG") != "1":
        try:
            ahora_acc = time.time()
            for r in pagina_resultados:
                if r and r[0]:
                    self._registrar_acceso_nodo(r[0], ahora_acc)
        except Exception:
            pass

    # Phase 2D: Telemetría de búsquedas (non-blocking)
    # Respeta BIORAG_NO_LOG=1 para no contaminar el log con consultas de test/benchmark
    if os.environ.get("BIORAG_NO_LOG") == "1":
        self.last_log_id = None
    else:
        try:
            top_score = pagina_resultados[0][4] if pagina_resultados else None
            # Guardar top-5 conceptos para atribución de feedback (ver
            # docs/FIX_FEEDBACK_NO_ALCANZABLE.md): permite unir feedback por
            # concepto a la búsqueda que lo recuperó, sin depender de estado
            # en memoria (que no sobrevive entre llamadas MCP).
            conceptos_top = None
            if pagina_resultados:
                top_conceptos = [r[0] for r in pagina_resultados[:5]]
                conceptos_top = ",".join(top_conceptos)
            self.cursor.execute(
                "INSERT INTO log_busquedas (query, resultados_count, top_score, creado_en, conceptos_top) VALUES (?, ?, ?, ?, ?)",
                (query, total, top_score, time.time(), conceptos_top),
            )
            self.last_log_id = self.cursor.lastrowid
            self.conn.commit()
        except Exception:
            self.last_log_id = None
            pass

    # SIN UMBRAL en buscar_por_frase.
    #
    # POR QUÉ: el umbral conforme se calibra sobre scores de consultas
    # negativas y filtra por CALIDAD (¿respondo o abstengo?). Aplicarlo
    # aquí destruye R@5 (medido: 96% → 73%) porque muchos nodos válidos
    # tienen score < umbral por la arquitectura del scoring.
    #
    # DÓNDE SÍ se aplica: MCP path (_recordar_impl en mcp_server.py),
    # que es el punto de decisión "¿respondo al usuario?".
    #
    # buscar_por_frase es motor de búsqueda puro: devuelve todo lo que
    # encuentre, sin filtro de calidad. El consumidor decide.
    # OPT-NUEVA-5: solo publica metadatos (side-channel); ranking intacto.
    if constants.EPISTEMICO_METADATA:
        self._epistemico_publicar(frase, pagina_resultados, total)
    self.last_pagina_resultados = pagina_resultados
    return pagina_resultados, total


def _generar_variaciones(self, query, historial_fallos=None):
    """Genera variaciones de la query basadas en el historial de fallos.

    Si "angular formularios" falló, probar:
    - Solo "angular" (más específico)
    - "angular" + sinónimos
    - Filtro por categoría probable
    """
    import re
    variaciones = []
    palabras = re.findall(r'\w{3,}', query.lower())

    # Excluir términos que ya fallaron
    palabras_filtradas = [p for p in palabras if p not in (historial_fallos or [])]

    # Solo la palabra más importante no fallida
    if palabras_filtradas:
        variaciones.append(palabras_filtradas[0])

    # ponytail: removed semantica table lookup — agent provides synonyms via parafrasis_list

    return variaciones[:3]


def buscar_recuerdo_microsegundos(self, concepto):
    """
    Evoca un recuerdo de largo plazo en microsegundos.
    Solo busca en nodos activos. Si esta dormido, no lo despierta.
    Busca en clave y en contenido.
    """
    key = concepto.lower().strip()
    inicio = time.perf_counter()

    self.cursor.execute("""
        SELECT contenido, peso_sinaptico, estado, asociaciones 
        FROM largo_plazo WHERE concepto = ?
    """, (key,))
    fila = self.cursor.fetchone()

    if not fila:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo WHERE estado = 'activo'")
        activos = self.cursor.fetchall()
        mejor_similitud = 0.0
        mejor_coincidencia = None

        for concepto_db, contenido_db, peso_db, estado_db, asociadas_db in activos:
            similitud = self._calcular_jaccard(key, concepto_db)
            if similitud > mejor_similitud:
                mejor_similitud = similitud
                mejor_coincidencia = (concepto_db, contenido_db, peso_db, estado_db, asociadas_db)

        if mejor_similitud >= 0.55 and mejor_coincidencia:
            print(f"[MemoryBioRAG] Coincidencia exacta fallida. Familiaridad difusa activada: '{concepto}' se asocia con '{mejor_coincidencia[0]}' (Similitud: {mejor_similitud:.2f})")
            key = mejor_coincidencia[0]
            fila = mejor_coincidencia[1:5]
        else:
            # Fallback: buscar en contenido
            contenido_match = self._buscar_en_contenido(concepto, solo_activos=True)
            if contenido_match:
                print(f"[MemoryBioRAG] Sin coincidencia en clave. Busqueda en contenido activada: '{concepto}' hallado en '{contenido_match[0]}'")
                key = contenido_match[0]
                fila = contenido_match[1:5]
            else:
                return None
    else:
        fila = (fila[0], fila[1], fila[2], fila[3])

    contenido, peso, estado, asociaciones = fila

    if estado == "dormido":
        return None

    nuevo_peso = min(1.0, peso + 0.15)
    self.cursor.execute("""
        UPDATE largo_plazo 
        SET peso_sinaptico = ?, ultimo_acceso = ? 
        WHERE concepto = ?
    """, (nuevo_peso, time.time(), key))

    if asociaciones:
        pass  # Legacy TEXT propagation removed — sinapsis table is canonical

    # Propagación vía sinapsis (fuente canónica)
    self.cursor.execute(
        "SELECT destino FROM sinapsis WHERE origen = ? UNION SELECT origen FROM sinapsis WHERE destino = ?",
        (key, key)
    )
    ahora = time.time()
    for (vecino,) in self.cursor.fetchall():
        self.cursor.execute("""
            UPDATE largo_plazo
            SET peso_sinaptico = MIN(1.0, peso_sinaptico + 0.05),
                ultimo_acceso = ?
            WHERE concepto = ? AND estado = 'activo'
        """, (ahora, vecino))
        self.cursor.execute(
            "UPDATE sinapsis SET ultimo_uso = ? WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
            (ahora, key, vecino, vecino, key)
        )

    self.conn.commit()
    fin = time.perf_counter()
    print(f"[MemoryBioRAG] Evocado exitosamente '{key}' en {(fin - inicio) * 1000000:.2f} microsegundos.")
    return contenido


def buscar_todos_recuerdos(self, concepto):
    """
    Busca TODOS los recuerdos relacionados con un concepto (clave + contenido).
    Devuelve lista de resultados ordenados por relevancia.
    Combina coincidencias de clave exacta, Jaccard en clave y busqueda en contenido.
    """
    key = concepto.lower().strip()
    resultados = []

    # 1. Coincidencia exacta
    self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado FROM largo_plazo WHERE concepto = ? AND estado = 'activo'", (key,))
    fila = self.cursor.fetchone()
    if fila:
        resultados.append((fila[0], fila[1], fila[2], fila[3], 1.0))

    # 2. Jaccard en claves activas
    self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado FROM largo_plazo WHERE estado = 'activo'")
    for concepto_db, contenido_db, peso_db, estado_db in self.cursor.fetchall():
        if concepto_db == key:
            continue
        sim = self._calcular_jaccard(key, concepto_db)
        if sim >= 0.55:
            resultados.append((concepto_db, contenido_db, peso_db, estado_db, sim))

    # 3. Contenido (incluye activos ya capturados, se filtran duplicados despues)
    contenidos = self._buscar_todos_en_contenido(concepto, solo_activos=True)
    existentes = {r[0] for r in resultados}
    for concepto_db, contenido_db, peso_db, estado_db, puntaje in contenidos:
        if concepto_db not in existentes:
            resultados.append((concepto_db, contenido_db, peso_db, estado_db, puntaje))

    resultados.sort(key=lambda r: r[4], reverse=True)
    return resultados


def buscar_recuerdo_profundo(self, concepto):
    """
    Busqueda en toda la corteza (activos + dormidos).
    Si encuentra un nodo dormido, lo despierta y aplica LTP.
    Busca en clave y en contenido.
    """
    key = concepto.lower().strip()
    inicio = time.perf_counter()

    self.cursor.execute("""
        SELECT contenido, peso_sinaptico, estado, asociaciones 
        FROM largo_plazo WHERE concepto = ?
    """, (key,))
    fila = self.cursor.fetchone()

    if not fila:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo")
        todos = self.cursor.fetchall()
        mejor_similitud = 0.0
        mejor_coincidencia = None

        for concepto_db, contenido_db, peso_db, estado_db, asociadas_db in todos:
            similitud = self._calcular_jaccard(key, concepto_db)
            if similitud > mejor_similitud:
                mejor_similitud = similitud
                mejor_coincidencia = (concepto_db, contenido_db, peso_db, estado_db, asociadas_db)

        if mejor_similitud >= 0.4 and mejor_coincidencia:
            print(f"[MemoryBioRAG] Busqueda profunda: '{concepto}' coincide con '{mejor_coincidencia[0]}' (Similitud: {mejor_similitud:.2f})")
            key = mejor_coincidencia[0]
            fila = mejor_coincidencia[1:5]
        else:
            # Fallback: buscar en contenido (incluye nodos dormidos)
            contenido_match = self._buscar_en_contenido(concepto, solo_activos=False)
            if contenido_match:
                print(f"[MemoryBioRAG] Sin coincidencia en clave. Busqueda en contenido activada: '{concepto}' hallado en '{contenido_match[0]}'")
                key = contenido_match[0]
                fila = contenido_match[1:5]
            else:
                return None
    else:
        fila = (fila[0], fila[1], fila[2], fila[3])

    contenido, peso, estado, asociaciones = fila

    # Despertar el nodo si estaba dormido y aplicar LTP
    nuevo_peso = min(1.0, peso + 0.15)
    self.cursor.execute("""
        UPDATE largo_plazo 
        SET estado = 'activo', peso_sinaptico = ?, ultimo_acceso = ? 
        WHERE concepto = ?
    """, (nuevo_peso, time.time(), key))
    if estado == "dormido":
        print(f"[MemoryBioRAG] Recuerdo '{key}' despertado de la memoria profunda.")

    if asociaciones:
        nodos_vecinos = [v.strip() for v in asociaciones.split(",") if v.strip()]
        for vecino in nodos_vecinos:
            self.cursor.execute("""
                UPDATE largo_plazo 
                SET peso_sinaptico = MIN(1.0, peso_sinaptico + 0.05),
                    ultimo_acceso = ?
                WHERE concepto = ? AND estado = 'activo'
            """, (time.time(), vecino))

    # Propagación también vía sinapsis
    self.cursor.execute(
        "SELECT destino FROM sinapsis WHERE origen = ? UNION SELECT origen FROM sinapsis WHERE destino = ?",
        (key, key)
    )
    ahora = time.time()
    for (vecino,) in self.cursor.fetchall():
        self.cursor.execute("""
            UPDATE largo_plazo
            SET peso_sinaptico = MIN(1.0, peso_sinaptico + 0.05),
                ultimo_acceso = ?
            WHERE concepto = ? AND estado = 'activo'
        """, (ahora, vecino))
        self.cursor.execute(
            "UPDATE sinapsis SET ultimo_uso = ? WHERE (origen = ? AND destino = ?) OR (origen = ? AND destino = ?)",
            (ahora, key, vecino, vecino, key)
        )

    self.conn.commit()
    fin = time.perf_counter()
    print(f"[MemoryBioRAG] Evocado exitosamente '{key}' en {(fin - inicio) * 1000000:.2f} microsegundos.")
    return contenido


def buscar_por_tokens(self, tokens, modo="relaxed", profundidad="activos", limite=3, pagina=1):
    """Busqueda multi-token con Soft AND.

    tokens: lista de raices (stems) para buscar en concepto y contenido
    modo: 'strict' (score=1.0) | 'relaxed' (al menos 1 token coincide)
    profundidad: 'activos' | 'profundo'
    limite: resultados por pagina
    pagina: numero de pagina (1-indexed)
    Retorna lista de (concepto, contenido, peso, estado, score)
    """
    if not tokens:
        return []

    total_tokens = len(tokens)
    resultados_con_score = []

    if profundidad == "profundo":
        self.cursor.execute(
            "SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo"
        )
    else:
        self.cursor.execute(
            "SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo WHERE estado = 'activo'"
        )

    for concepto, contenido, peso, estado, asociaciones in self.cursor.fetchall():
        texto_concepto = concepto.lower()
        texto_contenido = (contenido or "").lower()
        matches = 0
        en_concepto = False

        for t in tokens:
            t_lower = t.lower().strip()
            if t_lower in texto_concepto:
                matches += 1
                en_concepto = True
            elif t_lower in texto_contenido:
                matches += 1

        if matches == 0:
            continue

        score = matches / total_tokens
        if en_concepto:
            score = min(1.0, score + 0.1)

        if modo == "strict" and score < 1.0:
            continue

        resultados_con_score.append(
            (concepto, contenido, peso, estado, round(score, 2), asociaciones or "")
        )

    if not resultados_con_score:
        return [], 0

    resultados_con_score.sort(key=lambda r: (r[4], r[2]), reverse=True)

    inicio = (pagina - 1) * limite
    fin = inicio + limite
    pagina_resultados = resultados_con_score[inicio:fin]

    if profundidad == "profundo":
        pagina_resultados_actualizada = []
        for r in pagina_resultados:
            if r[3] == "dormido":
                nuevo_peso = min(1.0, r[2] + 0.15)
                self.cursor.execute(
                    "UPDATE largo_plazo SET estado = 'activo', peso_sinaptico = ?, ultimo_acceso = ? WHERE concepto = ?",
                    (nuevo_peso, time.time(), r[0]),
                )
                pagina_resultados_actualizada.append(
                    (r[0], r[1], nuevo_peso, "activo", r[4], r[5])
                )
            else:
                pagina_resultados_actualizada.append(r)
        pagina_resultados = pagina_resultados_actualizada
        self.conn.commit()
        pagina_resultados.sort(key=lambda r: (r[4], r[2]), reverse=True)
    else:
        self.conn.commit()
    return pagina_resultados, len(resultados_con_score)


def buscar_por_predicados(self, sujeto=None, accion=None, objeto=None, contexto=None, limite=10):
    """Búsqueda por roles semánticos (SRL v16.0).
    Filtra la tabla predicados por sujeto, acción, objeto y/o contexto.
    Retorna lista de (concepto, contenido, peso, estado, score, asociaciones)."""
    condiciones = []
    params = []
    if sujeto:
        condiciones.append("p.sujeto LIKE ?")
        params.append(f"%{sujeto}%")
    if accion:
        condiciones.append("p.accion LIKE ?")
        params.append(f"%{accion}%")
    if objeto:
        condiciones.append("p.objeto LIKE ?")
        params.append(f"%{objeto}%")
    if contexto:
        condiciones.append("p.contexto LIKE ?")
        params.append(f"%{contexto}%")

    if not condiciones:
        return []

    where = " AND ".join(condiciones)
    params.append(limite)
    self.cursor.execute(f"""
        SELECT DISTINCT l.concepto, l.contenido, l.peso_sinaptico, l.estado,
               l.peso_sinaptico AS score, l.asociaciones
        FROM predicados p
        JOIN largo_plazo l ON l.concepto = p.concepto
        WHERE {where} AND l.estado = 'activo'
        ORDER BY l.peso_sinaptico DESC
        LIMIT ?
    """, tuple(params))

    return [(r[0], r[1], r[2], r[3], r[4], r[5] or "") for r in self.cursor.fetchall()]


def _fallback_busqueda_predicados(self, frase, limite=10):
    """
    Fallback Causal SRL v1.0.
    Se ejecuta cuando la búsqueda tradicional por 8 señales arroja 0 candidatos o score < 0.35.
    Extrae o tokeniza la query y busca coincidencias por roles semánticos en la tabla predicados.
    """
    if not frase or len(frase.strip()) < 3:
        return []

    import re
    from core.srl_extractor import extraerte_normalizado, VERBOS_CANONICOS
    tokens = [extraerte_normalizado(w) for w in re.findall(r'\w{3,}', frase)]
    if not tokens:
        return []

    acciones = {VERBOS_CANONICOS.get(t, t) for t in tokens}

    placeholders = " OR ".join([
        "(PALABRA_PREFIJO(?, COALESCE(p.sujeto, '')) = 1 OR PALABRA_PREFIJO(?, COALESCE(p.accion, '')) = 1 OR PALABRA_PREFIJO(?, COALESCE(p.objeto, '')) = 1 OR PALABRA_PREFIJO(?, COALESCE(p.contexto, '')) = 1)"
    ] * len(tokens))
    params = []
    for t in tokens:
        params.extend([t, t, t, t])

    sql = f"""
        SELECT DISTINCT l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones,
                        p.sujeto, p.accion, p.objeto, p.contexto
        FROM predicados p
        JOIN largo_plazo l ON l.concepto = p.concepto
        WHERE ({placeholders}) AND l.estado = 'activo'
        LIMIT ?
    """
    params.append(limite)

    try:
        self.cursor.execute(sql, tuple(params))
        rows = self.cursor.fetchall()
    except Exception:
        return []

    resultados = []
    for r in rows:
        conc, cont, peso, est, asoc, suj, acc, obj, ctx = r
        match_bonus = 0.50
        if acc and extraerte_normalizado(acc) in acciones:
            match_bonus = 0.65
        score = round(min(0.85, match_bonus + (peso or 0.5) * 0.10), 4)
        resultados.append((conc, cont, peso or 0.5, est, score, asoc or ""))

    resultados.sort(key=lambda x: x[4], reverse=True)
    return resultados


def _buscar_en_contenido(self, query, solo_activos=True):
    """
    Busca coincidencias en el CONTENIDO (no solo en clave) usando coincidencia de tokens.
    Retorna tupla (concepto, contenido, peso, estado, asociaciones) o None.
    """
    tokens_query = set(re.findall(r'\b\w{3,}\b', query.lower()))

    if solo_activos:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo WHERE estado = 'activo'")
    else:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado, asociaciones FROM largo_plazo")

    nodos = self.cursor.fetchall()
    mejor_puntaje = 0.0
    mejor_nodo = None

    for concepto, contenido, peso, estado, asociaciones in nodos:
        contenido_lower = contenido.lower()
        # Buscar cada token en contenido
        tokens_encontrados = sum(1 for t in tokens_query if t in contenido_lower)
        if tokens_encontrados > 0:
            puntaje = tokens_encontrados / len(tokens_query) * 0.8 + 0.2  # base 0.2 + proporcion
            if puntaje > mejor_puntaje:
                mejor_puntaje = puntaje
                mejor_nodo = (concepto, contenido, peso, estado, asociaciones)

    if mejor_nodo and mejor_puntaje >= 0.3:
        return mejor_nodo
    return None


def _buscar_todos_en_contenido(self, query, solo_activos=True):
    """
    Busca TODAS las coincidencias en contenido. Retorna lista de tuplas
    (concepto, contenido, peso, estado, puntaje) ordenadas por relevancia.
    """
    tokens_query = set(re.findall(r'\b\w{3,}\b', query.lower()))
    if not tokens_query:
        return []

    if solo_activos:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado FROM largo_plazo WHERE estado = 'activo'")
    else:
        self.cursor.execute("SELECT concepto, contenido, peso_sinaptico, estado FROM largo_plazo")

    resultados = []
    for concepto, contenido, peso, estado in self.cursor.fetchall():
        contenido_lower = contenido.lower()
        tokens_encontrados = sum(1 for t in tokens_query if t in contenido_lower)
        if tokens_encontrados > 0:
            puntaje = tokens_encontrados / len(tokens_query) * 0.8 + 0.2
            resultados.append((concepto, contenido, peso, estado, puntaje))

    resultados.sort(key=lambda r: r[4], reverse=True)
    return resultados
