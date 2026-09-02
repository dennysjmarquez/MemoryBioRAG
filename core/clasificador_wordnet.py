import os
import nltk
import re

# Configurar ruta local de nltk_data dentro del proyecto
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
local_nltk_dir = os.path.join(project_root, "MemoryBioRAG_Data", "nltk_data")
os.makedirs(local_nltk_dir, exist_ok=True)
if local_nltk_dir not in nltk.data.path:
    nltk.data.path.insert(0, local_nltk_dir)

# Asegurar que wordnet y omw-1.4 estén disponibles de forma local y silenciosa
try:
    from nltk.corpus import wordnet as wn
    # Lookup rápido de prueba bilingüe
    wn.synsets('error')
    try:
        wn.synsets('error', lang='spa')
    except (LookupError, Exception):
        try:
            nltk.download('omw-1.4', download_dir=local_nltk_dir, quiet=True)
            nltk.download('omw-2.0', download_dir=local_nltk_dir, quiet=True)
        except Exception:
            pass
except LookupError:
    try:
        nltk.download('wordnet', download_dir=local_nltk_dir, quiet=True)
        nltk.download('omw-1.4', download_dir=local_nltk_dir, quiet=True)
        nltk.download('omw-2.0', download_dir=local_nltk_dir, quiet=True)
    except Exception:
        pass
    from nltk.corpus import wordnet as wn


# Cache en memoria para evitar lookups repetidos
_cache_lexnames = {}

def clasificar_palabra(palabra):
    """Retorna set de lexnames para una palabra.
    Ej: 'error' → {'noun.act', 'noun.attribute', 'noun.cognition'}
    Si WordNet no reconoce la palabra, retorna set vacío.
    Bilingüe: busca en español primero, fallback a inglés."""
    key = palabra.lower().strip()
    if key in _cache_lexnames:
        return _cache_lexnames[key]

    synsets = []
    # Bilingüe: intentar español primero con protección contra LookupError (omw-1.4 vs omw-2.0)
    try:
        synsets = wn.synsets(key, lang='spa')
    except (LookupError, AttributeError, Exception):
        pass

    if not synsets:
        try:
            synsets = wn.synsets(key)
        except (LookupError, AttributeError, Exception):
            synsets = []

    lexnames = set(s.lexname() for s in synsets)
    _cache_lexnames[key] = lexnames
    return lexnames

def clasificar_texto(texto):
    """Extrae palabras significativas de un texto y las clasifica.
    Retorna dict {palabra: set(lexnames)}.
    Solo palabras de 3+ chars que WordNet reconoce."""
    palabras = set(re.findall(r'\w{3,}', texto.lower()))
    resultado = {}
    for p in palabras:
        lexnames = clasificar_palabra(p)
        if lexnames:  # Solo palabras reconocidas
            resultado[p] = lexnames
    return resultado

def obtener_lexnames_query(query, parafrasis=None):
    """Clasifica las palabras del query + paráfrasis.
    Retorna set plano de todos los lexnames encontrados."""
    texto = query
    if parafrasis:
        texto += " " + " ".join(parafrasis)
    clasificado = clasificar_texto(texto)
    todos = set()
    for lexnames in clasificado.values():
        todos |= lexnames
    return todos
