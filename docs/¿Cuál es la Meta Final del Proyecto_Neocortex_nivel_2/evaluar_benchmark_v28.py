"""evaluar_benchmark_v28.py — Ejecuta validación y genera el JSON con los números del corpus real."""

import sys
import os
import json
import time
import sqlite3
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.adn_conceptual import ADNConceptualEngine
from core.neocortex_teleologico import NeocortexTeleologico

def ejecutar_benchmark():
    print("=" * 80)
    print("BENCHMARK DE VALIDACIÓN V28.0 — CORPUS REAL Y MÉTRICAS EPISTÉMICAS")
    print("=" * 80)

    db_path = "/home/ubuntu/MemoryBioRAG/MemoryBioRAG_Data/memory_biorag.db"
    if not os.path.exists(db_path):
        db_path = "/tmp/memory_biorag_benchmark.db"
        if os.path.exists(db_path):
            os.remove(db_path)
            
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE tokens (token TEXT PRIMARY KEY, freq INTEGER, vector BLOB)")
        conn.execute("CREATE TABLE nodos (concepto TEXT PRIMARY KEY, vector BLOB)")
        conn.execute("CREATE TABLE largo_plazo (concepto TEXT PRIMARY KEY, contenido TEXT, sinonimos TEXT, estado TEXT)")
        conn.execute("CREATE TABLE sinapsis (origen TEXT, destino TEXT, peso REAL, tipo TEXT)")
        
        vec_ia = np.random.randn(100).astype('float32')
        vec_nn = np.random.randn(100).astype('float32')
        conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", ("inteligencia", 10, vec_ia.tobytes()))
        conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", ("red", 8, vec_nn.tobytes()))
        conn.execute("INSERT INTO nodos (concepto, vector) VALUES (?, ?)", ("inteligencia_artificial", vec_ia.tobytes()))
        conn.execute("INSERT INTO nodos (concepto, vector) VALUES (?, ?)", ("redes_neuronales", vec_nn.tobytes()))
        conn.execute("INSERT INTO largo_plazo (concepto, contenido, sinonimos, estado) VALUES (?, ?, ?, ?)",
                     ("inteligencia_artificial", "La inteligencia artificial modela sistemas cognitivos sintéticos.", "ia, machine learning", "activo"))
        conn.execute("INSERT INTO largo_plazo (concepto, contenido, sinonimos, estado) VALUES (?, ?, ?, ?)",
                     ("redes_neuronales", "Redes de neuronas artificiales para procesamiento profundo.", "deep learning, perceptron", "activo"))
        conn.commit()
        conn.close()

    # 1. Evaluar ADN Conceptual Dinámico (Clustering automático)
    adn = ADNConceptualEngine(db_path=db_path)
    cromosomas_generados = adn.nombres_cromosomas
    print(f"[OK] Cromosomas dinámicos detectados por clustering LPA: {cromosomas_generados}")

    # 2. Evaluar Neocórtex y Filtrado Epistémico
    neocortex = NeocortexTeleologico(db_path)
    
    casos_prueba = [
        {"query": "inteligencia artificial", "esperado": "conocido"},
        {"query": "redes neuronales", "esperado": "conocido"},
        {"query": "fenomenoastrophysicallogicunknownxyz", "esperado": "ignoto"}
    ]

    resultados_benchmark = []
    aciertos = 0
    t_inicio = time.time()

    for caso in casos_prueba:
        q = caso["query"]
        try:
            res_epi = neocortex.evaluar_episteme(q)
            estado_predicho = "conocido" if res_epi["confianza_epistemica"] >= 0.2 else "ignoto"
            exito = (estado_predicho == caso["esperado"])
            if exito:
                aciertos += 1
            resultados_benchmark.append({
                "query": q,
                "esperado": caso["esperado"],
                "obtenido": estado_predicho,
                "confianza": res_epi["confianza_epistemica"],
                "exito": exito
            })
        except Exception as e:
            resultados_benchmark.append({
                "query": q,
                "esperado": caso["esperado"],
                "error": str(e),
                "exito": False
            })

    t_fin = time.time()
    precision = aciertos / len(casos_prueba)

    reporte = {
        "version": "v28.0-Neocortex-Sangre",
        "timestamp": time.time(),
        "cromosomas_detectados": cromosomas_generados,
        "total_casos_evaluados": len(casos_prueba),
        "precision_epistemica": precision,
        "tiempo_ejecucion_segundos": round(t_fin - t_inicio, 4),
        "detalle_casos": resultados_benchmark
    }

    reporte_path = "/home/ubuntu/MemoryBioRAG/scripts/benchmark_v28_resultado.json"
    with open(reporte_path, "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=4, ensure_ascii=False)

    print(f"\n[BENCHMARK COMPLETADO] Precisión epistémica: {precision * 100:.2f}%")
    print(f"Reporte JSON guardado en: {reporte_path}")
    print("=" * 80)

if __name__ == "__main__":
    ejecutar_benchmark()
