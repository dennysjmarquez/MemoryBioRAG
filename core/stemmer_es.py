"""
Stemmer Bilingüe ES/EN para BioRAG v19.0
==========================================
Reducción morfológica ligera (light stemming) para vocabulario técnico
en ESPAÑOL e INGLÉS — los dos idiomas principales del corpus BioRAG.

SIN dependencias externas. Puro Python + unicodedata.

Cómo funciona:
  1. Detecta idioma del token (español tiene ñ/acentos/sufijos -ción/-ando)
  2. Aplica reglas del idioma detectado (primero)
  3. Si no aplica, prueba las del otro idioma (corpus mixto)

Normaliza:
  ES: configuración/configurar/configurando → configur
  ES: implementación/implementar/implementado → implement
  ES: búsqueda/buscando/buscar → busc/buscand/busc
  EN: configuration/configure/configuring → configur  (¡mismo stem!)
  EN: implement/implemented/implementing → implement
  EN: memory/memories/memorize → memor
  EN: search/searching/searched → search

La colisión de stems ES/EN es INTENCIONAL: permite que "configurar" y
"configure" sean el mismo token en la matriz PMI. Eso es exactamente
el cross-language bridge que buscamos.

Basado en:
  - Savoy (1999) — French/Spanish light stemmer
  - Paice/Husk (1990) — English stemmer
  - Porter (1980) — English suffix stripping
"""

import re
import unicodedata

# =============================================================================
# Normalización Unicode
# =============================================================================

_ACENTOS_ES = set('áéíóúüñÁÉÍÓÚÜÑ')


def _quitar_acentos(texto: str) -> str:
    """'búsqueda' → 'busqueda', 'implementation' → 'implementation' (no cambia)."""
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _es_espanol(word: str) -> bool:
    """
    Heurística rápida: ¿el token es probablemente español?
    Criterios: tiene ñ/acento, O termina con sufijo característico ES.
    """
    w = word.lower()
    # Caracteres exclusivos del español
    if any(c in _ACENTOS_ES for c in word):
        return True
    # Sufijos morfológicos específicos del español
    es_endings = ('ción', 'cion', 'ando', 'iendo', 'ados', 'idas',
                  'mente', 'idad', 'ista', 'ismo', 'ador', 'ando')
    return any(w.endswith(e) for e in es_endings)


# =============================================================================
# Sufijos ESPAÑOL — mayor a menor longitud (orden importa)
# =============================================================================

_SUFIJOS_ES = [
    # Sustantivos abstractos
    ('aciones',    5),   # configuraciones → configur
    ('amiento',    5),   # funcionamiento → funcion
    ('imientos',   5),   # procedimientos → procedi
    ('imiento',    5),   # procedimiento → procedi
    ('acion',      5),   # implementacion → implement
    ('acion',      5),
    ('iciones',    5),   # definiciones → defin
    ('icion',      5),   # definicion → defin
    ('adores',     5),   # procesadores → proces
    ('adora',      5),   # procesadora → proces
    ('ador',       5),   # procesador → proces
    ('mente',      5),   # rapidamente → rapid
    ('idades',     5),   # capacidades → capac
    ('idad',       4),   # capacidad → capac
    ('istas',      4),   # desarrollistas → desarroll
    ('ista',       4),   # desarrollista → desarroll
    # Verbales
    ('iendo',      4),   # implementando → implement
    ('ando',       4),   # configurando → configur
    ('ados',       4),   # configurados → configur
    ('adas',       4),   # configuradas → configur
    ('idos',       4),   # definidos → defin
    ('idas',       4),   # definidas → defin
    ('ado',        4),   # configurado → configur
    ('ada',        4),   # configurada → configur
    ('ido',        4),   # definido → defin
    ('ida',        4),   # definida → defin
    ('amos',       4),   # configuramos → configur
    ('aron',       4),   # configuraron → configur
    ('aban',       4),   # configuraban → configur
    ('aran',       4),   # configuraran → configur
    ('endo',       4),   # haciendo → hac
    # Infinitivos
    ('izar',       4),   # actualizar → actual
    ('ificar',     4),   # notificar → notif
    ('ecer',       4),   # establecer → establ
    ('acer',       4),   # hacer → hac
    ('ar',         4),   # configurar → configur
    ('er',         4),   # establecer → establec
    ('ir',         4),   # definir → defin
    # Plurales / género / derivados
    ('iones',      4),   # funciones → func
    ('bles',       4),   # disponibles → disponibl
    ('ble',        4),   # disponible → disponibl
    ('osos',       4),   # costosos → cost
    ('osas',       4),
    ('oso',        4),
    ('osa',        4),
    ('ivos',       4),   # relativos → relat
    ('ivas',       4),
    ('ivo',        4),
    ('iva',        4),
    ('les',        4),
    ('ueda',       4),   # busqueda → busc
    ('anza',       4),   # semejanza → semej
    ('eza',        4),   # dureza → dur
    ('eso',        4),   # proceso → proc, acceso → acc
    ('es',         4),   # clases → clas
    ('os',         3),   # datos → dat
    ('as',         3),   # tablas → tabl
    ('al',         4),   # funcional → funcion
]


# =============================================================================
# Sufijos INGLÉS — mayor a menor longitud (orden importa)
# =============================================================================

