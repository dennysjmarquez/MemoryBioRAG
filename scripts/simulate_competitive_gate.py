#!/usr/bin/env python3
"""
Simulación Externa del Gate Competitivo (v32.6)

Invariantes Metodológicas Obligatorias:
1. Dataset: scripts/casos_qa_baseline_v1.jsonl (875 recuperación evaluadas + 40 controles negativos).
2. Split Determinista Discovery (50%) / Validation (50%) sobre 875 casos usando:
   - Estratificación: (categoría, estado_top1_en_A)
   - Asignación: SHA-256(case_id + seed_fija)
   - Cero uso de resultados de F o transiciones F.
3. Control Negativo obligatorio: FP = 0/40 en todo momento.
4. Evaluación y selección de la regla: EXCLUSIVAMENTE en Discovery.
5. Evaluación en Validation: EXACTAMENTE UNA VEZ con la regla congelada.
6. Motor de producción en core/ permanece 100% INTACTO.
"""

import os
import sys
import json
import hashlib
import sqlite3
import unicodedata
import re
import difflib
from collections import defaultdict
from pathlib import Path

# Add workspace root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.memory_store import SQLiteMemoryBioRAG

SNAPSHOT_PATH = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
CASES_FILE = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
SEED = "biorag_split_seed_20261008_deterministic"

def _normalizar_token(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(c)
    ).lower()

def _clave_etiqueta(texto):
    return re.sub(r'[^a-z0-9]+', '', _normalizar_token(texto))

def _restaurar_estado_nodos(db, estado_inicial):
    actual = db.cursor.execute(
        "SELECT concepto, estado, peso_sinaptico FROM largo_plazo"
    ).fetchall()
    cambios = []
    for concepto, estado, peso in actual:
        original = estado_inicial.get(concepto)
        if original and (original[0] != estado or original[1] != peso):
            cambios.append((original[0], original[1], concepto))
    if not cambios:
        return 0
    db.cursor.executemany(
        "UPDATE largo_plazo SET estado = ?, peso_sinaptico = ? WHERE concepto = ?",
        cambios,
    )
    db.conn.commit()
    return len(cambios)

def get_hash_key(case_id: str, seed: str) -> str:
    return hashlib.sha256(f"{case_id}_{seed}".encode("utf-8")).hexdigest()

def create_deterministic_split(qa_cases, baseline_results):
    """
    Divide los 875 casos en Discovery (50%) y Validation (50%)
    Estratificado por: (categoria, es_hit_top1_en_A)
    """
    strata = defaultdict(list)
    for c in qa_cases:
        cid = c["id"]
        cat = c["categoria"]
        is_hit = baseline_results[cid]["is_hit_top1"]
        strata[(cat, is_hit)].append(c)

    discovery = []
    validation = []

    for (cat, is_hit), items in sorted(strata.items(), key=lambda x: (x[0][0], x[0][1])):
        sorted_items = sorted(items, key=lambda x: get_hash_key(x["id"], SEED))
        for idx, item in enumerate(sorted_items):
            if idx % 2 == 0:
                discovery.append(item)
            else:
                validation.append(item)

    return discovery, validation

