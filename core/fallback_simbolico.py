"""
core/fallback_simbolico.py
===========================
Fallback 2.1 puramente simbólico.
Zero embeddings. Zero LLM. Zero dependencias obligatorias nuevas.
Agnóstico al dominio del usuario y bilingüe real (ES + EN) con graceful degradation.
"""

from __future__ import annotations
import os
import re
import unicodedata
from functools import lru_cache
from typing import Optional
from core.stopwords import _STOPWORDS_QUERY

# Traducción externa desactivada por defecto (local-only).
# Activar con: export BIORAG_TRADUCCION_ACTIVA=1
_TRADUCCION_ACTIVA = os.environ.get("BIORAG_TRADUCCION_ACTIVA", "0") == "1"

# ═══════════════════════════════════════════════════════════
# CAPA 0: Normalización (base de todo)
# ═══════════════════════════════════════════════════════════

def _normalizar(texto: str) -> str:
    """
    Elimina tildes y normaliza a minúsculas.
    "hipertensión" → "hipertension"
    "cardíaco" → "cardiaco"
    """
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFKD', texto.lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


_STOPWORDS_NORM = {_normalizar(w) for w in _STOPWORDS_QUERY}



def _tokenizar_normalizado(texto: str) -> set[str]:
    """Tokeniza y normaliza (sin tildes, sin stopwords)."""
    if not texto:
        return set()
    texto_norm = _normalizar(texto.replace('_', ' ').replace('-', ' '))
    tokens = {t for t in re.findall(r'\w{2,}', texto_norm)}
    return tokens - _STOPWORDS_NORM


# ═══════════════════════════════════════════════════════════
# CAPA 1: Levenshtein (typos y variantes morfológicas)
# ═══════════════════════════════════════════════════════════

@lru_cache(maxsize=8192)
def _levenshtein(s1: str, s2: str) -> int:
    """
    Distancia de Levenshtein.
    Zero dependencias. O(n*m) tiempo, O(min(n,m)) espacio. Caged.
    """
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if not s2:
        return len(s1)

    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(
                prev[j + 1] + 1,   # borrar
                curr[j] + 1,       # insertar
                prev[j] + (c1 != c2)  # sustituir
            ))
        prev = curr
    return prev[-1]


def similitud_levenshtein(s1: str, s2: str) -> float:
    """
    Similitud normalizada [0.0, 1.0].
    Normaliza tildes antes de comparar.
    """
    if s1 == s2:
        return 1.0
    # Quick check: if both are ASCII lowercase (very common for tokenized words)
    # then they are already normalized!
    is_norm_1 = s1.islower() and s1.isascii()
    is_norm_2 = s2.islower() and s2.isascii()
    
    s1_norm = s1 if is_norm_1 else _normalizar(s1)
    s2_norm = s2 if is_norm_2 else _normalizar(s2)
    
    if s1_norm == s2_norm:
        return 1.0
        
    max_len = max(len(s1_norm), len(s2_norm))
    if max_len == 0:
        return 1.0
    dist = _levenshtein(s1_norm, s2_norm)
    return round(1.0 - dist / max_len, 4)


def mejor_similitud_levenshtein(
    tokens_query: set[str],
    tokens_nodo: set[str]
) -> float:
    """
    Mejor similitud Levenshtein entre pares de tokens.
    """
    if not tokens_query or not tokens_nodo:
        return 0.0

    # O(1) check for exact match of any word in the query.
    # If there is a common token, the maximum similarity is 1.0.
    if tokens_query & tokens_nodo:
        return 1.0

    mejor = 0.0
    for qt in tokens_query:
        for nt in tokens_nodo:
            # Solo comparar tokens de longitud similar
            max_len = max(len(qt), len(nt))
            if max_len == 0:
                continue
            
            # Si la diferencia de longitud hace matemáticamente imposible superar el mejor score actual, omitir.
            max_sim_teorica = 1.0 - abs(len(qt) - len(nt)) / max_len
            if max_sim_teorica <= mejor:
                continue
                
            if abs(len(qt) - len(nt)) > max_len * 0.5:
                continue
                
            sim = similitud_levenshtein(qt, nt)
            if sim > mejor:
                mejor = sim
            if mejor >= 0.95:
                return mejor  # early exit
    return mejor


# ═══════════════════════════════════════════════════════════
# CAPA 2: WordNet synsets (sinónimos de lenguaje general)
# ═══════════════════════════════════════════════════════════

