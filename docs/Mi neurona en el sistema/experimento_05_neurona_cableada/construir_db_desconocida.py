"""Datos que el motor NUNCA vio: DB nueva desde cero con la doc de Python en español.

Fuente: https://github.com/python/python-docs-es (clonado con --depth 1).
  - FAQ (faq/*.po): cada pregunta/respuesta es un recuerdo. El recuerdo guarda
    SOLO la respuesta y se nombra con las palabras más distintivas de la
    respuesta (tf-idf), NO con la pregunta. La pregunta escrita por humanos
    queda como examen: no sale de nuestro generador, así no hay "enseñar para
    el examen".
  - Glosario (glossary.po): cada término es un recuerdo más (distractores reales).

La DB se construye como la construiría un usuario: `memory_service.aprender`
uno por uno (cada consolidación dispara el aprendizaje en vivo de la neurona) y
un ciclo de sueño cada 50 recuerdos. Arranca VACÍA: sin pesos, sin examen.

Uso:
  python construir_db_desconocida.py --docs /ruta/python-docs-es --db /ruta/nueva.db \
      --examen examen_humano.jsonl --traza construccion.jsonl
"""
import argparse
import glob
import json
import math
import os
import random
import re
import sys
import time
import unicodedata
from collections import Counter

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
os.environ["BIORAG_NO_LOG"] = "1"

from core.stopwords import STOPWORDS  # noqa: E402


def limpiar(t):
    t = re.sub(r":[a-z:]+:`([^`<]*?)(\s*<[^>]*>)?`", r"\1", t)
    t = t.replace("``", "").replace("`", "")
    return re.sub(r"\s+", " ", t).strip()


def slug(t, maxlen=60):
    t = t.lower().replace("ñ", "\0")
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").replace("\0", "ñ")
    t = re.sub(r"[^a-z0-9ñ]+", "_", t).strip("_")
    return t[:maxlen].strip("_")


def tokens(t):
    return [w for w in re.findall(r"[a-záéíóúñü0-9]{3,}", t.lower()) if w not in STOPWORDS]


def leer_faq(docs):
    import polib
    pares = []
    for f in sorted(glob.glob(os.path.join(docs, "faq", "*.po"))):
        actual = None
        for e in polib.pofile(f):
            if e.obsolete or not e.msgstr:
                continue
            if e.msgid.strip().endswith("?") and len(e.msgid) < 200:
                if actual and len(actual["respuesta"]) >= 120:
                    pares.append(actual)
                actual = dict(seccion=os.path.basename(f)[:-3], pregunta=limpiar(e.msgstr), respuesta="")
            elif actual is not None and len(actual["respuesta"]) < 3000:
                actual["respuesta"] += " " + limpiar(e.msgstr)
        if actual and len(actual["respuesta"]) >= 120:
            pares.append(actual)
    return pares


def leer_glosario(docs):
    import polib
    terminos, actual = [], None
    for e in polib.pofile(os.path.join(docs, "glossary.po")):
        if e.obsolete or not e.msgstr:
            continue
        corto = len(e.msgid) < 45 and not e.msgid.rstrip().endswith((".", ":")) and "``" not in e.msgid
        if corto:
            if actual and len(actual["contenido"]) >= 80:
                terminos.append(actual)
            actual = dict(termino=limpiar(e.msgstr), contenido="")
        elif actual is not None and len(actual["contenido"]) < 2500:
            actual["contenido"] += " " + limpiar(e.msgstr)
    if actual and len(actual["contenido"]) >= 80:
        terminos.append(actual)
    return terminos


def nombrar_por_respuesta(pares):
    df = Counter()
    for p in pares:
        df.update(set(tokens(p["respuesta"])))
    n = len(pares)
    usados = set()
    for p in pares:
        tk = tokens(p["respuesta"])
        tf = Counter(tk)
        prim = {}
        for i, w in enumerate(tk):
            prim.setdefault(w, i)
        top = sorted(tf, key=lambda w: -tf[w] * math.log(n / df[w]))[:4]
        nombre = slug("_".join(sorted(top, key=lambda w: prim[w])))
        while nombre in usados:
            nombre += "_b"
        usados.add(nombre)
        p["concepto"] = nombre
    return pares


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--examen", required=True)
    ap.add_argument("--traza", required=True)
    ap.add_argument("--sueno-cada", type=int, default=50)
    a = ap.parse_args()
    if os.path.exists(a.db):
        sys.exit(f"{a.db} ya existe: este script crea una DB NUEVA.")

    faq = nombrar_por_respuesta(leer_faq(a.docs))
    glos = leer_glosario(a.docs)
    nombres = {p["concepto"] for p in faq}
    nodos = [dict(concepto=p["concepto"], contenido=p["respuesta"].strip(), categoria="General")
             for p in faq]
    for t in glos:
        c = slug(t["termino"])
        if c and c not in nombres and c != "glosario":
            nombres.add(c)
            nodos.append(dict(concepto=c, contenido=t["contenido"].strip(), categoria="General"))
    random.Random(5).shuffle(nodos)
    with open(a.examen, "w", encoding="utf-8") as f:
        for p in faq:
            f.write(json.dumps(dict(query=p["pregunta"], esperado=p["concepto"], seccion=p["seccion"]),
                               ensure_ascii=False) + "\n")
    print(f"FAQ {len(faq)} preguntas humanas, glosario {len(glos)} términos, {len(nodos)} recuerdos", flush=True)

    from core import memory_service
    from core.memory import neurona
    from core.memory_store import SQLiteMemoryBioRAG

    db = SQLiteMemoryBioRAG(db_path=os.path.abspath(a.db))
    t0 = time.time()
    with open(a.traza, "w", encoding="utf-8") as f:
        for i, n in enumerate(nodos, 1):
            t1 = time.time()
            memory_service.aprender(db, n["concepto"], n["contenido"], categoria=n["categoria"])
            fila = dict(n=i, ms_aprender=round((time.time() - t1) * 1000),
                        neurona=neurona.estado(db).stats.get("ultimo", {}))
            if a.sueno_cada and i % a.sueno_cada == 0:
                t2 = time.time()
                db.ciclo_sueno_consolidacion()
                fila["ms_sueno"] = round((time.time() - t2) * 1000)
                fila["neurona_sueno"] = neurona.estado(db).stats.get("ultimo", {})
            f.write(json.dumps(fila, ensure_ascii=False, default=float) + "\n")
            f.flush()
        db.ciclo_sueno_consolidacion()
    print(f"listo en {time.time() - t0:.0f}s", json.dumps(neurona.resumen(db), ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
