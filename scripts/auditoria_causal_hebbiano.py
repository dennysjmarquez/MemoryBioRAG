#!/usr/bin/env python3
"""
Auditoría Causal A/B: Impacto de la Propagación Hebbiana (Commit dd11bad)
========================================================================

Evalúa de forma rigurosa y diferencial:
  Modo A (Baseline): Sin propagación Hebbiana a primarios en BFS.
  Modo B (Actual):   Con propagación Hebbiana a primarios en BFS.

Métricas clave:
  - Comparativa Global R@1, R@5, MRR, Fallos y Falsos Positivos.
  - Clasificación de deltas: Rescates, Regresiones, Mejoras y No-Ops.
  - Auditoría detallada de las consultas donde intervino Spreading Activation / Hebbian Boost.
  - Evaluación formal de Graph-Candidates-Found vs Graph-Rescue@5 en EXP-Q.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import sqlite3
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from core.memory_store import SQLiteMemoryBioRAG


def _hacer_copia_aislada(src_path: str):
    temp_dir = tempfile.mkdtemp(prefix="biorag_causal_")
    dst_path = os.path.join(temp_dir, "isolated_eval.db")
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    dst = sqlite3.connect(dst_path)
    src.backup(dst)
    src.close()
    dst.close()
    return dst_path, temp_dir


def _resolver_etiqueta_oro(db, expected, fuzzy_min_ratio=0.94, margin=0.02):
    """Resuelve etiquetas desactualizadas de forma determinista contra la DB."""
    if not expected:
        return expected
    expected_list = expected if isinstance(expected, list) else [expected]
    cur = db.cursor
    resolved = []
    
    for exp in expected_list:
        cur.execute("SELECT concepto FROM largo_plazo WHERE concepto = ? AND estado = 'activo'", (exp,))
        row = cur.fetchone()
        if row:
            resolved.append(row[0])
            continue
            
        cur.execute("SELECT concepto FROM largo_plazo WHERE estado = 'activo'")
        all_concepts = [r[0] for r in cur.fetchall()]
        
        # Exact substring or normalized match
        norm_exp = exp.replace("-", "_").replace(" ", "_")
        matches = [c for c in all_concepts if norm_exp in c or c in norm_exp]
        if len(matches) == 1:
            resolved.append(matches[0])
            continue
            
        # Fallback to original
        resolved.append(exp)
        
    return resolved if isinstance(expected, list) else (resolved[0] if resolved else expected)


def auditar_causal_ab():
    snapshot_default = _RAIZ / "snapshots" / "qa_escape_qcr_20260811.db"
    snapshot_path = os.environ.get("BIORAG_PATH", str(snapshot_default))
    casos_file = _RAIZ / "scripts" / "casos_qa_baseline_v1.jsonl"
    
    if not os.path.exists(snapshot_path):
        print(f"[ERROR] Snapshot no encontrado en: {snapshot_path}")
        sys.exit(1)
        
    print("=" * 80)
    print("AUDITORÍA CAUSAL A/B: PROPAGACIÓN HEBBIANA EN RANKING")
    print("=" * 80)
    print(f"Snapshot origen:  {snapshot_path}")
    print(f"Casos QA:         {casos_file}")
    
    db_path, temp_dir = _hacer_copia_aislada(str(snapshot_path))
    
    try:
        # Cargar casos
        casos = []
        with open(casos_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    casos.append(json.loads(line.strip()))
                    
        print(f"Total casos cargados: {len(casos)}")
        
        cerebro = SQLiteMemoryBioRAG(db_path=db_path)
        
        # Umbral FP
        umbral_fp = cerebro._cargar_calibracion_persistida()
        if not umbral_fp or umbral_fp <= 0:
            umbral_fp = float(os.environ.get("BIORAG_FP_THRESHOLD", "0.25"))
            
        print(f"Umbral FP Conforme: {umbral_fp:.4f}")
        print("-" * 80)
        
        # Guardar método original de _expandir_contexto_bfs
        metodo_bfs_original = cerebro._expandir_contexto_bfs
        
        # Definir versión sin propagación a primarios (Modo A)
        def _bfs_sin_propagacion_primarios(pagina_resultados, depth, profundidad="activos", preview_chars=None):
            if not depth or depth <= 0 or not pagina_resultados:
                return pagina_resultados, []
                
            # Ejecutamos la lógica original pero conservamos la lista de primarios intacta
            _, contextos = metodo_bfs_original(pagina_resultados, depth, profundidad, preview_chars)
            return list(pagina_resultados), contextos

        stats_A = {"r1": 0, "r5": 0, "mrr_sum": 0.0, "total": 0, "fallos": 0, "fp": 0, "neg_total": 0}
        stats_B = {"r1": 0, "r5": 0, "mrr_sum": 0.0, "total": 0, "fallos": 0, "fp": 0, "neg_total": 0}
        
        deltas = {
            "rescates_top5": [],      # Gold > 5 -> Gold <= 5
            "rescates_top1": [],      # Gold != #1 -> Gold == #1
            "regresiones_top5": [],   # Gold <= 5 -> Gold > 5
            "regresiones_top1": [],   # Gold == #1 -> Gold != #1
            "mejoras_ranking": [],    # Gold subió puestos dentro de Top-5
            "empeoras_ranking": [],   # Gold bajó puestos dentro de Top-5
            "no_ops": 0,
            "falsos_positivos_A": [],
            "falsos_positivos_B": [],
            "consultas_spreading": []
        }
        
        start_time = time.time()
        
        for idx, caso in enumerate(casos, 1):
            query = caso["query"]
            expected_raw = caso.get("expected") or caso.get("esperado")
            categoria = caso.get("category") or caso.get("categoria", "general")
            profundidad = "profundo" if categoria == "dormido" else "activos"
            
            es_negativo = (categoria == "negativo" or expected_raw is None)
            expected = _resolver_etiqueta_oro(cerebro, expected_raw) if not es_negativo else None
            expected_set = set(expected if isinstance(expected, list) else [expected]) if expected else set()
            
            # ─── CORRIDA MODO A: Sin propagación Hebbiana ───
            cerebro._expandir_contexto_bfs = _bfs_sin_propagacion_primarios
            res_A, _ = cerebro.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
            spreading_A = bool(getattr(cerebro, "last_parent_map", None))
            
            # ─── CORRIDA MODO B: Con propagación Hebbiana (Actual) ───
            cerebro._expandir_contexto_bfs = metodo_bfs_original
            res_B, _ = cerebro.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
            spreading_B = bool(getattr(cerebro, "last_parent_map", None))
            
            conceptos_A = [r[0] for r in res_A]
            conceptos_B = [r[0] for r in res_B]
            scores_A = [r[4] for r in res_A]
            scores_B = [r[4] for r in res_B]
            
            if spreading_A or spreading_B:
                deltas["consultas_spreading"].append({
                    "id": caso.get("id", idx),
                    "query": query,
                    "esperado": list(expected_set),
                    "conceptos_A": conceptos_A,
                    "conceptos_B": conceptos_B,
                    "scores_A": scores_A,
                    "scores_B": scores_B,
                })
                
            if es_negativo:
                stats_A["neg_total"] += 1
                stats_B["neg_total"] += 1
                fp_A = any(s >= umbral_fp for s in scores_A)
                fp_B = any(s >= umbral_fp for s in scores_B)
                if fp_A:
                    stats_A["fp"] += 1
                    deltas["falsos_positivos_A"].append((idx, query, conceptos_A, scores_A))
                if fp_B:
                    stats_B["fp"] += 1
                    deltas["falsos_positivos_B"].append((idx, query, conceptos_B, scores_B))
                continue
                
            stats_A["total"] += 1
            stats_B["total"] += 1
            
            # Calcular rangos para Gold
            rank_A = None
            for r_idx, c in enumerate(conceptos_A, 1):
                if c in expected_set:
                    rank_A = r_idx
                    break
                    
            rank_B = None
            for r_idx, c in enumerate(conceptos_B, 1):
                if c in expected_set:
                    rank_B = r_idx
                    break
                    
            # Actualizar stats A
            if rank_A == 1:
                stats_A["r1"] += 1
            if rank_A and rank_A <= 5:
                stats_A["r5"] += 1
                stats_A["mrr_sum"] += 1.0 / rank_A
            else:
                stats_A["fallos"] += 1
                
            # Actualizar stats B
            if rank_B == 1:
                stats_B["r1"] += 1
            if rank_B and rank_B <= 5:
                stats_B["r5"] += 1
                stats_B["mrr_sum"] += 1.0 / rank_B
            else:
                stats_B["fallos"] += 1
                
            # Análisis diferencial
            if (not rank_A or rank_A > 5) and (rank_B and rank_B <= 5):
                deltas["rescates_top5"].append((caso.get("id", idx), query, expected, rank_A, rank_B))
            elif (rank_A and rank_A <= 5) and (not rank_B or rank_B > 5):
                deltas["regresiones_top5"].append((caso.get("id", idx), query, expected, rank_A, rank_B))
            elif rank_A != 1 and rank_B == 1:
                deltas["rescates_top1"].append((caso.get("id", idx), query, expected, rank_A, rank_B))
            elif rank_A == 1 and rank_B != 1:
                deltas["regresiones_top1"].append((caso.get("id", idx), query, expected, rank_A, rank_B))
            elif rank_A and rank_B and rank_A <= 5 and rank_B <= 5:
                if rank_B < rank_A:
                    deltas["mejoras_ranking"].append((caso.get("id", idx), query, expected, rank_A, rank_B))
                elif rank_B > rank_A:
                    deltas["empeoras_ranking"].append((caso.get("id", idx), query, expected, rank_A, rank_B))
                else:
                    deltas["no_ops"] += 1
            else:
                deltas["no_ops"] += 1

        elapsed = time.time() - start_time
        
        # ─── REPORTE DE RESULTADOS ───
        r5_A = (stats_A["r5"] / stats_A["total"]) * 100 if stats_A["total"] else 0.0
        r1_A = (stats_A["r1"] / stats_A["total"]) * 100 if stats_A["total"] else 0.0
        mrr_A = (stats_A["mrr_sum"] / stats_A["total"]) if stats_A["total"] else 0.0
        fp_rate_A = (stats_A["fp"] / stats_A["neg_total"]) * 100 if stats_A["neg_total"] else 0.0

        r5_B = (stats_B["r5"] / stats_B["total"]) * 100 if stats_B["total"] else 0.0
        r1_B = (stats_B["r1"] / stats_B["total"]) * 100 if stats_B["total"] else 0.0
        mrr_B = (stats_B["mrr_sum"] / stats_B["total"]) if stats_B["total"] else 0.0
        fp_rate_B = (stats_B["fp"] / stats_B["neg_total"]) * 100 if stats_B["neg_total"] else 0.0

        print(f"\nTiempo de auditoría A/B: {elapsed:.2f}s")
        print("=" * 80)
        print(f"{'MÉTRICA':<25} | {'MODO A (Sin Boost)':<20} | {'MODO B (Con Boost)':<20} | {'DELTA':<10}")
        print("-" * 80)
        print(f"{'Recall@5':<25} | {r5_A:>19.2f}% | {r5_B:>19.2f}% | {r5_B - r5_A:>+9.2f} pp")
        print(f"{'Recall@1 (Top-1)':<25} | {r1_A:>19.2f}% | {r1_B:>19.2f}% | {r1_B - r1_A:>+9.2f} pp")
        print(f"{'MRR':<25} | {mrr_A:>20.4f} | {mrr_B:>20.4f} | {mrr_B - mrr_A:>+10.4f}")
        print(f"{'Fallos Totales':<25} | {stats_A['fallos']:>20} | {stats_B['fallos']:>20} | {stats_B['fallos'] - stats_A['fallos']:>+10}")
        print(f"{'Falsos Positivos':<25} | {stats_A['fp']:>17}/{stats_A['neg_total']} | {stats_B['fp']:>17}/{stats_B['neg_total']} | {stats_B['fp'] - stats_A['fp']:>+10}")
        print(f"{'Tasa FP':<25} | {fp_rate_A:>19.2f}% | {fp_rate_B:>19.2f}% | {fp_rate_B - fp_rate_A:>+9.2f} pp")
        print("=" * 80)
        
        print("\nDESGLOSE DE MOVIMIENTOS CAUSALES:")
        print(f"  🟢 Rescates a Top-5 (Gold > 5 -> Gold <= 5):      {len(deltas['rescates_top5'])}")
        print(f"  🟢 Rescates a Top-1 (Gold != #1 -> Gold == #1):    {len(deltas['rescates_top1'])}")
        print(f"  🟡 Mejoras de posición dentro de Top-5:          {len(deltas['mejoras_ranking'])}")
        print(f"  ⚪ No-Ops (Sin cambio relativo de ranking):        {deltas['no_ops']}")
        print(f"  🔴 Empeoras de posición dentro de Top-5:          {len(deltas['empeoras_ranking'])}")
        print(f"  🔴 Regresiones de Top-1 (Gold == #1 -> Gold != #1): {len(deltas['regresiones_top1'])}")
        print(f"  🔴 Regresiones de Top-5 (Gold <= 5 -> Gold > 5):   {len(deltas['regresiones_top5'])}")
        print(f"  📡 Consultas donde intervino Spreading Activation: {len(deltas['consultas_spreading'])}")
        print("=" * 80)
        
        if deltas["rescates_top5"]:
            print("\nDETALLE DE RESCATES A TOP-5:")
            for item in deltas["rescates_top5"]:
                print(f"  [ID {item[0]}] Query: \"{item[1]}\" | Gold: {item[2]} | Rank: {item[3]} -> #{item[4]}")
                
        if deltas["regresiones_top5"]:
            print("\nDETALLE DE REGRESIONES DE TOP-5:")
            for item in deltas["regresiones_top5"]:
                print(f"  [ID {item[0]}] Query: \"{item[1]}\" | Gold: {item[2]} | Rank: #{item[3]} -> {item[4]}")
                
        # ─── AUDITORÍA EXP-Q (ABISMO LÉXICO) ───
        print("\n" + "=" * 80)
        print("AUDITORÍA EXP-Q (ABISMO LÉXICO): GRAPH-FOUND VS GRAPH-RESCUE@5")
        print("=" * 80)
        
        from scripts.test_abismo_lexico import CASOS_ABISMO_LEXICO
        
        for i, caso_q in enumerate(CASOS_ABISMO_LEXICO, 1):
            q_query = caso_q["query"]
            q_gold = caso_q["nodo_esperado"]
            
            # Primaria directa
            primarios, _ = cerebro.buscar_por_frase(q_query, context_window=0, limite=10)
            en_primaria = any(r[0] == q_gold for r in primarios)
            rank_primaria = next((idx for idx, r in enumerate(primarios, 1) if r[0] == q_gold), None)
            
            # Grafo BFS
            _, contexto_vecinos = cerebro.expandir_contexto_vecinos(primarios, depth=2)
            hallazgos_grafo = [idx for idx, v in enumerate(contexto_vecinos, 1) if v[0] == q_gold]
            pos_grafo = hallazgos_grafo[0] if hallazgos_grafo else None
            
            found_by_graph = bool(pos_grafo)
            rescue_top5 = bool(pos_grafo and pos_grafo <= 5)
            rescue_top1 = bool(pos_grafo and pos_grafo == 1)
            
            mecanismo_real = "primaria (Top1)" if rank_primaria == 1 else ("primaria" if en_primaria else ("grafo" if found_by_graph else "no_resuelto"))
            
            print(f"CASO {i} [{caso_q['id']}]: \"{q_query}\"")
            print(f"  Gold:                  {q_gold}")
            print(f"  Búsqueda Primaria:     {'✅ #' + str(rank_primaria) if en_primaria else '❌ 0 Overlap'}")
            print(f"  Candidato en Grafo:    {'✅ Sí (Pos #' + str(pos_grafo) + ')' if found_by_graph else '❌ No alcanzado'}")
            print(f"  Graph-Rescue@5:        {'✅ Sí (Top-5)' if rescue_top5 else '❌ No (Pos #' + str(pos_grafo) + ' > 5)'}")
            print(f"  Mecanismo Causal Real: {mecanismo_real}")
            print("-" * 80)
            
        # Exportar machine-readable JSON
        report_data = {
            "snapshot": str(snapshot_path),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stats_A_sin_boost": stats_A,
            "stats_B_con_boost": stats_B,
            "deltas": {
                "num_rescates_top5": len(deltas["rescates_top5"]),
                "num_rescates_top1": len(deltas["rescates_top1"]),
                "num_regresiones_top5": len(deltas["regresiones_top5"]),
                "num_regresiones_top1": len(deltas["regresiones_top1"]),
                "num_mejoras": len(deltas["mejoras_ranking"]),
                "num_empeoras": len(deltas["empeoras_ranking"]),
                "num_no_ops": deltas["no_ops"],
                "num_spreading_activation": len(deltas["consultas_spreading"])
            }
        }
        
        report_file = _RAIZ / "scripts" / "auditoria_causal_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
            
        print(f"\n[OK] Informe de auditoría guardado en: {report_file}")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    auditar_causal_ab()
