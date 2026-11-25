"""Ojos Unicode para palabras cortas en escrituras sin espacios (chino, japonés).

PROBLEMA (medido en el experimento 18, E1, 2026-11-25):
    `buscar_por_frase("番茄")` devolvía 0 resultados aunque dos recuerdos tenían «番茄»
    (tomate) en el contenido y en los sustantivos clave. Lo mismo con «消防» y «足球».
    La mayoría de las palabras chinas tienen 2 caracteres, y el motor no las veía:
    - el índice FTS5 `trigram` no puede buscar menos de 3 caracteres;
    - el índice `unicode61` toma una corrida CJK entera como una sola «palabra», así
      que «番茄*» solo encuentra textos donde la corrida EMPIEZA por 番茄.

SOLUCIÓN (un solo cambio):
    Si la consulta trae una corrida china o japonesa de 1–2 caracteres, el motor la
    busca como subcadena en concepto, sinónimos, sustantivos clave y contenido. Cada
    candidato recibe una puntuación de cobertura que depende SOLO de la consulta y de
    ese recuerdo (sin estadísticas del corpus: invariante al añadir recuerdos ajenos).

POR QUÉ ASÍ:
    - Sin listas de palabras ni diccionarios de idioma: la detección es por el
      nombre Unicode del carácter (ideogramas, hiragana, katakana).
    - Consultas sin escritura CJK: `terminos(...)` devuelve vacío y el motor no
      cambia en nada (identidad por construcción para español, inglés, etc.).
    - Corridas de 3 o más caracteres: ya las resuelve el trigram; no se tocan.
    - Una sola letra hiragana (の, は…) es partícula gramatical, no palabra: se omite
      para no traer medio corpus. Un ideograma o katakana suelto sí cuenta (庭, 车).

Evidencia: docs/Mi neurona en el sistema/ojos_unicode_busqueda/
"""
import unicodedata

from core.memory.stable_ranking import _FIELD_WEIGHTS, _MAX_FIELD_WEIGHT

MAX_TERMINOS = 8
TOPE_FILAS = 200

_PREFIJOS = ("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH", "HIRAGANA", "KATAKANA")


def _tipo(ch):
    """'h' hiragana, 'c' ideograma/katakana, None si no es escritura sin espacios."""
    nombre = unicodedata.name(ch, "")
    if not nombre.startswith(_PREFIJOS):
        return None
    return "h" if nombre.startswith("HIRAGANA") else "c"


def terminos(consulta):
    """Corridas CJK de 1–2 caracteres de la consulta (NFKC), sin repetir, como mucho 8."""
    texto = unicodedata.normalize("NFKC", str(consulta or ""))
    out, actual = [], []

    def cerrar():
        if not actual:
            return
        run = "".join(c for c, _ in actual)
        solo_hiragana = all(t == "h" for _, t in actual)
        if (len(run) == 2 or (len(run) == 1 and not solo_hiragana)) and run not in out:
            out.append(run)
        actual.clear()

    for ch in texto:
        t = _tipo(ch)
        if t is None:
            cerrar()
        else:
            actual.append((ch, t))
    cerrar()
    return tuple(out[:MAX_TERMINOS])


def _norm(texto):
    return unicodedata.normalize("NFKC", str(texto or "")).casefold()


def cobertura(terms, concepto, contenido, sinonimos="", sustantivos_clave=""):
    """Puntuación [0, 1] con la misma forma que `CorpusIndependentLexicalRanker.score`:
    0.65 cobertura de la unión + 0.20 mejor campo + 0.15 campos ponderados."""
    if not terms:
        return 0.0
    campos = tuple(_norm(t) for t in (concepto, contenido, sinonimos, sustantivos_clave))
    n = len(terms)
    por_campo = [sum(t in c for t in terms) / n for c in campos]
    union = sum(any(t in c for c in campos) for t in terms) / n
    ponderada = min(1.0, sum(w * cov for (_, w), cov in zip(_FIELD_WEIGHTS, por_campo)) / _MAX_FIELD_WEIGHT)
    return round(min(1.0, 0.65 * union + 0.20 * max(por_campo) + 0.15 * ponderada), 8)


def filas(cursor, terms, where_sql, params, sustantivos_select, tope=TOPE_FILAS):
    """Recuerdos que contienen algún término (subcadena), con las columnas del pool FTS.

    `where_sql` son los mismos filtros de la búsqueda (estado, categoría, fechas,
    límite estable de rowid). Orden por rowid y tope fijo, como los demás fallbacks.
    """
    if not terms:
        return []
    columnas = ["l.concepto", "COALESCE(l.sinonimos, '')", "COALESCE(l.contenido, '')"]
    if sustantivos_select != "''":  # bases legacy sin la columna
        columnas.append("COALESCE(l.sustantivos_clave, '')")
    conds = []
    args = []
    for t in terms:
        conds.append("(" + " OR ".join(f"instr({c}, ?) > 0" for c in columnas) + ")")
        args.extend([t] * len(columnas))
    sql = ("SELECT l.rowid, l.concepto, l.contenido, l.peso_sinaptico, l.estado, l.asociaciones, "
           f"COALESCE(l.sinonimos, ''), {sustantivos_select} FROM largo_plazo l WHERE ("
           + " OR ".join(conds) + ")" + (f" AND {where_sql}" if where_sql else "")
           + " ORDER BY l.rowid LIMIT ?")
    cursor.execute(sql, tuple(args) + tuple(params) + (int(tope),))
    return cursor.fetchall()