_SUFIJOS_EN = [
    # Nominalizations / derivations (longest first)
    ('izations',   5),   # implementations → implement
    ('ization',    5),   # organization → organiz
    ('ifications', 5),   # modifications → modif
    ('ification',  5),   # modification → modif
    ('ications',   5),   # applications → applic
    ('ication',    5),   # application → applic
    ('ations',     5),   # configurations → configur
    ('ation',      5),   # configuration → configur
    ('ments',      5),   # deployments → deploy
    ('ment',       5),   # deployment → deploy
    ('nesses',     5),   # businesses → busin
    ('ness',       4),   # business → busin
    ('ities',      4),   # capabilities → capabil
    ('ity',        4),   # capability → capabil
    ('ities',      4),
    # Participials / gerunds
    ('inging',     5),   # bringing → bring (edge case)
    ('tting',      5),   # setting → set (double consonant)
    ('nning',      5),   # running → run
    ('pping',      5),   # mapping → map
    ('essing',     4),   # processing → proc, addressing → addr
    ('ssing',      5),   # discussing → discu (fallback)
    ('ing',        4),   # searching → search, configuring → configur
    ('pped',       4),   # mapped → map
    ('tted',       4),   # committed → commit
    ('nned',       4),   # planned → plan
    ('ssed',       4),   # processed → process
    ('ied',        4),   # modified → modif
    ('ed',         4),   # configured → configur, searched → search
    # Plurals
    ('ies',        4),   # categories → categori
    ('ves',        4),   # leaves → leaf (approx)
    ('ses',        4),   # processes → process
    # Adjective / adverb derivations
    ('ically',     5),   # automatically → automat
    ('ically',     5),
    ('ally',       4),   # actually → actual
    ('ully',       4),   # fully → full (careful)
    ('ously',      4),   # continuously → continu
    ('ively',      4),   # effectively → effect
    ('ively',      4),
    ('able',       4),   # configurable → configur
    ('ible',       4),   # accessible → access
    ('ables',      4),
    ('ibles',      4),
    ('ous',        4),   # continuous → continu
    ('ive',        4),   # effective → effect
    ('ives',       4),
    ('ful',        4),   # powerful → power
    ('fuls',       4),
    ('less',       4),   # stateless → state
    ('ness',       4),
    ('ers',        4),   # processors → process
    ('er',         4),   # processor → process
    ('or',         4),   # processor (alt) → process
    ('ors',        4),
    ('ly',         4),   # quickly → quick
    ('al',         4),   # functional → function
    ('als',        4),
    # Simple plurals / verb forms
    ('ses',        4),   # processes → process
    ('ies',        4),   # queries → queri
    ('s',          4),   # nodes → node (solo si stem ≥ 4)
    # Trailing -e (configure → configur, store → stor, cache → cach)
    ('ory',        4),   # memory → memor, directory → director
    ('ories',      4),   # memories → memor, directories → director
    ('ory',        4),
    ('e',          4),   # configure → configur (stem ≥4 garantiza no cortar palabras cortas)
]


# =============================================================================
# Stemmer core
# =============================================================================

def _aplicar_sufijos(word: str, sufijos: list) -> str | None:
    """
    Prueba la lista de sufijos en orden.
    Retorna el stem si alguno aplica, None si ninguno aplica.
    """
    for sufijo, min_stem in sufijos:
        if word.endswith(sufijo) and len(word) - len(sufijo) >= min_stem:
            stem_result = word[:-len(sufijo)]
            if len(stem_result) >= 3:
                return stem_result
    return None


def stem(token: str) -> str:
    """
    Stemming bilingüe ES/EN automático.

    1. Normaliza (minúsculas + quitar acentos)
    2. Detecta idioma probable
    3. Aplica sufijos del idioma detectado primero
    4. Si no aplica, prueba el otro idioma

    Args:
        token: palabra (cualquier case, con/sin acentos)

    Returns:
        Stem reducido. Mínimo 3 caracteres.
        Colisiones ES/EN son intencionales (cross-language bridge).

    Ejemplos:
        stem('configurar')    → 'configur'
        stem('configuration') → 'configur'    ← mismo stem!
        stem('implementar')   → 'implement'
        stem('implementing')  → 'implement'   ← mismo stem!
        stem('búsqueda')      → 'busq'
        stem('searching')     → 'search'
        stem('memoria')       → 'memori'  (sin sufijo aplicable largo)
        stem('memory')        → 'memori'  ← via -ory? No, pero PMI los conecta
    """
    if not token or len(token) < 4:
        return token.lower() if token else token

    # Paso 1: normalizar siempre primero
    word = _quitar_acentos(token.lower())

    # Paso 2: detectar idioma y aplicar sufijos en orden prioritario
    if _es_espanol(token):
        result = _aplicar_sufijos(word, _SUFIJOS_ES)
        if result is None:
            result = _aplicar_sufijos(word, _SUFIJOS_EN)
    else:
        result = _aplicar_sufijos(word, _SUFIJOS_EN)
        if result is None:
            result = _aplicar_sufijos(word, _SUFIJOS_ES)

    return result if result is not None else word


# =============================================================================
# Utilidades públicas
# =============================================================================

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
        tokens_equivalentes('implement', 'implementar')   → True
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
    Jaccard con expansión morfológica bilingüe.
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
