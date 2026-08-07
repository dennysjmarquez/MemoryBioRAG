#!/usr/bin/env python3
"""Fase 1 del Plan Tejedora — Generación de Candidatos (Adamic-Adar).

Solo lectura: NO modifica producción. Trabaja sobre el snapshot de Fase 0.

Según plan Sección 4.1 + 4.2 + Fase 1 (L101-109), CON EL AJUSTE DE DISEÑO
aprobado 2026-08-06 (ver plan, Sección 4.1a "Ajuste de diseño"):
1. Calcular degree de cada nodo activo en el grafo de sinapsis
2. Identificar nodos con degree <= 3 (candidatos a "isla" — ampliado desde <= 1)
3. Para cada par de candidatos, calcular Adamic-Adar
4. Filtrar por AA >= umbral + dims compartidas >= 2
5. Excluir todo par con fila en sinapsis_cuarentena (cross-check bidireccional)
6. Registrar cuántos candidatos coinciden con cuarentena (señal de calibración)
7. Output: scripts/tejedora_candidatos.json

REMOCIÓN TOTAL DE VALENCIA (decisión Dennys 2026-08-06, SUPERSEDE al ajuste de
desempate): el experimento queda DESACOPLADO de valencia_somatica (salvaguarda
anti-olvido). La evidencia: los 13 pares candidatos de Fase 1 tienen valencia
0.0 (las islas son nodos no reforzados por definición), por lo que valencia es
NO-OP matemático en el pool; removerla cuesta CERO y no cambia ningún
candidato. La Tejedora usa SOLO señales estructurales: AA + dimensiones
compartidas + degree. Ver principio_desacoplamiento_tejedora_salvaguarda_olvido.

NOTA METODOLÓGICA: la cuarentena es un FILTRO NEGATIVO (exclusión), NO la
fuente de candidatos. Los candidatos nacen del grafo activo (sinapsis) por AA.
"""
import sys
import os
import json
import math
import time
import sqlite3
import unicodedata
import re
from collections import defaultdict
from itertools import combinations

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(BASE, "snapshots", "tejedora_pre_fase0_20260805_220447.db")
OUT = os.path.join(BASE, "scripts", "tejedora_candidatos.json")

# Parámetros iniciales del plan Sección 4.1 (el sweep de Fase 2 los varía)
# Ajuste 2026-08-06: AA arranca en 0.2 (no 0.5) y degree <= 3 (no <= 1),
# porque con los valores originales el pool quedaba en 2 pares (insuficiente
# para medir contra 921 casos). Ahora apunta a ~21 pares.
AA_UMBRAL = 0.2
DIMS_MIN = 2
DEGREE_MAX = 3  # Ampliado desde <= 1: cubre más fronteras sin perder coherencia
MAX_POR_NODO = 3  # Máximo conexiones por nodo por ciclo (riesgo sobresaturación)


