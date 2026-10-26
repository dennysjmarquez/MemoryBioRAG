"""Invariancia de escala del buscador (v35.1).

POR QUÉ EXISTE (experimento 2026-10-25, scripts/experimentos/escala_recall_20261025/):
con las MISMAS 921 preguntas y las MISMAS respuestas, agregar recuerdos del mismo
tema a una copia del snapshot bajaba el Recall@5 de 100 % a ~98 %. No porque los
recuerdos nuevos le ganaran a la respuesta (en 10 de 13 casos el que ganó era un
recuerdo VIEJO), sino porque dos decisiones del buscador dependían del tamaño:

1. El rescate de typos/variantes (fallback simbólico 2.1) solo corría si NINGÚN
   candidato cubría ≥ 60 % de la pregunta. Con más recuerdos es más probable que
   alguno, ajeno a la respuesta, la cubra: el rescate se apagaba para todos y el
   filtro QCR eliminaba después a la respuesta (sus palabras vienen mal escritas).
   → Aquí la decisión pasa a depender de la PREGUNTA: si trae palabras que la
     memoria no conoce o casi no conoce (en ≤ 1 recuerdo: typo o variante), el
     rescate corre. Lo que tengan otros recuerdos ya no lo apaga.

2. Las ventanas de candidatos de los rescates miraban los PRIMEROS recuerdos
   guardados (`LIMIT 1000` sin orden y `ORDER BY rowid LIMIT 200`). Con una
   memoria de más de 1000 recuerdos, los más nuevos quedaban invisibles.
   → Aquí la ventana mira los MÁS PARECIDOS (índice trigram, el mismo que ya usa
     el motor), con el mismo tamaño. Si la memoria cabe entera en la ventana, la
     consulta es exactamente la de antes (byte-idéntico: cero riesgo en memorias
     chicas).

Coste constante: una consulta al vocabulario por palabra (índice FTS5) y una
consulta trigram acotada por el mismo LIMIT que ya existía.

Interruptor: BIORAG_ESCALA=0 vuelve al comportamiento anterior.
"""
from __future__ import annotations

import os
import re
import sqlite3
import unicodedata

_VOCAB = "biorag_vocab_unicode"


def activa() -> bool:
    return os.environ.get("BIORAG_ESCALA", "1") != "0"


def _sin_tildes(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def sin_tildes(texto: str) -> str:
    """Minúsculas sin tildes (misma normalización que el índice unicode61)."""
    return _sin_tildes(texto)


def _asegurar_vocab(cursor) -> bool:
    """Vista de vocabulario sobre el índice unicode61 existente, en el esquema TEMP
    de la conexión (no escribe nada en la base)."""
    try:
        cursor.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS temp.{_VOCAB} "
            f"USING fts5vocab(main, 'largo_plazo_fts_unicode', 'row')"
        )
        return True
    except sqlite3.Error:
        return False


def _df_max_rara() -> int:
    try:
        return max(0, int(os.environ.get("BIORAG_ESCALA_DF_RARA", "1")))
    except ValueError:
        return 1


def palabras_desconocidas(cursor, tokens) -> list[str]:
    """Palabras de la pregunta (normalizadas, ≥ 3 letras, no solo dígitos) que la memoria
    no conoce o casi no conoce: aparecen en ≤ BIORAG_ESCALA_DF_RARA recuerdos (1).

    Por qué «≤ 1» y no «0»: un typo es personal; como mucho aparece en la nota que lo
    cita (p. ej. un recuerdo sobre fallos de la QA), y esa frecuencia NO crece con la
    memoria. Las palabras reales sí: en el snapshot «memoria» está en 180 recuerdos.
    Medido: typos con frecuencia 0 en el snapshot y 1 en una memoria que los cita.
    Si algo falla, devuelve [] (= comportamiento anterior)."""
    candidatas = [t for t in tokens if len(t) >= 3 and not t.isdigit()]
    if not candidatas or not _asegurar_vocab(cursor):
        return []
    df_max = _df_max_rara()
    raras = []
    try:
        for t in candidatas:
            fila = cursor.execute(
                f"SELECT doc FROM temp.{_VOCAB} WHERE term = ? LIMIT 1", (t,)
            ).fetchone()
            if fila is None or int(fila[0]) <= df_max:
                raras.append(t)
    except sqlite3.Error:
        return []
    return raras


def _trigramas(query: str) -> list[str]:
    vistos, out = set(), []
    for forma in {(query or "").lower(), _sin_tildes(query)}:
        for w in re.findall(r"\w{3,}", forma.replace("_", " ")):
            for i in range(len(w) - 2):
                g = w[i:i + 3]
                if g not in vistos and '"' not in g:
                    vistos.add(g)
                    out.append(g)
    return out


def rowids_por_parecido(cursor, query: str, where_extra: str, params_extra: tuple,
                        limite: int):
    """Los `limite` recuerdos más parecidos a la pregunta por trigramas (typo-tolerante),
    respetando el mismo filtro de estado/categoría. Devuelve None cuando la memoria
    entera cabe en la ventana: el llamador usa entonces su consulta de siempre."""
    try:
        total = cursor.execute(
            f"SELECT COUNT(*) FROM largo_plazo l {where_extra}", params_extra
        ).fetchone()[0]
    except sqlite3.Error:
        return None
    if total <= limite:
        return None
    grams = _trigramas(query)
    if not grams:
        return None
    match = " OR ".join(f'"{g}"' for g in grams)
    cond = where_extra.replace("WHERE", "AND", 1) if where_extra.strip() else ""
    try:
        filas = cursor.execute(
            "SELECT l.rowid FROM largo_plazo_fts f CROSS JOIN largo_plazo l "
            f"ON l.rowid = f.rowid WHERE largo_plazo_fts MATCH ? {cond} "
            "ORDER BY bm25(largo_plazo_fts) LIMIT ?",
            (match,) + tuple(params_extra) + (limite,),
        ).fetchall()
    except sqlite3.Error:
        return None
    return [r[0] for r in filas]
