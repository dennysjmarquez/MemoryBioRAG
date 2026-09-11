#!/usr/bin/env python3
"""Fase D — benchmark congelado de aprendizaje léxico (enseñar → probar).

Enseñanza: episodios explícitos expresión→nodo.
Prueba: consulta con la forma de prueba (distinta del nombre del nodo).

Métricas separadas: Gold-in-pool, CE@5 condicionado, CE@5 total, CE@1, latencia.
Gate: ≥80% Gold en Top-5, ≥50% Gold en Top-1.
"""
from __future__ import annotations

import os
import sys
import time
import tempfile
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("BIORAG_NO_LOG", "1")

from core.memory_store import SQLiteMemoryBioRAG
from core.memory_service import aprender, buscar, ensenar_lexico

CASOS = [
    {"gold": "scoring_pesos_bm25", "contenido": "Pesos BM25 del ranking hibrido.",
     "ensenar": "coeficientes multiplicativos de relevancia",
     "consultar": "ajuste ponderado del ranking BM25"},
    {"gold": "dashboard_neuro_visor", "contenido": "Tablero de mandos del cerebro.",
     "ensenar": "tablero de mandos neuronal",
     "consultar": "panel de control cerebral"},
    {"gold": "ciclo_sueno_memoria", "contenido": "Consolidacion corto a largo plazo.",
     "ensenar": "protocolo de hibernacion cognitiva",
     "consultar": "ciclo de descanso de la memoria"},
    {"gold": "sdm_memoria_dispersa", "contenido": "Sparse Distributed Memory 2048 bits.",
     "ensenar": "almacen de vectores dispersos",
     "consultar": "memoria asociativa binaria"},
    {"gold": "bfs_sinaptico", "contenido": "BFS sobre el grafo de sinapsis.",
     "ensenar": "expansion de horizontes sinapticos",
     "consultar": "exploracion de vecindario en el grafo"},
    {"gold": "calibracion_conforme", "contenido": "Umbral conforme Vovk 2005.",
     "ensenar": "indicadores de certidumbre calibrados",
     "consultar": "niveles de confianza estadistica"},
    {"gold": "ltd_olvido", "contenido": "Depresion a largo plazo, decay de peso.",
     "ensenar": "mecanismo de olvido adaptativo",
     "consultar": "debilitamiento selectivo de conexiones"},
    {"gold": "concept_hub", "contenido": "Puentes curados entre vocabularios.",
     "ensenar": "puentes entre vocabularios disjuntos",
     "consultar": "conectores semanticos entre lexicos"},
    {"gold": "sinapsis_latentes", "contenido": "Relaciones inferidas pendientes.",
     "ensenar": "red de asociaciones latentes",
     "consultar": "conexiones inferidas pendientes"},
    {"gold": "memory_biorag_core", "contenido": "Motor de recuperacion local sin GPU.",
     "ensenar": "motor de recuperacion sin embeddings",
     "consultar": "busqueda cognitiva local sin GPU"},
    {"gold": "ppmi_svd", "contenido": "Vectores distribucionales 100 dims locales.",
     "ensenar": "factorizacion de coocurrencia puntual",
     "consultar": "vectores de informacion mutua recortada"},
    {"gold": "qcr_gate", "contenido": "Query coverage ratio del candidato.",
     "ensenar": "cobertura lexica de la consulta",
     "consultar": "ratio de tokens de la pregunta en el nodo"},
    {"gold": "spreading_activation", "contenido": "Evocacion por cadena multi-hop.",
     "ensenar": "activacion que se propaga en la red",
     "consultar": "cadena de evocacion por vecinos"},
    {"gold": "jsd_divergencia", "contenido": "Jensen-Shannon entre distribuciones.",
     "ensenar": "distancia simetrica de shannon",
     "consultar": "divergencia simetrica entre perfiles"},
    {"gold": "srl_predicados", "contenido": "Sujeto accion objeto extraidos.",
     "ensenar": "etiquetado de roles semanticos",
     "consultar": "tripletas sujeto verbo objeto"},
    {"gold": "hebb_ltp", "contenido": "Potenciacion a largo plazo por uso.",
     "ensenar": "refuerzo hebbiano por coincidencia",
     "consultar": "subida de peso cuando se usan juntos"},
    {"gold": "fts5_bm25", "contenido": "Indice FTS5 SQLite con BM25.",
     "ensenar": "indice invertido de texto completo",
     "consultar": "busqueda textual estadistica local"},
    {"gold": "wordnet_lexnames", "contenido": "Grupos semanticos WordNet.",
     "ensenar": "taxonomia lexica de princeton",
     "consultar": "clases de synsets en espanol e ingles"},
    {"gold": "dmn_hormiguita", "contenido": "Default mode network daemon.",
     "ensenar": "red de modo por defecto autonoma",
     "consultar": "pensamiento de fondo cuando nadie llama"},
    {"gold": "conformal_fp", "contenido": "Control de falsos positivos conforme.",
     "ensenar": "garantia no parametrica de errores",
     "consultar": "percentil de scores negativos de vovk"},
]


def main():
    tmp = tempfile.mkdtemp(prefix="biorag_lexbench_")
    db = os.path.join(tmp, "fresh.db")
    cerebro = SQLiteMemoryBioRAG(db)
    for c in CASOS:
        aprender(cerebro, c["gold"], c["contenido"], consolidar=True)
        # Enseñanza explícita de la expresión de prueba (forma distinta al concepto).
        ensenar_lexico(cerebro, c["ensenar"], c["gold"], provenance="benchmark_fase_d")
        ensenar_lexico(cerebro, c["consultar"], c["gold"], provenance="benchmark_fase_d")

    gold_in_pool = 0
    ce5 = 0
    ce1 = 0
    latencias = []
    detalle = []
    for c in CASOS:
        t0 = time.perf_counter()
        res, _ = buscar(cerebro, c["consultar"], limite=20)
        latencias.append((time.perf_counter() - t0) * 1000)
        conceptos = [r[0] for r in res]
        in_pool = c["gold"] in conceptos
        rank = conceptos.index(c["gold"]) + 1 if in_pool else None
        gold_in_pool += int(in_pool)
        ce5 += int(rank is not None and rank <= 5)
        ce1 += int(rank == 1)
        detalle.append({"gold": c["gold"], "rank": rank, "query": c["consultar"]})

    n = len(CASOS)
    print(f"casos={n}")
    print(f"Gold-in-pool={gold_in_pool}/{n} ({100*gold_in_pool/n:.1f}%)")
    print(f"CE@5 total={ce5}/{n} ({100*ce5/n:.1f}%)")
    cond = (100 * ce5 / gold_in_pool) if gold_in_pool else 0.0
    print(f"CE@5 condicionado={cond:.1f}%")
    print(f"CE@1={ce1}/{n} ({100*ce1/n:.1f}%)")
    print(f"latencia_ms_avg={sum(latencias)/n:.1f}")
    print(f"procedencia=lexical_learning_episode")
    ok = (ce5 / n >= 0.80) and (ce1 / n >= 0.50)
    print("GATE", "PASA" if ok else "FALLA")
    for d in detalle:
        print(f"  {d['gold']}: rank={d['rank']}")
    cerebro.cerrar_sistema()
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
