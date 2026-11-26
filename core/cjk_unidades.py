"""Ojos Unicode para el NACIMIENTO de sinapsis en escrituras sin espacios (chino, japonés).

PROBLEMA (medido en el Paso 2b, UD PUD, 2026-11-25):
    Con las mismas ~839 frases reales por idioma, el motor creó 643 sinapsis en español,
    679 en inglés, 4 en chino y 0 en japonés. Las reglas automáticas de nacimiento no
    veían esas escrituras:
    - `core/sinapsis._tokenizar` (auto_vincular) solo acepta letras latinas;
    - `consolidation._auto_generar_co_ocurrencia` (sueño) usa `\\w{4,}`, que toma una
      corrida china entera («今晚我炒蒜和番茄配米饭») como UNA sola palabra, así que dos
      frases casi nunca comparten «palabras».

SOLUCIÓN (un solo cambio):
    Las corridas de ideogramas y kana se parten en bigramas de caracteres (la unidad
    estándar de recuperación para chino y japonés sin diccionario). Las reglas de
    nacimiento comparan esos bigramas igual que comparan palabras en un texto con
    espacios.

POR QUÉ ASÍ:
    - Sin listas de palabras ni diccionarios: la escritura se detecta por el nombre
      Unicode del carácter (ideogramas, hiragana, katakana).
    - Un texto sin caracteres CJK devuelve vacío, y `sin_cjk(texto)` lo devuelve tal
      cual: para español, inglés, etc. el motor queda idéntico por construcción.
    - Un bigrama SOLO de hiragana (した, ている, には…) es gramática, no contenido: no
      cuenta. Es una regla de escritura, no de vocabulario: lo mismo que hace la regla
      latina «4 letras o más» con «de», «la», «of», «the».
    - Una corrida de un solo ideograma o katakana es una unidad (庭, 车); una sola letra
      hiragana no (partícula).

Evidencia: docs/Mi neurona en el sistema/neurona_sinaptica_estrella/h1_nacimiento_cjk/
"""
import unicodedata

_PREFIJOS = ("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH", "HIRAGANA", "KATAKANA",
             "HALFWIDTH KATAKANA")  # el katakana de media anchura (ﾃｽﾄ) pasa a テスト con NFKC
MAX_TRIGRAMAS_FTS = 32


def _tipo(ch):
    """'h' hiragana, 'c' ideograma/katakana, None si no es escritura sin espacios."""
    if ch.isascii():
        return None
    nombre = unicodedata.name(ch, "")
    if not nombre.startswith(_PREFIJOS):
        return None
    return "h" if nombre.startswith("HIRAGANA") else "c"


def tiene_cjk(texto):
    return any(_tipo(ch) for ch in str(texto or ""))


def corridas(texto):
    """Corridas maximales de caracteres CJK (tras NFKC), en orden: [(texto, tipos)]."""
    texto = str(texto or "")
    if not tiene_cjk(texto):
        return []
    texto = unicodedata.normalize("NFKC", texto)
    out, actual, tipos = [], [], []
    for ch in texto:
        t = _tipo(ch)
        if t is None:
            if actual:
                out.append(("".join(actual), "".join(tipos)))
                actual, tipos = [], []
        else:
            actual.append(ch)
            tipos.append(t)
    if actual:
        out.append(("".join(actual), "".join(tipos)))
    return out


def unidades(texto):
    """Conjunto de unidades CJK: bigramas de cada corrida (salvo los solo-hiragana) y las
    corridas de un único ideograma/katakana. Vacío si el texto no tiene escritura CJK."""
    out = set()
    for run, tipos in corridas(texto):
        if len(run) == 1:
            if tipos != "h":
                out.add(run)
            continue
        for i in range(len(run) - 1):
            if tipos[i:i + 2] != "hh":
                out.add(run[i:i + 2])
    return out


def sin_cjk(texto):
    """El texto con cada carácter CJK cambiado por un espacio (idéntico si no hay CJK)."""
    texto = str(texto or "")
    if not tiene_cjk(texto):
        return texto
    return "".join(" " if _tipo(ch) else ch for ch in texto)


def trigramas_fts(texto, maximo=MAX_TRIGRAMAS_FTS):
    """Subcadenas CJK de 3 caracteres (para pedir candidatos al índice FTS5 trigram),
    sin repetir y como mucho `maximo`, saltando las que son solo hiragana."""
    out = []
    for run, tipos in corridas(texto):
        for i in range(len(run) - 2):
            if tipos[i:i + 3] == "hhh":
                continue
            g = run[i:i + 3]
            if g not in out:
                out.append(g)
                if len(out) >= maximo:
                    return out
    return out