_wordnet_disponible: Optional[bool] = None

def _verificar_wordnet() -> bool:
    """Verifica si WordNet está disponible de forma local y silenciosa. Cachea el resultado."""
    global _wordnet_disponible
    if os.environ.get("BIORAG_WORDNET_ENABLED", "1") == "0":
        return False
    if _wordnet_disponible is None:
        try:
            import nltk
            # Configurar ruta local de nltk_data dentro del proyecto
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            local_nltk_dir = os.path.join(project_root, "MemoryBioRAG_Data", "nltk_data")
            if local_nltk_dir not in nltk.data.path:
                nltk.data.path.insert(0, local_nltk_dir)

            from nltk.corpus import wordnet as wn
            wn.synsets('test')
            _wordnet_disponible = True
        except Exception:
            _wordnet_disponible = False
    return _wordnet_disponible


@lru_cache(maxsize=512)
def expandir_palabra_wordnet(palabra: str) -> frozenset[str]:
    """
    Expande una palabra con sus sinónimos de WordNet.
    Busca en español E inglés.
    """
    if not _verificar_wordnet():
        return frozenset()

    try:
        from nltk.corpus import wordnet as wn

        palabra_norm = _normalizar(palabra)
        expansiones: set[str] = set()

        for lang in ('spa', 'eng'):
            synsets = wn.synsets(palabra_norm, lang=lang)
            if not synsets:
                synsets = wn.synsets(palabra, lang=lang)

            for syn in synsets[:3]:  # máx 3 synsets
                # Lemas en español
                for lemma in syn.lemmas(lang='spa'):
                    nombre = _normalizar(lemma.name().replace('_', ' '))
                    for tok in nombre.split():
                        if len(tok) >= 2:
                            expansiones.add(tok)
                # Lemas en inglés
                for lemma in syn.lemmas(lang='eng'):
                    nombre = _normalizar(lemma.name().replace('_', ' '))
                    for tok in nombre.split():
                        if len(tok) >= 2:
                            expansiones.add(tok)

        expansiones.discard(palabra_norm)
        expansiones.discard(palabra.lower())
        return frozenset(expansiones)

    except Exception:
        return frozenset()


def expandir_query_wordnet(tokens: set[str]) -> set[str]:
    """Expande todos los tokens del query con WordNet."""
    expansiones: set[str] = set()
    for token in tokens:
        expansiones.update(expandir_palabra_wordnet(token))
    return expansiones - tokens


# ═══════════════════════════════════════════════════════════
# CAPA 3: Puente de Traducción (ES -> EN / EN -> ES)
# ═══════════════════════════════════════════════════════════

@lru_cache(maxsize=512)
def _traducir_token(token: str) -> Optional[str]:
    """
    Traduce un token individual de español a inglés usando deep-translator.
    Retorna None de forma elegante si falla o no está instalado.
    """
    try:
        from deep_translator import GoogleTranslator
        # Traducir al inglés (detector automático del origen)
        traducido = GoogleTranslator(source='auto', target='en').translate(token)
        if traducido:
            return _normalizar(traducido)
    except Exception:
        pass
    return None


def expandir_con_traduccion(tokens: set[str]) -> set[str]:
    """
    Traduce los tokens y busca sus sinónimos en el WordNet inglés para aumentar recall.
    Solo se ejecuta si BIORAG_TRADUCCION_ACTIVA=1 (off por defecto).
    """
    if not _TRADUCCION_ACTIVA:
        return set()
    expansiones: set[str] = set()
    for token in tokens:
        trad = _traducir_token(token)
        if trad and trad != token:
            expansiones.add(trad)
            expansiones.update(expandir_palabra_wordnet(trad))
    return expansiones - tokens


@lru_cache(maxsize=512)
def _expandir_token_cached(token: str) -> frozenset[str]:
    """Cachea la expansión de WordNet y traducción para un único token."""
    expansiones = set([token])
    expansiones.update(expandir_palabra_wordnet(token))
    if _TRADUCCION_ACTIVA:
        trad = _traducir_token(token)
        if trad and trad != token:
            expansiones.add(trad)
            expansiones.update(expandir_palabra_wordnet(trad))
    return frozenset(expansiones)


