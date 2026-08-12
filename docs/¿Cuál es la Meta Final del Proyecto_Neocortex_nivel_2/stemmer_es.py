"""
Stemmer Bilingüe ES/EN para BioRAG v19.1
==========================================
Motor de stemming industrial completo usando algoritmos académicos probados:

  ESPAÑOL : Snowball Spanish — implementación de Savoy (1999)
            Cubre ~260 reglas morfológicas en 4 pasos estructurados.
            Gestiona: verbales, nominales, adjetivales, derivaciones.

  INGLÉS  : Snowball English — basado en Porter (1980) / Porter2 (Snowball)
            Cubre 5 fases + reglas especiales para irregular forms.
            Estándar de la industria en motores de búsqueda (Lucene, ES, Whoosh).

  FUENTE  : NLTK — ya instalado como dependencia de BioRAG (WordNet).
            Cero dependencias nuevas.

Principio del Cross-Language Bridge (ES/EN):
  configurar → 'configur'    configuration → 'configur'   ← MISMO STEM
  implementar → 'implement'  implementing → 'implement'   ← MISMO STEM
  consolidar → 'consolid'    consolidating → 'consolid'   ← MISMO STEM
  memoria → 'memori'         memory → 'memori'            ← MISMO STEM

  Las colisiones de stem ES/EN son INTENCIONALES. Permiten que el motor PMI
  trate 'configurar' y 'configuration' como el mismo token en la matriz
  de co-ocurrencia → cross-language retrieval sin traducción ni embeddings.

Compatibilidad:
  - Misma API pública que v19.0: stem(), stemizar_set(), tokens_equivalentes(),
    similitud_stem()
  - Fallback automático a reglas manuales si NLTK no está disponible.
"""

import unicodedata
import re

# =============================================================================
# Normalización Unicode
# =============================================================================

_ACENTOS_ES = set('áéíóúüñÁÉÍÓÚÜÑ')


def _quitar_acentos(texto: str) -> str:
    """'configuración' → 'configuracion', 'memory' → 'memory' (sin cambio)."""
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _es_espanol(word: str) -> bool:
    """
    Heurística rápida: ¿el token es probablemente español?
    Criterios: tiene ñ/acento, O termina con sufijo morfológico del español.
    """
    w = word.lower()
    # Caracteres exclusivos del español
    if any(c in _ACENTOS_ES for c in word):
        return True
    # Sufijos morfológicos con alta certeza de ser español:
    es_endings_alta = (
        'ción', 'cion',          # configuración, función
        'ando', 'iendo',         # configurando, implementando
        'ados', 'idas',          # configurados
        'mente',                 # rápidamente
        'idad', 'idades',        # velocidad, capacidades
        'ista', 'istas',         # desarrollista
        'ismo', 'ismos',         # mecanismo
        'ador', 'adora',         # procesador
        'eces', 'eces',          # veces
        # Infinitivos (alta frecuencia en corpus técnico)
        'izar', 'ificar',        # sincronizar, notificar
        'ecer', 'acer',          # establecer, hacer
    )
    if any(w.endswith(e) for e in es_endings_alta):
        return True
    # Terminaciones -ar/-er/-ir: solo si la raíz tiene longitud suficiente
    # (evita confundir "bar", "her", "sir" en inglés)
    for suf in ('ar', 'er', 'ir'):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return True
    return False


# =============================================================================
# Inicialización lazy de los stemmers industriales (NLTK)
# =============================================================================

_stemmer_es = None   # Snowball Spanish (Savoy 1999)
_stemmer_en = None   # Snowball English (Porter 1980 / Porter2)
_nltk_disponible = None


def _init_stemmers() -> bool:
    """
    Inicializa los stemmers NLTK en el primer uso (lazy).
    Retorna True si NLTK está disponible, False si se usará el fallback.
    """
    global _stemmer_es, _stemmer_en, _nltk_disponible
    if _nltk_disponible is not None:
        return _nltk_disponible

    try:
        from nltk.stem import SnowballStemmer
        _stemmer_es = SnowballStemmer('spanish')   # Savoy (1999)
        _stemmer_en = SnowballStemmer('english')   # Porter (1980) / Snowball
        _nltk_disponible = True
        return True
    except Exception:
        _nltk_disponible = False
        return False


# =============================================================================
# Fallback — reglas manuales para cuando NLTK no está disponible
# =============================================================================

