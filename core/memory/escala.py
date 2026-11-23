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

Interruptor: BIORAG_ESCALA=0 desactiva estas ayudas de escala; no revierte por sí solo todo el buscador a una versión anterior.
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


def palabras_desconocidas(cursor, tokens, *, baseline_rowid=None) -> list[str]:
    """Palabras de la pregunta que la memoria conoce en ≤ el umbral de recuerdos.

    Si se proporciona ``baseline_rowid``, la frecuencia se mide sobre el corpus
    de referencia, no sobre las altas posteriores. Se consultan los postings del
    índice ``unicode61`` con ``LIMIT df_max + 1``: el trabajo queda acotado por el
    umbral y no recorre filas ni recalcula el vocabulario del corpus durante la
    búsqueda. Sin límite explícito se conserva la compatibilidad con la API previa.
    """
    candidatas = [str(t) for t in tokens if len(str(t)) >= 3 and not str(t).isdigit()]
    if not candidatas:
        return []
    df_max = _df_max_rara()

    if baseline_rowid is not None:
        raras = []
        try:
            for token in candidatas:
                normalizado = _sin_tildes(token)
                match = '"' + normalizado.replace('"', '""') + '"'
                filas = cursor.execute(
                    "SELECT 1 FROM largo_plazo_fts_unicode "
                    "WHERE largo_plazo_fts_unicode MATCH ? AND rowid <= ? LIMIT ?",
                    (match, int(baseline_rowid), df_max + 1),
                ).fetchall()
                if len(filas) <= df_max:
                    raras.append(token)
            return raras
        except sqlite3.Error:
            # No usar la frecuencia global como fallback: produciría de nuevo
            # una decisión dependiente de las filas añadidas después del corte.
            return []

    if not _asegurar_vocab(cursor):
        return []
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
                        limite: int, *, baseline_rowid=None):
    """Los `limite` recuerdos más parecidos a la pregunta por trigramas (typo-tolerante),
    respetando el mismo filtro de estado/categoría. Devuelve None cuando la memoria
    entera cabe en la ventana: el llamador usa entonces su consulta de siempre."""
    try:
        # Solo hace falta distinguir <= límite de > límite. LIMIT corta la
        # comprobación tras límite+1 filas; no se cuenta el corpus completo.
        probe_limit = max(1, int(limite) + 1)
        muestra = cursor.execute(
            f"SELECT 1 FROM largo_plazo l {where_extra} LIMIT ?",
            tuple(params_extra) + (probe_limit,),
        ).fetchall()
    except (sqlite3.Error, TypeError, ValueError):
        return None
    if len(muestra) <= int(limite):
        return None
    grams = _trigramas(query)
    if not grams:
        return None
    match = " OR ".join(f'"{g}"' for g in grams)
    cond = where_extra.replace("WHERE", "AND", 1) if where_extra.strip() else ""
    cond = cond.replace("rowid <=", "l.rowid <=")
    fts_table = "largo_plazo_fts"
    if baseline_rowid is not None:
        try:
            from core.memory.growth_stable_fts import REFERENCE_FTS
            exists = cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
                (REFERENCE_FTS,),
            ).fetchone()
            if exists:
                fts_table = REFERENCE_FTS
        except sqlite3.Error:
            pass
    try:
        filas = cursor.execute(
            f"SELECT l.rowid FROM {fts_table} f CROSS JOIN largo_plazo l "
            f"ON l.rowid = f.rowid WHERE {fts_table} MATCH ? {cond} "
            f"ORDER BY bm25({fts_table}) LIMIT ?",
            (match,) + tuple(params_extra) + (limite,),
        ).fetchall()
    except sqlite3.Error:
        return None
    return [r[0] for r in filas]
