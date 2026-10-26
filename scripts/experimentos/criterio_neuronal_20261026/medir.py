#!/usr/bin/env python3
"""¿Dónde le falta criterio al sistema? Mediciones de solo lectura sobre una base BioRAG.

POR QUÉ existe: antes de proponer una neurona hay que probar con números que en ese
punto una regla fija decide mal. Este script mide dos puntos candidatos:

  1. Enlaces por alias (core/sinapsis.py `vincular_por_sinonimos`): al guardar un
     recuerdo con alias, se crea un enlace fuerte (0.9, tipo protegido) hacia TODO
     recuerdo cuyo nombre o alias CONTIENE ese texto (LIKE %alias%). Mide cuántos
     enlaces hay, cuántos salen de alias cortos o masivos, cuántos coinciden como
     palabra entera y cuántos salen de recuerdos que ya no existen.
  2. Vigencia ("¿cuál es la última versión de X?"): si se pasa --consultas, busca
     en una COPIA de la base y muestra el top-5 con la fecha de cada recuerdo.

USO (la base nunca se modifica: la parte 1 abre en solo lectura y la 2 usa una copia):
  python scripts/experimentos/criterio_neuronal_20261026/medir.py --db RUTA.db
  python scripts/experimentos/criterio_neuronal_20261026/medir.py --db RUTA.db \
      --consultas "¿cuál es la última versión de biorag?" "biorag latest version"
"""
from __future__ import annotations

import argparse
import collections
import datetime
import os
import re
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def medir_enlaces_por_alias(db: str) -> None:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    nodos = {c: (c.lower(), (s or "").lower()) for c, s in
             con.execute("SELECT concepto, sinonimos FROM largo_plazo")}
    alias = {c: [t.strip().lower() for t in (s or "").split(",") if t.strip()]
             for c, s in con.execute("SELECT concepto, sinonimos FROM largo_plazo")}
    total = con.execute("SELECT COUNT(*) FROM sinapsis").fetchone()[0]
    enlaces = con.execute(
        "SELECT origen, destino FROM sinapsis WHERE tipo = 'sinonimo_explicito'").fetchall()

    alcance: dict[str, int] = {}

    def alcanza(t: str) -> int:
        if t not in alcance:
            alcance[t] = sum(1 for n, s in nodos.values() if t in n or t in s)
        return alcance[t]

    huerfanos = explicados = cortos = masivos = palabra_entera = 0
    for a, b in enlaces:
        if a not in nodos or b not in nodos:
            huerfanos += 1
            continue
        n, s = nodos[b]
        ts = [t for t in alias[a] if t in n or t in s]
        if not ts:
            continue
        explicados += 1
        t = min(ts, key=alcanza)
        cortos += len(t) <= 3
        masivos += alcanza(t) >= 20
        texto = n + " , " + s
        palabra_entera += any(
            re.search(r"(^|[\s,_\-])" + re.escape(x) + r"($|[\s,_\-])", texto) for x in ts)

    grado = collections.Counter()
    for a, b in con.execute("SELECT origen, destino FROM sinapsis"):
        grado[a] += 1
        grado[b] += 1
    v = sorted(grado.values())
    top = sorted({(alcanza(t), t) for ts in alias.values() for t in ts}, reverse=True)[:8]
    con.close()

    print("1) ENLACES POR ALIAS (tipo 'sinonimo_explicito', peso 0.9, protegido)")
    print(f"   recuerdos={len(nodos)}  sinapsis totales={total}")
    print(f"   enlaces por alias={len(enlaces)} ({100 * len(enlaces) / max(1, total):.1f} % del grafo)")
    print(f"   con un extremo que ya no existe={huerfanos}")
    print(f"   explicados por la regla actual (el alias está CONTENIDO en el otro)={explicados}")
    print(f"     - por un alias de 3 letras o menos={cortos}")
    print(f"     - por un alias que alcanza 20 recuerdos o más={masivos}")
    print(f"     - donde el alias coincide como PALABRA ENTERA={palabra_entera}")
    print(f"   enlaces por recuerdo: mediana={v[len(v) // 2]}  p90={v[int(len(v) * .9)]}  máximo={v[-1]}")
    print("   alias con más alcance (cuántos recuerdos lo CONTIENEN):",
          ", ".join(f"'{t}'={n}" for n, t in top))


def medir_vigencia(db: str, consultas: list[str]) -> None:
    sys.path.insert(0, RAIZ)
    tmp = tempfile.mkdtemp(prefix="vigencia_")
    copia = os.path.join(tmp, "copia.db")
    shutil.copy(db, copia)
    os.environ["BIORAG_PATH"] = copia
    from core.memory_store import SQLiteMemoryBioRAG

    con = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
    fecha = {c: datetime.datetime.fromtimestamp(t or 0).strftime("%Y-%m-%d")
             for c, t in con.execute("SELECT concepto, creado_en FROM largo_plazo")}
    con.close()
    mem = SQLiteMemoryBioRAG(db_path=copia)
    print("\n2) VIGENCIA (búsqueda en una copia; la base original no se toca)")
    for q in consultas:
        res, _ = mem.buscar_por_frase(q, limite=5)
        print(f"   >> {q}")
        for i, r in enumerate(res[:5], 1):
            print(f"      {i}. {r[4]:.3f}  {fecha.get(r[0], '?')}  {r[0][:70]}")
    shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--consultas", nargs="*", default=[])
    a = p.parse_args()
    medir_enlaces_por_alias(a.db)
    if a.consultas:
        medir_vigencia(a.db, a.consultas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
