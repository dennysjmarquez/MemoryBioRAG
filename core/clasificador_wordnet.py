import os
from pathlib import Path
import nltk
import re

# WordNet vive en el directorio del usuario: los wheels pueden instalarse en un
# site-packages de solo lectura. Se conserva la ruta del repositorio como fallback
# para instalaciones existentes.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
local_nltk_dir = str(
    Path(os.environ.get("BIORAG_NLTK_DATA", str(Path.home() / ".biorag" / "nltk_data")))
    .expanduser()
)
legacy_nltk_dir = str(Path(project_root) / "MemoryBioRAG_Data" / "nltk_data")
if local_nltk_dir not in nltk.data.path:
    nltk.data.path.insert(0, local_nltk_dir)
if legacy_nltk_dir not in nltk.data.path:
    nltk.data.path.append(legacy_nltk_dir)

_auto_download = os.environ.get("BIORAG_NLTK_AUTO_DOWNLOAD", "1").strip().lower() not in {
    "0", "false", "no", "off"
}

# El instalador puede descargar los corpus explícitamente. La descarga automática
# se conserva por compatibilidad, pero es desactivable para entornos aislados.
try:
    from nltk.corpus import wordnet as wn
    try:
        wn.synsets("error")
        try:
            wn.synsets("error", lang="spa")
        except Exception:
            if _auto_download:
                try:
                    nltk.download("omw-1.4", download_dir=local_nltk_dir, quiet=True)
                    nltk.download("omw-2.0", download_dir=local_nltk_dir, quiet=True)
                except Exception:
                    pass
    except LookupError:
        if _auto_download:
            try:
                nltk.download("wordnet", download_dir=local_nltk_dir, quiet=True)
                nltk.download("omw-1.4", download_dir=local_nltk_dir, quiet=True)
                nltk.download("omw-2.0", download_dir=local_nltk_dir, quiet=True)
            except Exception:
                pass
except ImportError:
    # NLTK es una dependencia declarada, pero importar el motor debe seguir
    # siendo posible si un entorno mínimo aún no la instaló.
    wn = None


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
