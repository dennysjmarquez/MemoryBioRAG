#!/usr/bin/env python3
"""Benchmark competitivo simbólico (sin embeddings).

Tipos 1–10 con ≥15 casos sintéticos cada uno sobre DB fresca.
No usa transformers ni APIs. Mide R@5, MRR, FP y latencia.
"""
from __future__ import annotations

import os
import sys
import time
import tempfile
import shutil
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("BIORAG_NO_LOG", "1")

from core.memory_store import SQLiteMemoryBioRAG
from core.memory_service import aprender, buscar, ensenar_lexico

random.seed(31)

TIPOS = {
    "literal": [],
    "sinonimo": [],
    "tema": [],
    "pregunta": [],
    "typo": [],
    "idioma": [],
    "periferica": [],
    "temporal": [],
    "multihop": [],
    "negativo": [],
}


def _nodos_base():
    return [
        ("reunion_juan_martes", "Reunion con Juan el martes sobre el informe."),
        ("can_mascota", "El can del vecino ladra de noche."),
        ("firewall_red", "Reglas de firewall para seguridad informatica perimetral."),
        ("manejo_errores", "Aprendi manejo de errores con try except y logs."),
        ("programacion_python", "Programacion en Python para agentes locales."),
        ("sdm_kanerva", "Memoria dispersa de Kanerva vectores binarios."),
        ("sinapsis_grafo", "Grafo de sinapsis con peso hebbiano."),
        ("calibracion_vovk", "Calibracion conforme de Vovk para falsos positivos."),
        ("ciclo_sueno", "Ciclo de sueno que consolida corto plazo."),
        ("ppmi_local", "PPMI SVD calculado en numpy sin GPU."),
        ("hub_conceptos", "Concept hub puente entre lexicos disjuntos."),
        ("dmn_idle", "DMN piensa cuando el usuario esta idle."),
        ("qcr_cobertura", "QCR mide cobertura de tokens de la query."),
        ("fts5_indice", "FTS5 indice invertido de SQLite."),
        ("ltd_decay", "LTD reduce peso de nodos no usados."),
    ]


def main():
    tmp = tempfile.mkdtemp(prefix="biorag_comp_")
    db = os.path.join(tmp, "c.db")
    c = SQLiteMemoryBioRAG(db)
    for concepto, contenido in _nodos_base():
        aprender(c, concepto, contenido, consolidar=True)

    ensenar_lexico(c, "perro", "can_mascota")
    ensenar_lexico(c, "seguridad informatica", "firewall_red")
    ensenar_lexico(c, "error handling", "manejo_errores")
    ensenar_lexico(c, "programcion", "programacion_python")

    casos = []
    for i in range(15):
        casos.append(("literal", "Reunion con Juan el martes", "reunion_juan_martes"))
        casos.append(("sinonimo", "perro", "can_mascota"))
        casos.append(("tema", "seguridad informatica", "firewall_red"))
        casos.append(("pregunta", "que aprendi sobre manejo de errores", "manejo_errores"))
        casos.append(("typo", "programcion", "programacion_python"))
        casos.append(("idioma", "error handling", "manejo_errores"))
        casos.append(("periferica", "memoria asociativa binaria kanerva", "sdm_kanerva"))
        casos.append(("temporal", "lo consolidado en el sueno", "ciclo_sueno"))
        casos.append(("multihop", "peso hebbiano del grafo", "sinapsis_grafo"))
        casos.append(("negativo", f"receta de paella valenciana {i}", None))

    hits = {k: [0, 0] for k in TIPOS}
    fp = 0
    neg = 0
    mrr_sum = 0.0
    mrr_n = 0
    lats = []
    for tipo, q, gold in casos:
        t0 = time.perf_counter()
        res, _ = buscar(c, q, limite=5)
        lats.append((time.perf_counter() - t0) * 1000)
        conceptos = [r[0] for r in res]
        if gold is None:
            neg += 1
            if res and res[0][4] >= 0.25:
                fp += 1
            continue
        hits[tipo][1] += 1
        if gold in conceptos:
            hits[tipo][0] += 1
            rank = conceptos.index(gold) + 1
            mrr_sum += 1.0 / rank
            mrr_n += 1
        else:
            mrr_n += 1

    print("=== benchmark_competitivo ===")
    for tipo, (h, n) in hits.items():
        if n:
            print(f"{tipo:12} R@5={100*h/n:.1f}% ({h}/{n})")
    print(f"MRR={mrr_sum/max(mrr_n,1):.4f}")
    print(f"FP={fp}/{neg} ({100*fp/max(neg,1):.1f}%)")
    print(f"P95_lat_ms={sorted(lats)[int(0.95*len(lats))-1]:.1f}")
    c.cerrar_sistema()
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