# ═══════════════════════════════════════════════════════════
def _calcular_cobertura_fuzzy(tokens_query: set[str], tokens_target: set[str]) -> float:
    """
    Calcula la fracción de tokens de la query que coinciden con los tokens destino,
    permitiendo expansión semántica (WordNet) y coincidencias parciales por Levenshtein.
    """
    if not tokens_query or not tokens_target:
        return 0.0
        
    total_coincidencia = 0.0
    for q_tok in tokens_query:
        # 1. Coincidencia exacta o semántica (WordNet/Traducción)
        q_exp = _expandir_token_cached(q_tok)
        if q_exp & tokens_target:
            total_coincidencia += 1.0
            continue
            
        # 2. Coincidencia difusa (Levenshtein) con tokens del destino
        max_sim = 0.0
        for t_tok in tokens_target:
            max_len = max(len(q_tok), len(t_tok))
            if max_len == 0:
                continue
            if abs(len(q_tok) - len(t_tok)) > max_len * 0.5:
                continue
            sim = similitud_levenshtein(q_tok, t_tok)
            if sim > max_sim:
                max_sim = sim
                
        if max_sim >= 0.75:
            total_coincidencia += max_sim
            
    return round(total_coincidencia / len(tokens_query), 4)


# Score Simbólico Compuesto
# ═══════════════════════════════════════════════════════════

def score_simbolico(
    tokens_query: set[str],
    concepto: str,
    contenido: str,
    sinonimos: str = ""
) -> float:
    """
    Score simbólico compuesto para el Fallback 2.1.
    Combina Normalización, Levenshtein, WordNet bilingüe y traducción opcional.
    """
    if not tokens_query:
        return 0.0

    texto_nodo = f"{concepto} {contenido or ''} {sinonimos or ''}"
    tokens_nodo = _tokenizar_normalizado(texto_nodo)
    if not tokens_nodo:
        return 0.0

    # Si es un solo token y tiene un match exacto/levenshtein alto, early-exit
    if len(tokens_query) == 1:
        score_lev = mejor_similitud_levenshtein(tokens_query, tokens_nodo)
        if score_lev >= 0.95:
            return score_lev

    return _calcular_cobertura_fuzzy(tokens_query, tokens_nodo)


# ═══════════════════════════════════════════════════════════
# Interfaz de búsqueda
# ═══════════════════════════════════════════════════════════

def buscar_fallback_simbolico(
    query: str,
    candidatos: list[tuple],
    umbral: float = 0.60,
    top_k: int = 10
) -> list[tuple]:
    """
    Aplica el fallback simbólico sobre una lista de candidatos.
    Retorna lista de (score, rowid, concepto, contenido, peso, estado, asoc) ordenada DESC.
    """
    tokens_query = _tokenizar_normalizado(query)
    if not tokens_query:
        return []

    resultados: list[tuple] = []

    for cand in candidatos:
        rowid  = cand[0]
        conc   = cand[1] or ""
        cont   = cand[2] or ""
        peso   = cand[3] if len(cand) > 3 else 1.0
        estado = cand[4] if len(cand) > 4 else "activo"
        asoc   = cand[5] if len(cand) > 5 else ""
        sins   = cand[6] if len(cand) > 6 else ""

        score = score_simbolico(tokens_query, conc, cont, sins)

        if score >= umbral:
            resultados.append((score, rowid, conc, cont, peso, estado, asoc))

    resultados.sort(key=lambda x: x[0], reverse=True)
    return resultados[:top_k]


def score_simbolico_concepto(tokens_query: set[str], concepto: str) -> float:
    """Calcula la similitud simbólica contra el nombre del concepto."""
    if not tokens_query or not concepto:
        return 0.0
    tokens_c = _tokenizar_normalizado(concepto)
    if not tokens_c:
        return 0.0
    
    if len(tokens_query) == 1:
        score_lev = mejor_similitud_levenshtein(tokens_query, tokens_c)
        if score_lev >= 0.95:
            return score_lev
            
    return _calcular_cobertura_fuzzy(tokens_query, tokens_c)


def score_simbolico_sinonimos(tokens_query: set[str], sinonimos: str) -> float:
    """Calcula la similitud simbólica contra la lista de sinónimos."""
    if not tokens_query or not sinonimos:
        return 0.0
    tokens_s = _tokenizar_normalizado(sinonimos)
    if not tokens_s:
        return 0.0
    
    if len(tokens_query) == 1:
        score_lev = mejor_similitud_levenshtein(tokens_query, tokens_s)
        if score_lev >= 0.95:
            return score_lev
            
    return _calcular_cobertura_fuzzy(tokens_query, tokens_s)