def strip_accents(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


def tokens(text):
    t = re.sub(r'[^\w\s_-]', ' ', (text or '').lower())
    out = []
    for w in t.split():
        wc = strip_accents(w)
        if len(w) >= 2:
            out.append(wc)
    return set(out)


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_graph(db_path):
    """Construye el grafo de sinapsis y los metadatos de nodos activos."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    nodos_activos = {r["concepto"] for r in cur.execute(
        "SELECT concepto FROM largo_plazo WHERE estado = 'activo'")}

    # Grafo completo de sinapsis (topología real, cualquier estado de nodo)
    vecinos = defaultdict(set)
    for r in cur.execute("SELECT origen, destino FROM sinapsis"):
        a, b = r["origen"], r["destino"]
        vecinos[a].add(b)
        vecinos[b].add(a)

    # Dimensiones compartidas: agrupar dimension_id por concepto (activos)
    dims_por_concepto = defaultdict(set)
    for r in cur.execute(
        "SELECT d.concepto, d.dimension_id FROM largo_plazo_dimensiones d "
        "JOIN largo_plazo l ON l.concepto = d.concepto AND l.estado = 'activo'"):
        dims_por_concepto[r["concepto"]].add(r["dimension_id"])

    # Cuarentena bidireccional (pares podados por la Hormiguita)
    cuarentena_pares = set()
    for r in cur.execute("SELECT origen, destino FROM sinapsis_cuarentena"):
        a, b = r["origen"], r["destino"]
        cuarentena_pares.add((a, b))
        cuarentena_pares.add((b, a))

    db.close()
    return nodos_activos, vecinos, dims_por_concepto, cuarentena_pares


def adamic_adar(u, v, vecinos, degree, active):
    """AA(u,v) = sum_{w in N(u) ∩ N(v)} 1/log(deg(w))."""
    nu = vecinos[u]
    nv = vecinos[v]
    comunes = nu & nv
    if not comunes:
        return 0.0
    total = 0.0
    for w in comunes:
        dw = degree.get(w, 0)
        if dw >= 2:
            total += 1.0 / math.log(dw)
    return total


def main():
    t0 = time.time()
    nodos_activos, vecinos, dims_por_concepto, cuarentena = load_graph(SNAP)

    # 1. Degree de cada nodo activo en el grafo de sinapsis
    degree = {n: len(vecinos.get(n, ())) for n in nodos_activos}

    # 2. Islas: nodos activos con degree <= DEGREE_MAX (ajustado 2026-08-06)
    islas = [n for n in nodos_activos if degree[n] <= DEGREE_MAX]
    islas.sort()

    # 3-4. Candidatos AA por par de islas, con filtros
    candidatos = []
    candidatos_cuarentena = 0
    pares_procesados = 0
    por_nodo_count = defaultdict(int)

    for u, v in combinations(islas, 2):
        pares_procesados += 1
        par = (u, v)

        # Filtro dimensional: dims compartidas >= DIMS_MIN
        dims_comp = len(dims_por_concepto.get(u, set()) & dims_por_concepto.get(v, set()))
        if dims_comp < DIMS_MIN:
            continue

        # AA
        aa = adamic_adar(u, v, vecinos, degree, nodos_activos)
        if aa < AA_UMBRAL:
            continue

        # 5. Cross-check cuarentena (exclusión bidireccional) — señal de calibración
        if par in cuarentena:
            candidatos_cuarentena += 1
            continue

        # Límite de saturación: max 3 candidatos por nodo por ciclo
        if por_nodo_count[u] >= MAX_POR_NODO or por_nodo_count[v] >= MAX_POR_NODO:
            continue

        por_nodo_count[u] += 1
        por_nodo_count[v] += 1

        # Jaccard léxico como métrica complementaria (contexto, no criterio)
        # valencia_somatica REMOVIDA por completo (decisión Dennys 2026-08-06):
        # desacople total del experimento respecto a la salvaguarda anti-olvido.
        candidatos.append({
            "a": u,
            "b": v,
            "aa": round(aa, 4),
            "dims_compartidas": dims_comp,
            "degree_a": degree[u],
            "degree_b": degree[v],
        })

    # Orden: AA primero, luego dims compartidas. Sin valencia (remoción total).
    candidatos.sort(key=lambda c: (-c["aa"], -c["dims_compartidas"]))

    out = {
        "fase": "1",
        "descripcion": "Candidatos a tejido estructural (Adamic-Adar) sobre el snapshot de Fase 0. "
                       "La cuarentena es EXCLUSIÓN (filtro negativo), no fuente. "
                       "REMOCIÓN TOTAL DE VALENCIA 2026-08-06 (desacople de la salvaguarda "
                       "anti-olvido) — señales SOLO estructurales: AA + dims + degree.",
        "snapshot": os.path.basename(SNAP),
        "parametros": {
            "aa_umbral": AA_UMBRAL,
            "dims_min": DIMS_MIN,
            "degree_max": DEGREE_MAX,
            "max_por_nodo": MAX_POR_NODO,
            "valencia": "removida (desacople total)",
        },
        "grafo": {
            "nodos_activos": len(nodos_activos),
            "islas_degree_le": DEGREE_MAX,
            "pares_islas_evaluados": pares_procesados,
        },
        "filtros": {
            "excluidos_por_cuarentena": candidatos_cuarentena,
            "excluidos_por_dims_aa": pares_procesados - candidatos_cuarentena - len(candidatos),
        },
        "total_candidatos": len(candidatos),
        "candidatos": candidatos,
        "tiempo_s": round(time.time() - t0, 1),
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"nodos_activos={len(nodos_activos)} islas(deg<={DEGREE_MAX})={len(islas)} "
          f"pares_evaluados={pares_procesados}")
    print(f"excluidos_por_cuarentena={candidatos_cuarentena} (señal de calibración)")
    print(f"total_candidatos={len(candidatos)} ({time.time()-t0:.1f}s)")
    if candidatos:
        for c in candidatos[:8]:
            print(f"  AA={c['aa']:.3f} dims={c['dims_compartidas']} "
                  f"deg=({c['degree_a']},{c['degree_b']}) | {c['a'][:45]} <-> {c['b'][:45]}")
    print(f"-> {os.path.relpath(OUT, BASE)}")


if __name__ == "__main__":
    main()