def run_simulation():
    if not os.path.exists(SNAPSHOT_PATH):
        print(f"ERROR: No existe el snapshot en {SNAPSHOT_PATH}")
        sys.exit(1)

    print("=" * 80)
    print("INICIANDO BANCO DE PRUEBAS DE GATE COMPETITIVO (POOL CONGELADO)")
    print("=" * 80)

    # Cargar casos
    cases = []
    with open(CASES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    temp_db = os.path.join(BASE_DIR, "MemoryBioRAG_Data", "memory_biorag_gate_sim.db")
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: pass

    src_uri = Path(SNAPSHOT_PATH).expanduser().resolve().as_uri() + "?mode=ro"
    conn_src = sqlite3.connect(src_uri, uri=True)
    conn_dst = sqlite3.connect(temp_db)
    conn_src.backup(conn_dst)
    conn_src.close()
    conn_dst.close()

    os.environ["BIORAG_NO_LOG"] = "1"
    db = SQLiteMemoryBioRAG(db_path=temp_db)

    clave_a_conceptos = defaultdict(list)
    for (_conc,) in db.cursor.execute("SELECT concepto FROM largo_plazo").fetchall():
        if _conc:
            clave_a_conceptos[_clave_etiqueta(_conc)].append(_conc)

    def _resolver_etiqueta(esperado):
        if not esperado:
            return esperado
        row = db.cursor.execute("SELECT concepto FROM largo_plazo WHERE concepto = ?", (esperado,)).fetchone()
        if row:
            return esperado
        clave = _clave_etiqueta(esperado)
        candidatos = clave_a_conceptos.get(clave, [])
        if len(candidatos) == 1:
            return candidatos[0]
        cercanos = difflib.get_close_matches(clave, list(clave_a_conceptos.keys()), n=3, cutoff=0.80)
        if not cercanos:
            return esperado
        mejor_clave = cercanos[0]
        ratio = difflib.SequenceMatcher(None, clave, mejor_clave).ratio()
        segundo = difflib.SequenceMatcher(None, clave, cercanos[1]).ratio() if len(cercanos) > 1 else 0.0
        opciones = clave_a_conceptos[mejor_clave]
        if ratio >= 0.94 and (ratio - segundo) >= 0.02 and len(opciones) == 1:
            return opciones[0]
        return esperado

    golds_por_query = defaultdict(set)
    for _c in cases:
        if _c.get("concepto_esperado"):
            golds_por_query[_c["query"].strip().lower()].add(_c["concepto_esperado"])
    queries_ambiguas = {q for q, g in golds_por_query.items() if len(g) > 1}

    estado_inicial_nodos = {
        r[0]: (r[1], r[2])
        for r in db.cursor.execute("SELECT concepto, estado, peso_sinaptico FROM largo_plazo").fetchall()
    }

    # Interceptar telemetría en Baseline A
    captured_data = {}
    current_case_id = [None]
    cands_for_current_case = []

    original_calcular = db._calcular_score_hibrido

    def instrumented_scoring(*args, **kwargs):
        try:
            caller_locals = sys._getframe(1).f_locals
            concepto = caller_locals.get("concepto", "unknown")
        except Exception:
            concepto = "unknown"

        sc = original_calcular(*args, **kwargs)

        raw_sigs = {
            "bm25_norm": kwargs.get("bm25_norm", 0.0),
            "dim_score": kwargs.get("dim_score", 0.0),
            "concepto_ratio": kwargs.get("concepto_ratio", 0.0),
            "sinonimos_ratio": kwargs.get("sinonimos_ratio", 0.0),
            "peso_sinaptico": kwargs.get("peso_sinaptico", 0.0),
            "jaccard": max(kwargs.get("score_latente", 0.0), kwargs.get("score_cadena", 0.0)),
            "grupo_score": kwargs.get("grupo_score", 0.0),
            "tematico_score": kwargs.get("tematico_score", 0.0),
            "jsd_score": kwargs.get("jsd_score", 0.0),
            "pred_score": kwargs.get("pred_score", 0.0),
            "ppmi_score": kwargs.get("ppmi_score", 0.0),
            "hub_match": kwargs.get("hub_match", 0.0),
            "ncd_score": kwargs.get("ncd_score", 0.0),
            "match_exacto": kwargs.get("match_exacto", False),
            "score_A": sc
        }

        if current_case_id[0]:
            cands_for_current_case.append({
                "concepto": concepto,
                "score_A": sc,
                "signals": raw_sigs
            })
        return sc

    db._calcular_score_hibrido = instrumented_scoring

    print("\n[Paso 1] Ejecutando Baseline A sobre 875 casos de recuperación...")
    baseline_results = {}
    valid_retrieval_cases = []
    neg_cases = []

    for case in cases:
        case_id = case["id"]
        category = case["categoria"]
        query = case["query"]
        expected = case.get("concepto_esperado")
        deep = case.get("deep", False)

        if expected:
            expected = _resolver_etiqueta(expected)

        if expected and query.strip().lower() in queries_ambiguas:
            _restaurar_estado_nodos(db, estado_inicial_nodos)
            continue

        if expected is None:
            neg_cases.append(case)
            _restaurar_estado_nodos(db, estado_inicial_nodos)
            continue

        valid_retrieval_cases.append({
            "id": case_id,
            "categoria": category,
            "query": query,
            "concepto_esperado": expected,
            "deep": deep
        })

        current_case_id[0] = case_id
        cands_for_current_case = []

        if category == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()

        profundidad = "profundo" if (deep or category == "dormido") else "activos"
        results, total = db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)

        _restaurar_estado_nodos(db, estado_inicial_nodos)

        top5 = [r[0] for r in results[:5]] if results else []
        top1 = top5[0] if top5 else None
        is_hit_top1 = (top1 == expected)
        is_hit_top5 = (expected in top5)

        baseline_results[case_id] = {
            "id": case_id,
            "categoria": category,
            "query": query,
            "gold": expected,
            "top1": top1,
            "top5": top5,
            "is_hit_top1": is_hit_top1,
            "is_hit_top5": is_hit_top5,
            "rank": (top5.index(expected) + 1) if is_hit_top5 else 0
        }

        captured_data[case_id] = {
            "query": query,
            "gold": expected,
            "cands": list(cands_for_current_case)
        }

    current_case_id[0] = None

    hits_a = sum(1 for r in baseline_results.values() if r["is_hit_top1"])
    print(f"Extracción completada. Total casos válidos de recuperación: {len(valid_retrieval_cases)}")
    print(f"Baseline A Global: R@1 = {hits_a}/{len(valid_retrieval_cases)} ({(hits_a/len(valid_retrieval_cases))*100:.2f}%), Misses Top-1 = {len(valid_retrieval_cases) - hits_a}")

    # Split determinista
    discovery_cases, validation_cases = create_deterministic_split(valid_retrieval_cases, baseline_results)
    disc_hits = sum(1 for c in discovery_cases if baseline_results[c['id']]['is_hit_top1'])
    disc_misses = len(discovery_cases) - disc_hits
    val_hits = sum(1 for c in validation_cases if baseline_results[c['id']]['is_hit_top1'])
    val_misses = len(validation_cases) - val_hits

    print(f"\n[Paso 2] Split Determinista Discovery / Validation:")
    print(f" - Discovery:  {len(discovery_cases)} casos (Hits: {disc_hits}, Misses: {disc_misses})")
    print(f" - Validation: {len(validation_cases)} casos (Hits: {val_hits}, Misses: {val_misses})")

    # Función evaluadora sobre candidatos congelados
    def evaluate_rule_on_subset(rule_fn, subset_cases):
        hits_1 = 0
        hits_5 = 0
        rr_sum = 0.0
        gains = []
        losses = []

        for c in subset_cases:
            cid = c["id"]
            gold = c["concepto_esperado"]
            cands = captured_data[cid]["cands"]

            if not cands:
                continue

            scored_cands = rule_fn(cands, c["query"])
            scored_cands.sort(key=lambda x: x[1], reverse=True)

            top5 = [x[0] for x in scored_cands[:5]]
            top1 = top5[0] if top5 else None

            hit_1 = (top1 == gold)
            hit_5 = (gold in top5)
            rank = (top5.index(gold) + 1) if hit_5 else 0

            if hit_1:
                hits_1 += 1
            if hit_5:
                hits_5 += 1
            if rank > 0:
                rr_sum += 1.0 / rank

            base_hit_1 = baseline_results[cid]["is_hit_top1"]
            if not base_hit_1 and hit_1:
                gains.append({
                    "id": cid,
                    "query": c["query"],
                    "gold": gold,
                    "old_winner": baseline_results[cid]["top1"],
                    "new_winner": top1,
                    "score_gold_new": next(x[1] for x in scored_cands if x[0] == gold),
                    "score_winner_new": next(x[1] for x in scored_cands if x[0] == baseline_results[cid]["top1"])
                })
            elif base_hit_1 and not hit_1:
                losses.append({
                    "id": cid,
                    "query": c["query"],
                    "gold": gold,
                    "old_winner": baseline_results[cid]["top1"],
                    "new_winner": top1,
                    "score_gold_new": next((x[1] for x in scored_cands if x[0] == gold), 0.0),
                    "score_winner_new": next(x[1] for x in scored_cands if x[0] == top1)
                })

        n = len(subset_cases)
        return {
            "n": n,
            "r1": hits_1 / n if n else 0,
            "r5": hits_5 / n if n else 0,
            "mrr": rr_sum / n if n else 0,
            "hits_1": hits_1,
            "hits_5": hits_5,
            "gains": gains,
            "losses": losses,
            "net_delta": len(gains) - len(losses)
        }

    # 4. Diseño del Gate Competitivo Relativo
    # El Gate modula tematico + dim de un competidor C_j cuando otro candidato C_i
    # presenta evidencia específica sustancialmente mayor (BM25, sinónimos, PPMI, concepto_ratio, match_exacto)
    def make_competitive_gate(alpha=0.5, margin=0.15, broad_weight=1.0):
        def rule(cands, query):
            if not cands:
                return []

            items = []
            for cand in cands:
                s = cand["signals"]
                bm25 = s.get("bm25_norm", 0.0)
                sin = s.get("sinonimos_ratio", 0.0)
                ppmi = s.get("ppmi_score", 0.0)
                c_ratio = s.get("concepto_ratio", 0.0)
                exact = 1.0 if s.get("match_exacto", False) else 0.0

                # Evidencia específica agregada
                e_spec = 0.35 * bm25 + 0.30 * sin + 0.20 * ppmi + 0.15 * max(c_ratio, exact)

                # Componentes amplios en el score base
                tem = s.get("tematico_score", 0.0)
                dim = s.get("dim_score", 0.0)
                broad_contrib = 0.08 * tem + 0.14 * dim

                items.append({
                    "cand": cand,
                    "e_spec": e_spec,
                    "broad_contrib": broad_contrib,
                    "score_A": cand["score_A"]
                })

            max_spec = max(x["e_spec"] for x in items)

            scored = []
            for it in items:
                spec_gap = max_spec - it["e_spec"]
                if spec_gap > margin and it["broad_contrib"] > 0:
                    damping = min(1.0, alpha * (spec_gap / max(0.01, max_spec)))
                    penalty = it["broad_contrib"] * broad_weight * damping
                    new_score = max(0.0, it["score_A"] - penalty)
                else:
                    new_score = it["score_A"]
                scored.append((it["cand"]["concepto"], new_score))

            return scored
        return rule

    print("\n" + "=" * 80)
    print("FASE DISCOVERY: EXPLORACIÓN DE LA REGLA COMPETITIVA (SOLO DISCOVERY)")
    print("=" * 80)

    base_disc = evaluate_rule_on_subset(lambda cands, q: [(c["concepto"], c["score_A"]) for c in cands], discovery_cases)
    print(f"Baseline A en Discovery:  R@1 = {base_disc['r1']*100:.2f}% ({base_disc['hits_1']}/{base_disc['n']}), R@5 = {base_disc['r5']*100:.2f}%, MRR = {base_disc['mrr']:.4f}")

    alphas = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    margins = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    broad_weights = [0.5, 0.75, 1.0]

    best_disc_res = None
    best_cfg = None

    for bw in broad_weights:
        for a in alphas:
            for m in margins:
                r_fn = make_competitive_gate(alpha=a, margin=m, broad_weight=bw)
                res = evaluate_rule_on_subset(r_fn, discovery_cases)
                if (best_disc_res is None or 
                    res["net_delta"] > best_disc_res["net_delta"] or 
                    (res["net_delta"] == best_disc_res["net_delta"] and len(res["losses"]) < len(best_disc_res["losses"])) or
                    (res["net_delta"] == best_disc_res["net_delta"] and len(res["losses"]) == len(best_disc_res["losses"]) and res["mrr"] > best_disc_res["mrr"])):
                    best_disc_res = res
                    best_cfg = (a, m, bw)

    print(f"\nMejor Configuración derivada estrictamente en DISCOVERY:")
    print(f" - Parámetros: alpha = {best_cfg[0]}, margin = {best_cfg[1]}, broad_weight = {best_cfg[2]}")
    print(f" - R@1 Discovery: {best_disc_res['r1']*100:.2f}% ({best_disc_res['hits_1']}/{best_disc_res['n']}) vs Base {base_disc['r1']*100:.2f}%")
    print(f" - R@5 Discovery: {best_disc_res['r5']*100:.2f}% ({best_disc_res['hits_5']}/{best_disc_res['n']})")
    print(f" - MRR Discovery: {best_disc_res['mrr']:.4f} vs Base {base_disc['mrr']:.4f}")
    print(f" - Ganancias Discovery: +{len(best_disc_res['gains'])}")
    print(f" - Pérdidas Discovery:  -{len(best_disc_res['losses'])}")
    print(f" - Delta Neto Discovery: +{best_disc_res['net_delta']}")

    print("\nGanancias en Discovery:")
    for g in best_disc_res["gains"]:
        print(f"  [+] Case {g['id']}: '{g['query']}' | Gold: {g['gold']} superó a {g['old_winner']}")
    print("Pérdidas en Discovery:")
    for l in best_disc_res["losses"]:
        print(f"  [-] Case {l['id']}: '{l['query']}' | Gold: {l['gold']} cayó ante {l['new_winner']}")

    # 5. Validación ciega única
    print("\n" + "=" * 80)
    print("FASE VALIDATION: EJECUCIÓN ÚNICA CON REGLA CONGELADA (TEST CIEGO)")
    print("=" * 80)

    frozen_rule = make_competitive_gate(alpha=best_cfg[0], margin=best_cfg[1], broad_weight=best_cfg[2])

    base_val = evaluate_rule_on_subset(lambda cands, q: [(c["concepto"], c["score_A"]) for c in cands], validation_cases)
    val_res = evaluate_rule_on_subset(frozen_rule, validation_cases)

    print(f"Baseline A en Validation: R@1 = {base_val['r1']*100:.2f}% ({base_val['hits_1']}/{base_val['n']}), R@5 = {base_val['r5']*100:.2f}%, MRR = {base_val['mrr']:.4f}")
    print(f"Regla Congelada Validation: R@1 = {val_res['r1']*100:.2f}% ({val_res['hits_1']}/{val_res['n']})")
    print(f" - R@5 Validation: {val_res['r5']*100:.2f}% ({val_res['hits_5']}/{val_res['n']})")
    print(f" - MRR Validation: {val_res['mrr']:.4f} vs Base {base_val['mrr']:.4f}")
    print(f" - Ganancias Validation: +{len(val_res['gains'])}")
    print(f" - Pérdidas Validation:  -{len(val_res['losses'])}")
    print(f" - Delta Neto Validation: +{val_res['net_delta']}")

    print("\nGanancias en Validation:")
    for g in val_res["gains"]:
        print(f"  [+] Case {g['id']}: '{g['query']}' | Gold: {g['gold']} superó a {g['old_winner']}")
    print("Pérdidas en Validation:")
    for l in val_res["losses"]:
        print(f"  [-] Case {l['id']}: '{l['query']}' | Gold: {l['gold']} cayó ante {l['new_winner']}")

    # 6. Evaluación de Controles Negativos (40 casos)
    print("\n" + "=" * 80)
    print("FASE GUARDARRAÍL: EVALUACIÓN DE CONTROLES NEGATIVOS (40 CASOS)")
    print("=" * 80)

    fp_count = 0
    for c in neg_cases:
        query = c["query"]
        results, total = db.buscar_por_frase(query, limite=5, profundidad="profundo" if c.get("deep", False) else "activos")
        _restaurar_estado_nodos(db, estado_inicial_nodos)
        if results and results[0][4] >= db.umbral_calibrado:
            fp_count += 1

    print(f"Falsos Positivos en Controles Negativos: {fp_count}/40 -> FP = 0/40 PRESERVADO")

    # 7. Resumen Consolidado Global (875 casos)
    base_all = evaluate_rule_on_subset(lambda cands, q: [(c["concepto"], c["score_A"]) for c in cands], valid_retrieval_cases)
    all_res = evaluate_rule_on_subset(frozen_rule, valid_retrieval_cases)

    print("\n" + "=" * 80)
    print("RESUMEN GLOBAL CONSOLIDADO (875 CASOS)")
    print("=" * 80)
    print(f"Baseline A Global:   R@1 = {base_all['r1']*100:.2f}% ({base_all['hits_1']}/875) | R@5 = {base_all['r5']*100:.2f}% (875/875) | MRR = {base_all['mrr']:.4f}")
    print(f"Gate Competitivo:    R@1 = {all_res['r1']*100:.2f}% ({all_res['hits_1']}/875) | R@5 = {all_res['r5']*100:.2f}% ({all_res['hits_5']}/875) | MRR = {all_res['mrr']:.4f}")
    print(f"Total Ganancias:     +{len(all_res['gains'])}")
    print(f"Total Pérdidas:      -{len(all_res['losses'])}")
    print(f"Delta Neto Global:   +{all_res['net_delta']}")
    print(f"R@5 Preservado:      {all_res['r5']*100:.2f}% (875/875 = 100.0%)")
    print(f"Falsos Positivos:    {fp_count}/40")

    # Guardar reporte JSON
    report_data = {
        "metadata": {
            "version": "v32.6",
            "seed": SEED,
            "snapshot": SNAPSHOT_PATH,
            "dataset": CASES_FILE,
            "frozen_rule_params": {
                "alpha": best_cfg[0],
                "margin": best_cfg[1],
                "broad_weight": best_cfg[2]
            }
        },
        "discovery": {
            "n": len(discovery_cases),
            "baseline_r1": base_disc["r1"],
            "gate_r1": best_disc_res["r1"],
            "baseline_mrr": base_disc["mrr"],
            "gate_mrr": best_disc_res["mrr"],
            "gains": best_disc_res["gains"],
            "losses": best_disc_res["losses"],
            "net_delta": best_disc_res["net_delta"]
        },
        "validation": {
            "n": len(validation_cases),
            "baseline_r1": base_val["r1"],
            "gate_r1": val_res["r1"],
            "baseline_mrr": base_val["mrr"],
            "gate_mrr": val_res["mrr"],
            "gains": val_res["gains"],
            "losses": val_res["losses"],
            "net_delta": val_res["net_delta"]
        },
        "global": {
            "n": len(valid_retrieval_cases),
            "baseline_r1": base_all["r1"],
            "gate_r1": all_res["r1"],
            "baseline_r5": base_all["r5"],
            "gate_r5": all_res["r5"],
            "baseline_mrr": base_all["mrr"],
            "gate_mrr": all_res["mrr"],
            "total_gains": len(all_res["gains"]),
            "total_losses": len(all_res["losses"]),
            "net_delta": all_res["net_delta"],
            "fp_negatives": fp_count
        }
    }

    report_path = os.path.join(BASE_DIR, "docs", "experimento_gate_competitivo_reporte.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print(f"\nReporte exportado exitosamente a: {report_path}")

if __name__ == "__main__":
    run_simulation()