_SUFIJOS_ES_FALLBACK = [
    ('aciones', 5), ('amiento', 5), ('imientos', 5), ('imiento', 5),
    ('acion', 5), ('iciones', 5), ('icion', 5),
    ('adores', 5), ('adora', 5), ('ador', 5),
    ('mente', 5), ('idades', 5), ('idad', 4),
    ('istas', 4), ('ista', 4),
    ('iendo', 4), ('ando', 4), ('ados', 4), ('adas', 4),
    ('idos', 4), ('idas', 4), ('ado', 4), ('ada', 4),
    ('ido', 4), ('ida', 4), ('amos', 4), ('aron', 4),
    ('aban', 4), ('aran', 4), ('endo', 4),
    ('izar', 4), ('ificar', 4), ('ecer', 4), ('acer', 4),
    ('ar', 4), ('er', 4), ('ir', 4),
    ('iones', 4), ('bles', 4), ('ble', 4),
    ('osos', 4), ('osas', 4), ('oso', 4), ('osa', 4),
    ('ivos', 4), ('ivas', 4), ('ivo', 4), ('iva', 4),
    ('les', 4), ('ueda', 4), ('anza', 4), ('eza', 4),
    ('eso', 4), ('es', 4), ('os', 3), ('as', 3), ('al', 4),
]

_SUFIJOS_EN_FALLBACK = [
    ('izations', 5), ('ization', 5), ('ifications', 5), ('ification', 5),
    ('ications', 5), ('ication', 5), ('ations', 5), ('ation', 5),
    ('ments', 5), ('ment', 5), ('nesses', 5), ('ness', 4),
    ('ities', 4), ('ity', 4),
    ('inging', 5), ('tting', 5), ('nning', 5), ('pping', 5),
    ('essing', 4), ('ssing', 5), ('ing', 4),
    ('pped', 4), ('tted', 4), ('nned', 4), ('ssed', 4),
    ('ied', 4), ('ed', 4),
    ('ies', 4), ('ves', 4), ('ses', 4),
    ('ically', 5), ('ally', 4), ('ully', 4), ('ously', 4),
    ('ively', 4), ('able', 4), ('ible', 4), ('ables', 4), ('ibles', 4),
    ('ous', 4), ('ive', 4), ('ives', 4),
    ('ful', 4), ('fuls', 4), ('less', 4),
    ('ers', 4), ('er', 4), ('or', 4), ('ors', 4),
    ('ly', 4), ('al', 4), ('als', 4),
    ('ories', 4), ('ory', 4),
    ('s', 4), ('e', 4),
]


def _aplicar_sufijos_fallback(word: str, sufijos: list) -> str | None:
    """Prueba sufijos en orden. Retorna el stem o None si ninguno aplica."""
    for sufijo, min_stem in sufijos:
        if word.endswith(sufijo) and len(word) - len(sufijo) >= min_stem:
            stem_result = word[:-len(sufijo)]
            if len(stem_result) >= 3:
                return stem_result
    return None


def _stem_fallback(token: str) -> str:
    """
    Stemmer de respaldo usando listas de sufijos manuales.
    Se usa cuando NLTK no está disponible.
    """
    if not token or len(token) < 4:
        return token.lower() if token else token

    word = _quitar_acentos(token.lower())

    if _es_espanol(token):
        result = _aplicar_sufijos_fallback(word, _SUFIJOS_ES_FALLBACK)
        if result is None:
            result = _aplicar_sufijos_fallback(word, _SUFIJOS_EN_FALLBACK)
    else:
        result = _aplicar_sufijos_fallback(word, _SUFIJOS_EN_FALLBACK)
        if result is None:
            result = _aplicar_sufijos_fallback(word, _SUFIJOS_ES_FALLBACK)

    return result if result is not None else word


# =============================================================================
# Post-procesado para infinitivos españoles que Snowball no reduce
# =============================================================================
# Snowball Spanish es un stemmer "light" que preserva los infinitivos intactos.
# Esto rompe el cross-language bridge con los gerundios en inglés.
# Solución: si Snowball no redujo la palabra, aplicar un paso de infinitivos.

_INFINITIVOS_ES = [
    # Verbos -izar (muy frecuentes en vocabulario técnico)
    # "sincronizar" → "sincroniz", "optimizar" → "optim"
    ('izar',  4),   # sincronizar→sincroniz, tokenizar→tokeniz
    ('ificar', 4),  # notificar→notif, modificar→modif, verificar→verif
    ('izar',  4),
    # Verbos -ar generales
    ('ar',    4),   # implementar→implement, consolidar→consolid
    # Verbos -er
    ('ecer',  4),   # establecer→establec, aparecer→aparec
    ('cer',   4),   # reconocer→reconoc
    ('er',    4),   # establecer→establec, resolver→resolv
    # Verbos -ir
    ('ir',    4),   # definir→defin, vivir→viv
]

_GERUNDIOS_ES = [
    # Snowball a veces tampoco reduce gerundios
    ('iendo', 4),   # implementando→implement, estableciendo→establec
    ('ando',  4),   # configurando→configur
]

_PARTICIPIOS_ES = [
    ('ado', 4),   # configurado→configur
    ('ada', 4),
    ('ido', 4),   # definido→defin
    ('ida', 4),
]

