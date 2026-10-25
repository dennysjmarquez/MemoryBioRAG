#!/usr/bin/env python3
"""Diagnóstico de los fallos de la QA: ¿POR QUÉ falla cada caso? (solo lectura)

Lee scripts/casos_fallidos.jsonl (lo deja evaluar_qa.py / run_qa_suite.sh), copia la base
con la API de backup de SQLite a una carpeta temporal y, sobre ESA copia, repite cada
búsqueda fallida para clasificar la causa:

  ETIQUETA_VIEJA    la respuesta esperada ya no existe en esta base.
  FUERA_DEL_POOL    la respuesta ni siquiera está entre los 40 primeros: falla de recuperación.
  RECUERDO_NUEVO    le gana un recuerdo creado DESPUÉS del snapshot que tiene tantas o más
                    palabras de la pregunta: la pregunta se escribió antes de que existiera
                    (competencia legítima, no necesariamente un error del motor).
  RECUERDO_GIGANTE  le gana un recuerdo ≥ 4 veces más largo, con tantas o más palabras de
                    la pregunta: gana por volumen de texto, no por ser LA respuesta.
  ORDEN             la respuesta está entre los 40 primeros, pero la fórmula la pone abajo.
  HOY_PASA          en esta corrida sí aparece entre los 5 primeros.

La base original NUNCA se abre en modo escritura. La copia temporal se borra al final.

Uso:
  python3 scripts/diagnostico_fallos.py                       # usa BIORAG_PATH
  python3 scripts/diagnostico_fallos.py --db ruta/memoria.db --fallos scripts/casos_fallidos.jsonl
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(RAIZ, "snapshots", "qa_escape_qcr_20260811.db")
POOL = 40
FACTOR_GIGANTE = 4.0


def norm(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


_VACIAS = {"de", "la", "el", "en", "y", "a", "o", "que", "los", "las", "del", "se", "por", "un",
           "una", "con", "para", "es", "al", "lo", "le", "su", "mi", "no", "si", "como", "mas"}


def palabras(texto):
    return {w for w in re.findall(r"[a-z0-9ñ]{2,}", norm(texto).replace("_", " ").replace("-", " "))
            if w not in _VACIAS}


def copia_segura(origen, destino):
    src = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    dst = sqlite3.connect(destino)
    src.backup(dst)
    dst.close()
    src.close()


def fecha_corte_snapshot():
    if not os.path.exists(SNAPSHOT):
        return None, set()
    c = sqlite3.connect(f"file:{SNAPSHOT}?mode=ro&immutable=1", uri=True)
    corte = c.execute("SELECT MAX(creado_en) FROM largo_plazo").fetchone()[0]
    conceptos = {r[0] for r in c.execute("SELECT concepto FROM largo_plazo")}
    c.close()
    return corte, conceptos


def ficha(cur, concepto, q_palabras):
    fila = cur.execute(
        "SELECT concepto, COALESCE(sinonimos,''), COALESCE(contenido,''), creado_en, estado "
        "FROM largo_plazo WHERE concepto = ?", (concepto,)).fetchone()
    if not fila:
        return None
    texto = f"{fila[0]} {fila[1]} {fila[2]}"
    return {
        "concepto": fila[0],
        "largo": len(fila[2]),
        "creado": fila[3],
        "estado": fila[4],
        "palabras_de_la_pregunta": len(q_palabras & palabras(texto)),
    }


def fecha(ts):
    try:
        return datetime.date.fromtimestamp(float(ts)).isoformat()
    except (TypeError, ValueError):
        return "?"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=os.environ.get("BIORAG_PATH")
                    or os.path.join(RAIZ, "MemoryBioRAG_Data", "memory_biorag.db"))
    ap.add_argument("--fallos", default=os.path.join(RAIZ, "scripts", "casos_fallidos.jsonl"))
    ap.add_argument("--salida", default=os.path.join(RAIZ, "scripts", "diagnostico_fallos.json"))
    args = ap.parse_args()

    for ruta, que in ((args.db, "la base"), (args.fallos, "el archivo de fallos")):
        if not os.path.exists(ruta):
            sys.exit(f"No encuentro {que}: {ruta}")

    casos = {}
    for linea in open(os.path.join(RAIZ, "scripts", "casos_qa.jsonl"), encoding="utf-8"):
        d = json.loads(linea)
        casos[d["id"]] = d
    fallos = []
    for linea in open(args.fallos, encoding="utf-8"):
        d = json.loads(linea)
        if d.get("expected") and isinstance(d["expected"], str) and d.get("categoria") not in ("ambiguo", "negativo"):
            fallos.append(d)
    if not fallos:
        sys.exit("No hay fallos con respuesta esperada para diagnosticar.")

    tmp = tempfile.mkdtemp(prefix="biorag_diag_")
    copia = os.path.join(tmp, "copia.db")
    print(f"Copiando (solo lectura) {args.db}\n  → {copia}")
    copia_segura(args.db, copia)

    os.environ["BIORAG_PATH"] = copia
    os.environ["BIORAG_NO_LOG"] = "1"
    sys.path.insert(0, RAIZ)
    from core.memory_store import SQLiteMemoryBioRAG

    corte, del_snapshot = fecha_corte_snapshot()
    db = SQLiteMemoryBioRAG(copia)
    cur = db.cursor
    resultados, cuenta = [], {}
    try:
        for f in fallos:
            caso = casos.get(f["id"], {})
            query, oro, cat = f["query"], f["expected"], f["categoria"]
            q_pal = palabras(query)
            info = {"id": f["id"], "categoria": cat, "query": query, "oro": oro}
            oro_f = ficha(cur, oro, q_pal)
            if oro_f is None:
                info["causa"] = "ETIQUETA_VIEJA"
            else:
                # Igual que evaluar_qa.py: la respuesta esperada se activa antes de buscar.
                if cat != "dormido":
                    cur.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (oro,))
                    db.conn.commit()
                prof = "profundo" if (caso.get("deep") or cat == "dormido") else "activos"
                top5, _ = db.buscar_por_frase(query, profundidad=prof, limite=5, ignore_peso_sinaptico=True)
                pool, _ = db.buscar_por_frase(query, profundidad=prof, limite=POOL, ignore_peso_sinaptico=True)
                origen = db.last_origen_scores or {}
                n5 = [r[0] for r in top5]
                n40 = [r[0] for r in pool]
                ganadores = [x for x in (ficha(cur, c, q_pal) for c in n5[:3]) if x]
                for g in ganadores:
                    g["nuevo"] = bool(corte and g["creado"] and float(g["creado"]) > float(corte)
                                      and g["concepto"] not in del_snapshot)
                    g["origen"] = str(origen.get(g["concepto"], ""))[:30]
                info.update(oro_info=oro_f, puesto5=(n5.index(oro) + 1 if oro in n5 else None),
                            puesto40=(n40.index(oro) + 1 if oro in n40 else None), ganadores=ganadores)
                fuerte = [g for g in ganadores if g["concepto"] != oro
                          and g["palabras_de_la_pregunta"] >= oro_f["palabras_de_la_pregunta"]]
                if info["puesto5"]:
                    info["causa"] = "HOY_PASA"
                elif not info["puesto40"]:
                    info["causa"] = "FUERA_DEL_POOL"
                elif any(g["nuevo"] for g in fuerte):
                    info["causa"] = "RECUERDO_NUEVO"
                elif any(g["largo"] >= FACTOR_GIGANTE * max(oro_f["largo"], 1) for g in fuerte):
                    info["causa"] = "RECUERDO_GIGANTE"
                else:
                    info["causa"] = "ORDEN"
            cuenta[info["causa"]] = cuenta.get(info["causa"], 0) + 1
            resultados.append(info)
    finally:
        db.cerrar_sistema()
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 78)
    print("POR QUÉ FALLA CADA CASO")
    print("=" * 78)
    for r in resultados:
        print(f"\n[{r['id']}] {r['categoria']}  «{r['query']}»  →  causa: {r['causa']}")
        o = r.get("oro_info")
        if not o:
            print(f"   esperado: {r['oro']}  (NO existe en esta base)")
            continue
        print(f"   esperado: {o['concepto'][:55]}  | puesto {r['puesto40'] or '>40'} | "
              f"{o['palabras_de_la_pregunta']} palabras de la pregunta | {o['largo']} letras | {fecha(o['creado'])}")
        for i, g in enumerate(r["ganadores"], 1):
            marca = " (NUEVO)" if g["nuevo"] else ""
            print(f"   gana {i}: {g['concepto'][:55]}  | {g['palabras_de_la_pregunta']} palabras | "
                  f"{g['largo']} letras | {fecha(g['creado'])}{marca} | {g['origen']}")
    print("\n" + "=" * 78)
    print("RESUMEN")
    for causa, n in sorted(cuenta.items(), key=lambda x: -x[1]):
        print(f"   {causa:18s} {n}")
    print("=" * 78)
    with open(args.salida, "w", encoding="utf-8") as fh:
        json.dump({"base": args.db, "resumen": cuenta, "casos": resultados}, fh, ensure_ascii=False, indent=1)
    print(f"Detalle completo: {args.salida}  (la base original no se modificó)")


if __name__ == "__main__":
    main()
