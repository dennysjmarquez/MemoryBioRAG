#!/usr/bin/env python3
"""¿Sirve el léxico externo (WordNet / tesauro) para cruzar el abismo léxico?

Mide tres cosas, sin tocar el motor:
  1. CUÁNTA cobertura real tiene el léxico externo sobre el vocabulario de las
     921 consultas canónicas (no sobre palabras de diccionario: sobre las que
     la gente escribe de verdad).
  2. CUÁNTA contaminación cruzada hay: palabras españolas que caen al inglés.
  3. Si el léxico alcanza el NODO ESPERADO en los 3 casos de EXP-Q, que es
     abismo léxico puro (cero solapamiento de raíces con el recuerdo).

Uso:
    python scripts/experimento_lexico_externo.py
    python scripts/experimento_lexico_externo.py --tesauro /ruta/th_es_v2.dat

El tesauro es opcional: RLA-ES (sbosio/rla-es), LGPL 2.1, ~2.8 MB, UTF-8 con
cabecera ISO8859-1 (el contenido SÍ es UTF-8). No se guarda en el repo.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import nltk  # noqa: E402

nltk.data.path.insert(0, str(RAIZ / "MemoryBioRAG_Data" / "nltk_data"))

from nltk.corpus import wordnet as wn  # noqa: E402
from core.stopwords import STOPWORDS_ES  # noqa: E402

DB = RAIZ / "snapshots" / "qa_escape_qcr_20260811.db"
CASOS = RAIZ / "scripts" / "casos_qa_baseline_v1.jsonl"

# Los 3 casos de EXP-Q: consulta -> recuerdo esperado. Cero raíces en común.
EXP_Q = [
    ("comprobacion fidedigna de ficheros previo a emitir dictamenes",
     "regla_verificar_codigo_real_antes_de_diagnostico"),
    ("resolucion de colisiones valorativas en bifurcaciones",
     "ajuste_tejedora_valencia_desempate_fase1"),
    ("panel visual de desarrollo para despacho de tareas",
     "kilo_vscode_extension_principal"),
]


def plano(w):
    """Sin tildes, minúsculas. WordNet español guarda CON tilde; las consultas
    se escriben SIN tilde. Este es el desajuste que se mide aquí."""
    return "".join(c for c in unicodedata.normalize("NFD", w.lower())
                   if unicodedata.category(c) != "Mn")


def variantes(w):
    """Formas plausibles de una palabra tal como la escribe la gente."""
    v = {w, w.rstrip("s")}
    if w.endswith("es"):
        v.add(w[:-2])
    return v


def cargar_tesauro(ruta):
    """RLA-ES: cabecera `palabra|n` y líneas `-|sin1|sin2|...` por sinónimos."""
    tes, cabeza = {}, None
    with open(ruta, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("ISO"):
                continue
            if ln.startswith("-|"):
                if cabeza:
                    for s in ln[2:].split("|"):
                        s = s.strip()
                        if s and s != cabeza:
                            tes.setdefault(plano(cabeza), set()).add(plano(s))
            else:
                cabeza = ln.split("|")[0].strip()
    return tes


def cobertura(palabras, fuente):
    return 100.0 * sum(1 for w in palabras
                       if any(plano(v) in fuente for v in variantes(w))) / len(palabras)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tesauro", help="ruta a th_es_v2.dat (opcional)")
    args = ap.parse_args()

    qs = [json.loads(l)["query"] for l in open(CASOS, encoding="utf-8") if l.strip()]
    palabras = {w for q in qs for w in re.findall(r"\w{3,}", q.lower())
                if w not in STOPWORDS_ES}
    print(f"Consultas: {len(qs)}   palabras de contenido distintas: {len(palabras)}\n")

    # ── 1. ¿Cuánto cubre WordNet español, y cuánto cae al inglés? ──
    spa = eng = nada = 0
    caen = []
    for w in palabras:
        if any(wn.synsets(plano(v), lang="spa") or wn.synsets(v, lang="spa")
               for v in variantes(w)):
            spa += 1
        elif any(wn.synsets(v) for v in variantes(w)):
            eng += 1
            caen.append(w)
        else:
            nada += 1
    tot = len(palabras)
    print("WORDNET (wordnet.zip inglés + omw-1.4.zip español)")
    print(f"  resuelve por español : {spa:>5}  ({100*spa/tot:5.1f} %)")
    print(f"  cae a INGLÉS         : {eng:>5}  ({100*eng/tot:5.1f} %)   <- sin detección de idioma")
    print(f"  no está             : {nada:>5}  ({100*nada/tot:5.1f} %)")
    print(f"  muestra de las que caen al inglés: {sorted(caen)[:15]}\n")

    # ── 2. Tesauro, si se pidió ──
    tes = {}
    if args.tesauro:
        tes = cargar_tesauro(args.tesauro)
        print(f"TESAURO RLA-ES: {len(tes)} entradas")
        print(f"  cobertura            : {cobertura(palabras, tes):5.1f} %\n")

    # ── 3. EXP-Q: ¿el léxico alcanza el nodo esperado? ──
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    print("EXP-Q — ¿alguna expansión léxica toca el nodo esperado?")
    for q, nodo in EXP_Q:
        r = conn.execute("SELECT concepto, contenido, sinonimos FROM largo_plazo "
                         "WHERE concepto = ?", (nodo,)).fetchone()
        if not r:
            print(f"  «{q[:44]}» -> el nodo no está en el snapshot")
            continue
        destino = {plano(x) for x in re.findall(r"\w{3,}", " ".join(x or "" for x in r))}
        toks = [t for t in re.findall(r"\w{3,}", q.lower()) if t not in STOPWORDS_ES]
        filas = []
        for t in toks:
            wn_exp = set()
            for v in variantes(t):
                for s in wn.synsets(v, lang="spa")[:3]:
                    for l in s.lemmas(lang="spa"):
                        wn_exp.add(plano(l.name().replace("_", " ")))
            tes_exp = set()
            for v in variantes(t):
                tes_exp |= tes.get(plano(v), set())
            filas.append((t, sorted(wn_exp & destino), sorted(tes_exp & destino)))
        toc_wn = sum(1 for _, a, _ in filas if a)
        toc_te = sum(1 for _, _, b in filas if b)
        print(f"  «{q[:44]}»  ({len(toks)} palabras)")
        for t, a, b in filas:
            print(f"     {t:<13} wordnet:{'TOCA' if a else '  - ':>5} {a[:2] if a else ''}"
                  f"   tesauro:{'TOCA' if b else '  - ':>6} {b[:2] if b else ''}")
        print(f"     -> wordnet alcanza {toc_wn}/{len(toks)} · tesauro alcanza {toc_te}/{len(toks)}")


if __name__ == "__main__":
    main()
