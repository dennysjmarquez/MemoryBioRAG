#!/usr/bin/env python3
"""eval_recall_completo.py — Evalúa recall@5 con los 921 casos de prueba.

Mide el recall real de BioRAG con las 4 técnicas semánticas habilitadas.

USO:
    python3 scripts/eval_recall_completo.py [--db PATH] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from core.memory_store import SQLiteMemoryBioRAG


def cargar_casos(jsonl_path: str) -> list[dict]:
    """Carga los casos de prueba desde JSONL."""
    casos = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                casos.append(json.loads(line))
    return casos


def evaluar_caso(cerebro: SQLiteMemoryBioRAG, caso: dict, limite: int = 5) -> dict:
    """Evalúa un caso individual."""
    query = caso["query"]
    esperado = caso["concepto_esperado"]
    categoria = caso.get("categoria", "unknown")
    
    start = time.time()
    try:
        resultados, total = cerebro.buscar_por_frase(query, limite=limite)
        tiempo = time.time() - start
    except Exception as e:
        return {
            "id": caso.get("id", "?"),
            "query": query,
            "esperado": esperado,
            "categoria": categoria,
            "encontrado": False,
            "posicion": -1,
            "tiempo": 0,
            "error": str(e)
        }
    
    # Verificar si el nodo esperado está en los resultados
    encontrado = False
    posicion = -1
    for i, r in enumerate(resultados):
        if r[0] == esperado:
            encontrado = True
            posicion = i + 1
            break
    
    return {
        "id": caso.get("id", "?"),
        "query": query,
        "esperado": esperado,
        "categoria": categoria,
        "encontrado": encontrado,
        "posicion": posicion,
        "tiempo": tiempo,
        "total_resultados": total,
        "top5": [r[0] for r in resultados[:5]]
    }


def ejecutar_evaluacion(db_path: str, limite: int = 5, max_casos: int = 0) -> dict:
    """Ejecuta la evaluación completa."""
    # Cargar casos
    jsonl_path = os.path.join(BASE, "scripts", "casos_qa.jsonl")
    if not os.path.exists(jsonl_path):
        print(f"[ERROR] Archivo de casos no encontrado: {jsonl_path}")
        return {}
    
    casos = cargar_casos(jsonl_path)
    if max_casos > 0:
        casos = casos[:max_casos]
    
    print(f"[INFO] Cargados {len(casos)} casos de prueba")
    print(f"[INFO] DB: {db_path}")
    print(f"[INFO] Límite por query: {limite}")
    print()
    
    # Inicializar cerebro
    cerebro = SQLiteMemoryBioRAG(db_path)
    
    # Evaluar cada caso
    resultados = []
    tiempos = []
    
    for i, caso in enumerate(casos):
        if (i + 1) % 50 == 0:
            print(f"  Procesando caso {i+1}/{len(casos)}...")
        
        resultado = evaluar_caso(cerebro, caso, limite)
        resultados.append(resultado)
        tiempos.append(resultado["tiempo"])
    
    # Calcular métricas
    total_casos = len(resultados)
    encontrados = sum(1 for r in resultados if r["encontrado"])
    por_categoria = defaultdict(lambda: {"total": 0, "encontrados": 0})
    por_posicion = defaultdict(int)
    
    for r in resultados:
        cat = r["categoria"]
        por_categoria[cat]["total"] += 1
        if r["encontrado"]:
            por_categoria[cat]["encontrados"] += 1
            por_posicion[r["posicion"]] += 1
    
    recall_at_5 = encontrados / total_casos if total_casos > 0 else 0
    recall_at_1 = por_posicion.get(1, 0) / total_casos if total_casos > 0 else 0
    mrr = sum(1/r["posicion"] for r in resultados if r["encontrado"]) / total_casos if total_casos > 0 else 0
    tiempo_promedio = sum(tiempos) / len(tiempos) if tiempos else 0
    
    # Guardar resultados detallados
    output_path = os.path.join(BASE, "docs", "eval_recall_completo_v29.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "version": "v29.0",
            "db": db_path,
            "total_casos": total_casos,
            "recall_at_5": recall_at_5,
            "recall_at_1": recall_at_1,
            "mrr": mrr,
            "tiempo_promedio_ms": tiempo_promedio * 1000,
            "por_categoria": dict(por_categoria),
            "por_posicion": dict(por_posicion),
            "resultados": resultados
        }, f, indent=2, ensure_ascii=False)
    
    return {
        "total_casos": total_casos,
        "encontrados": encontrados,
        "recall_at_5": recall_at_5,
        "recall_at_1": recall_at_1,
        "mrr": mrr,
        "tiempo_promedio_ms": tiempo_promedio * 1000,
        "por_categoria": dict(por_categoria),
        "por_posicion": dict(por_posicion),
        "output_path": output_path
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa recall@5 completo")
    parser.add_argument("--db", default=os.path.join(BASE, "MemoryBioRAG_Data", "memory_biorag.db"))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max", type=int, default=0, help="Máximo de casos (0=todos)")
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(f"[ERROR] DB no encontrada: {args.db}")
        return 1
    
    print("=" * 70)
    print("  EVALUACIÓN RECALL COMPLETA — BioRAG v29.0")
    print("=" * 70)
    print()
    
    metrics = ejecutar_evaluacion(args.db, args.limit, args.max)
    
    if not metrics:
        return 1
    
    print()
    print("=" * 70)
    print("  RESULTADOS")
    print("=" * 70)
    print()
    print(f"  Total casos:           {metrics['total_casos']}")
    print(f"  Encontrados (R@5):     {metrics['encontrados']}/{metrics['total_casos']} ({metrics['recall_at_5']*100:.1f}%)")
    print(f"  Recall@1:              {metrics['recall_at_1']*100:.1f}%")
    print(f"  MRR:                   {metrics['mrr']:.4f}")
    print(f"  Tiempo promedio:       {metrics['tiempo_promedio_ms']:.1f}ms")
    print()
    
    print("  Por categoría:")
    for cat, data in sorted(metrics['por_categoria'].items()):
        recall = data['encontrados'] / data['total'] if data['total'] > 0 else 0
        print(f"    {cat:<20} {data['encontrados']}/{data['total']} ({recall*100:.1f}%)")
    
    print()
    print("  Por posición de hallazgo:")
    for pos in sorted(metrics['por_posicion'].keys()):
        count = metrics['por_posicion'][pos]
        print(f"    TOP-{pos}: {count} casos")
    
    print()
    print(f"  Resultados guardados en: {metrics['output_path']}")
    print()
    
    # Determinar si pasa
    if metrics['recall_at_5'] >= 0.90:
        print("  ✅ RECALL >= 90% — Pasa para merge a master")
        return 0
    else:
        print(f"  ❌ RECALL < 90% ({metrics['recall_at_5']*100:.1f}%) — NO pasa para merge")
        return 1


if __name__ == "__main__":
    sys.exit(main())
