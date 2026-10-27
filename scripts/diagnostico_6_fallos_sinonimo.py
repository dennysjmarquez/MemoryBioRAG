#!/usr/bin/env python3
"""Diagnóstico de los 6 fallos de `sinonimo`. SOLO LEE: no cambia el motor.

POR QUÉ existe: la neurona de ranking solo reordena el top-5 (search.py:2288), así
que no puede arreglar un caso cuyo recuerdo correcto está en el puesto 9, 18 o 21.
Antes de proponer nada hay que separar dos cosas que se estaban mezclando:

  A) palabras SUELTAS y genéricas (perfil, metodología, agente, regla, cv): las
     declaran decenas de recuerdos. Con una sola palabra nadie —ni una persona—
     sabe cuál se quiere. Empate legítimo, no fallo forzable.
  B) alias ESPECÍFICOS (filtro-arquitecto-prolijo): si falla, es un fallo real.

CONDICIONES: replican `evaluar_qa.py` al pie de la letra.
  - antes de preguntar, el nodo esperado se pone en 'activo' (para `dormido`, en
    'dormido'), igual que el setup de la QA;
  - `profundidad='activos'`, `limite=5`, `ignore_peso_sinaptico=True`;
  - el estado de los nodos se restaura después de cada caso (la QA hace lo mismo
    con `_restaurar_estado_nodos`: sin eso cada caso hereda el anterior).
  - PYTHONHASHSEED=1 (regla de la guía: nada de orden de hash).

USO:
  PYTHONHASHSEED=1 biovenv/bin/python scripts/diagnostico_6_fallos_sinonimo.py \
      --db /tmp/viva.db --fallos /tmp/fallos_antes.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.environ.setdefault("BIORAG_NO_LOG", "1")

# Los 6 fallos de la corrida con neurona sobre la base viva (1357 nodos).
FALLOS = [
    ("0514", "perfil", "dennys-identidad-profunda"),
    ("0674", "filtro-arquitecto-prolijo", "compuerta-pre-validacion"),
    ("0692", "metodologia", "dennys-working-style"),
    ("0710", "agente", "aforismo_criterio_agente"),
    ("0734", "regla", "plan_mode_biorag"),
    ("0805", "cv", "cv_seccion_d_test_vinculacion"),
]


def _norm(s: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def censo(con: sqlite3.Connection, palabra: str) -> dict:
    """Cuántos recuerdos declaran la palabra y cuántos la llevan en el nombre."""
    p = f"%{palabra}%"
    total = con.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]
    en_nombre = con.execute(
        "SELECT COUNT(*) FROM largo_plazo WHERE LOWER(REPLACE(concepto,'_',' ')) LIKE ?", (p,)
    ).fetchone()[0]
    en_alias = con.execute(
        "SELECT COUNT(*) FROM largo_plazo WHERE LOWER(COALESCE(sinonimos,'')) LIKE ?", (p,)
    ).fetchone()[0]
    en_ambos = con.execute(
        "SELECT COUNT(*) FROM largo_plazo WHERE LOWER(COALESCE(sinonimos,'')) LIKE ? "
        "AND LOWER(REPLACE(concepto,'_',' ')) LIKE ?", (p, p)
    ).fetchone()[0]
    return {
        "palabra": palabra,
        "nodos": total,
        "en_nombre": en_nombre,
        "en_alias": en_alias,
        "en_ambos": en_ambos,
        "multiplicidad": max(en_nombre, en_alias),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/tmp/viva.db")
    ap.add_argument("--limite-puesto", type=int, default=200)
    args = ap.parse_args()

    from core.memory_store import SQLiteMemoryBioRAG

    # Copia de trabajo: el motor muta estado (despierta nodos, sube peso).
    tmp = os.path.join(tempfile.gettempdir(), "diag_sinonimo.db")
    shutil.copyfile(args.db, tmp)
    db = SQLiteMemoryBioRAG(db_path=tmp)
    ro = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)

    estado_inicial = {
        r[0]: (r[1], r[2])
        for r in db.cursor.execute("SELECT concepto, estado, peso_sinaptico FROM largo_plazo").fetchall()
    }

    def restaurar():
        db.cursor.executemany(
            "UPDATE largo_plazo SET estado = ?, peso_sinaptico = ? WHERE concepto = ?",
            [(e, p, c) for c, (e, p) in estado_inicial.items()],
        )
        db.conn.commit()

    # Desglose de puntos: se espía la llamada al score híbrido y se guarda con qué
    # agujas se calculó cada concepto.
    import core.fallback_simbolico as FS

    _orig_concepto = FS.score_simbolico_concepto
    _actual = {"concepto": None}
    capturado: dict[str, dict] = {}

    def _espia(tokens, concepto):
        _actual["concepto"] = concepto
        return _orig_concepto(tokens, concepto)

    FS.score_simbolico_concepto = _espia
    _orig_score = type(db)._calcular_score_hibrido

    def _espia_score(self, **kw):
        s = _orig_score(self, **kw)
        if _actual["concepto"] is not None:
            capturado[_actual["concepto"]] = dict(kw, _score=s)
        return s

    type(db)._calcular_score_hibrido = _espia_score

    # ── 1. Censo: ¿es palabra suelta o alias específico? ──
    print("=" * 78)
    print("1. ¿QUÉ TIPO DE FALLO ES CADA UNO?")
    print("=" * 78)
    print(f"{'ID':<6} {'consulta':<24} {'nodos':>6} {'en nombre':>10} {'en alias':>9} {'veredicto':<22}")
    censos = []
    for cid, q, _esp in FALLOS:
        c = censo(ro, q.lower())
        veredicto = "AMBIGUO (no forzable)" if c["multiplicidad"] >= 5 else "ALIAS ESPECÍFICO"
        censos.append(dict(id=cid, query=q, **c, veredicto=veredicto))
        print(f"{cid:<6} {q[:24]:<24} {c['nodos']:>6} {c['en_nombre']:>10} {c['en_alias']:>9} {veredicto:<22}")

    # ── 2. Puesto real con las condiciones de la QA ──
    print()
    print("=" * 78)
    print("2. PUESTO REAL DEL CORRECTO (condiciones de la QA: esperado despierto)")
    print("=" * 78)
    print(f"{'ID':<6} {'consulta':<24} {'estado QA':<9} {'puesto':>8}  esperado")
    puestos = []
    for cid, q, esp in FALLOS:
        # Setup idéntico al de evaluar_qa.py
        db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (esp,))
        db.conn.commit()
        res, _ = db.buscar_por_frase(
            q, profundidad="activos", limite=args.limite_puesto, ignore_peso_sinaptico=True
        )
        ids = [r[0] for r in res]
        pos = ids.index(esp) + 1 if esp in ids else 0
        est = estado_inicial.get(esp, ("?", None))[0]
        puestos.append(dict(id=cid, query=q, esperado=esp, estado_qa="activo",
                            estado_real=est, puesto=pos))
        print(f"{cid:<6} {q[:24]:<24} {'activo':<9} {(pos or 'FUERA'):>8}  {esp}")
        restaurar()

    # ── 3. Desglose del caso específico: por qué pierde ──
    print()
    print("=" * 78)
    print("3. POR QUÉ PIERDE: desglose de puntos (caso específico)")
    print("=" * 78)
    for cid, q, esp in FALLOS:
        c = next(x for x in censos if x["id"] == cid)
        if c["veredicto"] != "ALIAS ESPECÍFICO":
            continue
        db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (esp,))
        db.conn.commit()
        capturado.clear()
        res, _ = db.buscar_por_frase(q, profundidad="activos", limite=5, ignore_peso_sinaptico=True)
        print(f"\n  [{cid}] «{q}»  esperado: {esp}")
        print(f"  {'#':<3} {'concepto':<44} {'score':>6} {'bm25':>6} {'concepto':>9} {'sinonimo':>9} {'grupo':>6} {'exacto':>6}")
        for i, r in enumerate(res, 1):
            kw = capturado.get(r[0], {})
            g = kw.get
            print(f"  {i:<3} {r[0][:44]:<44} {r[4]:>6.3f} {g('bm25_norm',0):>6.3f} "
                  f"{g('concepto_ratio',0):>9.3f} {g('sinonimos_ratio',0):>9.3f} "
                  f"{g('grupo_score',0):>6.3f} {1 if g('match_exacto') else 0:>6}")
        kw = capturado.get(esp, {})
        g = kw.get
        if kw:
            print(f"\n  EL CORRECTO con las mismas agujas:")
            print(f"    bm25={g('bm25_norm',0):.3f}  concepto={g('concepto_ratio',0):.3f}  "
                  f"sinonimo={g('sinonimos_ratio',0):.3f}  grupo={g('grupo_score',0):.3f}  "
                  f"score={kw.get('_score',0):.3f}")
        # ¿Dónde está el correcto y con qué score?
        res2, _ = db.buscar_por_frase(q, profundidad="activos", limite=args.limite_puesto,
                                      ignore_peso_sinaptico=True)
        ids = [r[0] for r in res2]
        if esp in ids:
            p = ids.index(esp) + 1
            print(f"    puesto {p} de {len(ids)}  score={res2[p-1][4]:.3f}  "
                  f"(el 1º saca {res2[0][4]:.3f})")
        restaurar()

    # ── 4. Qué declara el correcto frente a los rivales ──
    print()
    print("=" * 78)
    print("4. LO QUE DECLARA CADA NODO (nombre vs alias)")
    print("=" * 78)
    for cid, q, esp in FALLOS:
        c = next(x for x in censos if x["id"] == cid)
        if c["veredicto"] != "ALIAS ESPECÍFICO":
            continue
        fila = ro.execute(
            "SELECT concepto, COALESCE(sinonimos,''), substr(COALESCE(contenido,''),1,120) "
            "FROM largo_plazo WHERE concepto = ?", (esp,)
        ).fetchone()
        print(f"\n  [{cid}] {esp}")
        print(f"    nombre : {fila[0]}")
        print(f"    alias  : {fila[1]}")
        print(f"    texto  : {fila[2]}...")
        print(f"    ¿la consulta '{q}' está en el nombre? "
              f"{'SÍ' if _norm(q) in _norm(fila[0]).replace('_',' ').replace('-',' ') else 'NO'}")
        print(f"    ¿está en el alias?  "
              f"{'SÍ' if _norm(q) in _norm(fila[1]) else 'NO'}")
        print(f"    ¿está en el texto?  "
              f"{'SÍ' if _norm(q) in _norm(fila[2]) else 'NO'}")

    type(db)._calcular_score_hibrido = _orig_score
    FS.score_simbolico_concepto = _orig_concepto
    os.remove(tmp)

    salida = os.path.join(RAIZ, "docs", "diagnostico_6_fallos_sinonimo_viva_20261026.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump({"censo": censos, "puestos": puestos}, f, indent=2, ensure_ascii=False)
    print(f"\n-> {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