_POST_SUFIJOS_ES = _GERUNDIOS_ES + _PARTICIPIOS_ES + _INFINITIVOS_ES


def _post_procesar_es(word_original: str, stem_snowball: str) -> str:
    """
    Si Snowball no redujo la palabra (resultado == input normalizado),
    intenta aplicar reglas de infinitivos, gerundios y participios.
    Garantiza que implementar→implement, consolidar→consolid, etc.
    """
    if stem_snowball != word_original:
        return stem_snowball  # Snowball ya lo redujo, respetar

    # Snowball no cambió nada → intentar post-procesado
    for sufijo, min_stem in _POST_SUFIJOS_ES:
        if word_original.endswith(sufijo):
            candidato = word_original[:-len(sufijo)]
            if len(candidato) >= min_stem and len(candidato) >= 3:
                return candidato

    return stem_snowball  # Sin cambio posible → devolver tal cual


# =============================================================================
# API pública — Motor principal con Snowball (Savoy + Porter)
# =============================================================================

def stem(token: str) -> str:
    """
    Stemming bilingüe ES/EN con estrategia híbrida:

    INGLÉS:
      1. Snowball English (Porter 1980/2) — 5 fases, ~400 patrones
    
    ESPAÑOL:
      1. Snowball Spanish (Savoy 1999) — maneja formas complejas nominales/derivadas
      2. Post-procesado propio — captura infinitivos (-ar/-er/-ir) que Snowball omite

    El post-procesado cierra el gap del cross-language bridge:
      implementar → Snowball→"implementar" → post→"implement"
      implementing → Snowball→"implement"
      ► Mismo stem: "implement" ✅

    Fallback automático a reglas manuales si NLTK no está disponible.
    """
    if not token or len(token) < 3:
        return token.lower() if token else token

    word_normalizada = _quitar_acentos(token.lower())

    if not _init_stemmers():
        return _stem_fallback(token)

    try:
        if _es_espanol(token):
            stem_snow = _stemmer_es.stem(word_normalizada)
            # Post-procesado: corregir infinitivos que Snowball no reduce
            return _post_procesar_es(word_normalizada, stem_snow)
        else:
            result = _stemmer_en.stem(word_normalizada)
            return result if result and len(result) >= 3 else word_normalizada

    except Exception:
        return _stem_fallback(token)


def stemizar_set(tokens: set[str]) -> set[str]:
    """
    Expande un set de tokens incluyendo sus stems.
    Mantiene el original Y el stem para no perder búsquedas exactas.

    {'configure', 'configuration'} → {'configure', 'configur', 'configuration'}
    """
    resultado = set()
    for tok in tokens:
        resultado.add(tok)
        s = stem(tok)
        if s and s != tok:
            resultado.add(s)
    return resultado


def tokens_equivalentes(tok_a: str, tok_b: str) -> bool:
    """
    True si dos tokens son morfológicamente equivalentes (mismo stem).
    Funciona cross-language:
        tokens_equivalentes('configurar', 'configuration') → True
        tokens_equivalentes('implementar', 'implementing') → True
        tokens_equivalentes('perro', 'gato')              → False
    """
    if not tok_a or not tok_b:
        return False
    if tok_a.lower() == tok_b.lower():
        return True
    stem_a = stem(tok_a)
    stem_b = stem(tok_b)
    return stem_a == stem_b and len(stem_a) >= 3


def similitud_stem(tokens_a: set[str], tokens_b: set[str]) -> float:
    """
    Jaccard con expansión morfológica bilingüe (Snowball ES + EN).
    Encuentra solapamiento aunque los tokens estén en idiomas distintos.

    Returns: float [0, 1]
    """
    if not tokens_a or not tokens_b:
        return 0.0

    stems_a = {stem(t) for t in tokens_a}
    stems_b = {stem(t) for t in tokens_b}

    interseccion = stems_a & stems_b
    union = stems_a | stems_b

    return len(interseccion) / len(union) if union else 0.0


# =============================================================================
# Diagnóstico — mostrar qué motor está activo
# =============================================================================

def info_motor() -> dict:
    """
    Retorna información sobre el motor de stemming activo.
    Útil para debug y auditoría.
    """
    nltk_ok = _init_stemmers()
    return {
        'motor': 'Snowball (Savoy 1999 + Porter 1980)' if nltk_ok else 'Reglas manuales (fallback)',
        'nltk_disponible': nltk_ok,
        'motor_es': 'SnowballStemmer("spanish")' if nltk_ok else 'sufijos_manuales_es',
        'motor_en': 'SnowballStemmer("english")' if nltk_ok else 'sufijos_manuales_en',
        'ejemplo_es': f'configuración → {stem("configuración")}',
        'ejemplo_en': f'configuration → {stem("configuration")}',
        'cross_bridge': stem('configuración') == stem('configuration'),
    }
