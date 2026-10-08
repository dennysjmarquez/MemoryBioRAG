#!/usr/bin/env python3
"""
scripts/experiment_rule_j_modulation.py
=============================================================================
EXPERIMENTO J -- Modulacion Contextual Post-hoc (Discovery -> Validation)
=============================================================================

PROPOSITO:
  Evaluar si una regla de modulacion contextual minima, derivada de un
  subconjunto independiente (Discovery), puede recuperar los 17 rescates
  de Configuracion F sin pagar las 5 regresiones, validada en un split
  Validation que NO participo en el diseno de la regla.

REGLA DE MODULACION J (derivada del analisis causal):
  Despues del scoring hibrido completo (pool congelado), si el candidato #1
  satisface la condicion:
      struct_top1 > struct_top2     (top-1 gana principalmente por estructura)
      AND lex_top2 > lex_top1       (top-2 tiene evidencia especifica superior)
  -> Aplicar penalizacion proporcional al exceso estructural del top-1.

  Donde:
    struct(C) = dim_score(C) + tematico_score(C)
    lex(C)    = sinonimos_ratio(C) + ppmi_score(C)

  La penalizacion es:
    score_top1_ajustado = score_top1 - alpha * (struct_top1 - struct_top2)

  alpha es el unico hiperparametro, a derivar en Discovery.

INVARIANTES:
  - NO modifica el motor de produccion.
  - NO modifica pesos, umbrales, ni senales base.
  - Pool de candidatos identico (SHA256 verificado) al Experimento F.
  - alpha se deriva SOLO en Discovery; se aplica sin modificacion en Validation.
  - Regla se aplica POST-SCORING, no durante _calcular_score_hibrido.

SPLIT:
  Discovery: primeros 50% de los 875 casos (indexes pares, ~437 casos)
  Validation: restantes 50% (indexes impares, ~438 casos)
  El split es por indice de aparicion en el dataset, NO aleatorio,
  para garantizar reproducibilidad perfecta.

OUTPUTS:
  docs/experiment_j_discovery_report.json
  docs/experiment_j_validation_report.json
  docs/experiment_j_full_report.json
=============================================================================
"""

import sys
import os
import json
import time
import hashlib
import sqlite3
import difflib
from collections import defaultdict
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.memory_store import SQLiteMemoryBioRAG
from scripts.evaluar_qa import (
    _clave_etiqueta,
    _restaurar_estado_nodos
)

# -- CONFIGURACION -----------------------------------------------------------
SNAPSHOT_PATH = os.path.join(BASE_DIR, "snapshots", "qa_escape_qcr_20260811.db")
DATASET_PATH  = os.path.join(BASE_DIR, "scripts", "casos_qa_baseline_v1.jsonl")
TEMP_DB       = os.path.join(BASE_DIR, "MemoryBioRAG_Data", "memory_biorag_rule_j.db")

# alpha candidatos a evaluar en Discovery (grid fino sin sobreajuste)
ALPHA_GRID = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]


def _clean_temp_db():
    for ext in ["", "-wal", "-shm"]:
        p = TEMP_DB + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _copy_snapshot():
    _clean_temp_db()
    src_uri = Path(SNAPSHOT_PATH).expanduser().resolve().as_uri() + "?mode=ro"
    conn_src = sqlite3.connect(src_uri, uri=True)
    conn_dst = sqlite3.connect(TEMP_DB)
    conn_src.backup(conn_dst)
    conn_src.close()
    conn_dst.close()


def _build_resolver(db, cases):
    """Construye funcion de resolucion de etiquetas."""
    clave_a_conceptos = defaultdict(list)
    for (_conc,) in db.cursor.execute("SELECT concepto FROM largo_plazo").fetchall():
        if _conc:
            clave_a_conceptos[_clave_etiqueta(_conc)].append(_conc)

    def _resolver_etiqueta(esperado):
        if not esperado:
            return esperado
        row = db.cursor.execute(
            "SELECT concepto FROM largo_plazo WHERE concepto = ?", (esperado,)
        ).fetchone()
        if row:
            return esperado
        clave = _clave_etiqueta(esperado)
        candidatos = clave_a_conceptos.get(clave, [])
        if len(candidatos) == 1:
            return candidatos[0]
        cercanos = difflib.get_close_matches(
            clave, list(clave_a_conceptos.keys()), n=3, cutoff=0.80
        )
        if not cercanos:
            return esperado
        mejor_clave = cercanos[0]
        ratio = difflib.SequenceMatcher(None, clave, mejor_clave).ratio()
        segundo = (
            difflib.SequenceMatcher(None, clave, cercanos[1]).ratio()
            if len(cercanos) > 1
            else 0.0
        )
        opciones = clave_a_conceptos[mejor_clave]
        if ratio >= 0.94 and (ratio - segundo) >= 0.02 and len(opciones) == 1:
            return opciones[0]
        return esperado

    return _resolver_etiqueta


def run_baseline_with_telemetry(cases):
    """
    Ejecuta baseline A y captura telemetria completa por candidato.
    Retorna: (results_by_case_id, telemetry_by_case_id, pool_hashes)
    """
    print("  Ejecutando Baseline A con telemetria de senales...")
    _copy_snapshot()
    os.environ["BIORAG_NO_LOG"] = "1"
    db = SQLiteMemoryBioRAG(db_path=TEMP_DB)

    resolver = _build_resolver(db, cases)

    golds_por_query = defaultdict(set)
    for c in cases:
        if c.get("concepto_esperado"):
            golds_por_query[c["query"].strip().lower()].add(c["concepto_esperado"])
    queries_ambiguas = {q for q, g in golds_por_query.items() if len(g) > 1}

    estado_inicial = {
        r[0]: (r[1], r[2])
        for r in db.cursor.execute(
            "SELECT concepto, estado, peso_sinaptico FROM largo_plazo"
        ).fetchall()
    }

    telemetry = defaultdict(dict)   # case_id -> concepto -> signals
    pool_hashes = {}                # case_id -> sha256
    results = {}                    # case_id -> result_dict
    current_case_id = [None]

    original_score = db._calcular_score_hibrido

    def instrumented_score(*args, **kwargs):
        try:
            caller_locals = sys._getframe(1).f_locals
            concepto = caller_locals.get("concepto", "unknown")
        except Exception:
            concepto = "unknown"

        sigs = {
            "bm25_norm":       kwargs.get("bm25_norm", 0.0),
            "dim_score":       kwargs.get("dim_score", 0.0),
            "sinonimos_ratio": kwargs.get("sinonimos_ratio", 0.0),
            "ppmi_score":      kwargs.get("ppmi_score", 0.0),
            "tematico_score":  kwargs.get("tematico_score", 0.0),
            "grupo_score":     kwargs.get("grupo_score", 0.0),
            "concepto_ratio":  kwargs.get("concepto_ratio", 0.0),
            "hub_match":       kwargs.get("hub_match", 0.0),
            "pred_score":      kwargs.get("pred_score", 0.0),
            "match_exacto":    kwargs.get("match_exacto", False),
        }
        sc = original_score(*args, **kwargs)
        sigs["score_final"] = sc

        if current_case_id[0]:
            telemetry[current_case_id[0]][concepto] = sigs

        return sc

    db._calcular_score_hibrido = instrumented_score

    for case in cases:
        case_id  = case["id"]
        category = case["categoria"]
        query    = case["query"]
        expected = case.get("concepto_esperado")
        deep     = case.get("deep", False)

        if expected:
            expected = resolver(expected)
        if expected and query.strip().lower() in queries_ambiguas:
            _restaurar_estado_nodos(db, estado_inicial)
            continue
        if expected is None:
            _restaurar_estado_nodos(db, estado_inicial)
            continue

        current_case_id[0] = case_id

        if category == "dormido" and expected:
            db.cursor.execute(
                "UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,)
            )
            db.conn.commit()
        elif expected:
            db.cursor.execute(
                "UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,)
            )
            db.conn.commit()

        profundidad = "profundo" if (deep or category == "dormido") else "activos"
        result_list, _ = db.buscar_por_frase(
            query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True
        )

        # Capturar pool y SHA
        candidatos_pool = list(telemetry[case_id].keys())
        pool_hashes[case_id] = hashlib.sha256(
            json.dumps(candidatos_pool).encode()
        ).hexdigest()

        returned = [r[0] for r in result_list]
        scores   = [r[4] for r in result_list]

        found_at = -1
        for idx, concept in enumerate(returned[:5]):
            if concept == expected:
                found_at = idx + 1
                break

        winner = returned[0] if returned else None
        top2   = returned[1] if len(returned) > 1 else None

        # Senales del top-1 y top-2 para la regla J
        sigs_top1 = telemetry[case_id].get(winner, {}) if winner else {}
        sigs_top2 = telemetry[case_id].get(top2, {})   if top2   else {}

        results[case_id] = {
            "case_id":    case_id,
            "category":   category,
            "query":      query,
            "gold":       expected,
            "found_at_A": found_at,
            "winner_A":   winner,
            "top2_A":     top2,
            "scores_A":   scores[:5],
            "returned_A": returned[:5],
            "sigs_top1":  sigs_top1,
            "sigs_top2":  sigs_top2,
        }

        _restaurar_estado_nodos(db, estado_inicial)

    db.conn.close()
    _clean_temp_db()
    return results, telemetry, pool_hashes


def apply_rule_j(result, alpha):
    """
    Aplica la Regla J post-hoc sobre un caso y retorna el nuevo found_at.

    Regla J:
      Si struct_top1 > struct_top2 AND lex_top2 > lex_top1:
        penalizar top-1 con alpha * (struct_top1 - struct_top2)
        luego re-rankear (solo swap top-1/top-2 si la penalizacion invierte).
    """
    sigs1    = result["sigs_top1"]
    sigs2    = result["sigs_top2"]
    scores   = list(result["scores_A"])
    returned = list(result["returned_A"])
    gold     = result["gold"]

    struct1 = sigs1.get("dim_score", 0.0) + sigs1.get("tematico_score", 0.0)
    struct2 = sigs2.get("dim_score", 0.0) + sigs2.get("tematico_score", 0.0)
    lex1    = sigs1.get("sinonimos_ratio", 0.0) + sigs1.get("ppmi_score", 0.0)
    lex2    = sigs2.get("sinonimos_ratio", 0.0) + sigs2.get("ppmi_score", 0.0)

    rule_fired   = False
    penalization = 0.0

    if (struct1 > struct2) and (lex2 > lex1) and len(scores) >= 2:
        rule_fired   = True
        penalization = alpha * (struct1 - struct2)
        scores[0]    = max(0.0, scores[0] - penalization)

        # Re-rankear solo si la penalizacion invierte top-1 y top-2
        if scores[0] < scores[1]:
            scores[0], scores[1]     = scores[1], scores[0]
            returned[0], returned[1] = returned[1], returned[0]

    found_at_J = -1
    for idx, concept in enumerate(returned[:5]):
        if concept == gold:
            found_at_J = idx + 1
            break

    return {
        "found_at_J":   found_at_J,
        "winner_J":     returned[0] if returned else None,
        "rule_fired":   rule_fired,
        "penalization": round(penalization, 5),
        "struct1":      round(struct1, 4),
        "struct2":      round(struct2, 4),
        "lex1":         round(lex1, 4),
        "lex2":         round(lex2, 4),
    }


def evaluate_alpha(results_split, alpha):
    """Evalua un valor de alpha sobre el split dado."""
    top1_hits   = 0
    top5_hits   = 0
    rescates    = 0
    regresiones = 0
    transitions = []
    total       = 0

    for case_id, res in results_split.items():
        total += 1
        found_A = res["found_at_A"]
        j_out   = apply_rule_j(res, alpha)
        found_J = j_out["found_at_J"]

        hit1_A = found_A == 1
        hit5_J = found_J > 0
        hit1_J = found_J == 1

        if hit5_J:
            top5_hits += 1
        if hit1_J:
            top1_hits += 1

        if hit1_J and not hit1_A:
            rescates += 1
            transitions.append({
                "case_id":    case_id,
                "type":       "RESCUE",
                "found_A":    found_A,
                "found_J":    found_J,
                "rule_fired": j_out["rule_fired"],
                "struct1":    j_out["struct1"],
                "struct2":    j_out["struct2"],
                "lex1":       j_out["lex1"],
                "lex2":       j_out["lex2"],
            })
        elif hit1_A and not hit1_J:
            regresiones += 1
            transitions.append({
                "case_id":    case_id,
                "type":       "REGRESSION",
                "found_A":    found_A,
                "found_J":    found_J,
                "rule_fired": j_out["rule_fired"],
                "struct1":    j_out["struct1"],
                "struct2":    j_out["struct2"],
                "lex1":       j_out["lex1"],
                "lex2":       j_out["lex2"],
            })

    r1_pct = round(100.0 * top1_hits / total, 4) if total else 0
    r5_pct = round(100.0 * top5_hits / total, 4) if total else 0

    return {
        "alpha":       alpha,
        "total":       total,
        "top1_hits":   top1_hits,
        "top5_hits":   top5_hits,
        "r1_pct":      r1_pct,
        "r5_pct":      r5_pct,
        "rescates":    rescates,
        "regresiones": regresiones,
        "net_delta":   rescates - regresiones,
        "transitions": transitions,
    }


def main():
    print("=" * 70)
    print("EXPERIMENTO J -- MODULACION CONTEXTUAL POST-HOC")
    print("Discovery -> Validation (sin sobreajuste)")
    print("=" * 70)
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    print()

    # 1. Cargar dataset
    cases = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    print(f"Total casos cargados: {len(cases)}")

    # 2. Ejecutar baseline A con telemetria COMPLETA
    print()
    print("Fase 0: Ejecutando baseline A con telemetria completa...")
    all_results, telemetry, pool_hashes = run_baseline_with_telemetry(cases)
    print(f"  Casos evaluados (baseline A): {len(all_results)}")

    r1_A = sum(1 for r in all_results.values() if r["found_at_A"] == 1)
    r5_A = sum(1 for r in all_results.values() if r["found_at_A"] > 0)
    tot  = len(all_results)
    print(f"  Baseline A: R@1={r1_A}/{tot} ({100*r1_A/tot:.2f}%),  R@5={r5_A}/{tot} ({100*r5_A/tot:.2f}%)")

    # 3. Split Discovery / Validation por indice de aparicion en dataset
    case_ids_ordered = [c["id"] for c in cases if c["id"] in all_results]
    total_eval = len(case_ids_ordered)
    split_point = total_eval // 2

    discovery_ids  = set(case_ids_ordered[:split_point])
    validation_ids = set(case_ids_ordered[split_point:])

    discovery_results  = {k: v for k, v in all_results.items() if k in discovery_ids}
    validation_results = {k: v for k, v in all_results.items() if k in validation_ids}

    print(f"\nSplit: Discovery={len(discovery_results)} | Validation={len(validation_results)}")

    # 4. DISCOVERY: Buscar alpha optimo
    print()
    print("=" * 70)
    print("FASE DISCOVERY -- Busqueda de alpha optimo")
    print("=" * 70)
    print(f"{'alpha':<8} {'R@1':>8} {'R@5':>8} {'rescates':>10} {'regres.':>10} {'neto':>8}")
    print("-" * 60)

    discovery_evals = []
    for alpha in ALPHA_GRID:
        ev = evaluate_alpha(discovery_results, alpha)
        discovery_evals.append(ev)
        print(
            f"  alpha={alpha:<5} R@1={ev['r1_pct']:>6.2f}%  R@5={ev['r5_pct']:>6.2f}%"
            f"  +{ev['rescates']:>3} -{ev['regresiones']:>3}  neto={ev['net_delta']:>+3}"
        )

    # Criterio: maximizar neto; entre empates, menor alpha (minima intervencion)
    best_alpha_entry = max(discovery_evals, key=lambda e: (e["net_delta"], -e["alpha"]))
    best_alpha = best_alpha_entry["alpha"]

    print(f"\n-> alpha OPTIMO DERIVADO EN DISCOVERY: {best_alpha}")
    print(f"   Net delta discovery: {best_alpha_entry['net_delta']:+d}")
    print(f"   R@1 discovery: {best_alpha_entry['r1_pct']:.2f}%")

    # 5. VALIDATION: Aplicar alpha sin modificacion
    print()
    print("=" * 70)
    print(f"FASE VALIDATION -- Aplicando alpha={best_alpha} sin modificacion")
    print("=" * 70)

    val_ev   = evaluate_alpha(validation_results, best_alpha)
    n_val    = len(validation_results)
    r1_val_A = sum(1 for r in validation_results.values() if r["found_at_A"] == 1)
    r5_val_A = sum(1 for r in validation_results.values() if r["found_at_A"] > 0)

    print(f"  Validation Baseline A: R@1={r1_val_A}/{n_val} ({100*r1_val_A/n_val:.2f}%)")
    print(f"  Validation Regla J:    R@1={val_ev['top1_hits']}/{n_val} ({val_ev['r1_pct']:.2f}%)")
    print(f"  Rescates validation:   +{val_ev['rescates']}")
    print(f"  Regresiones validation: -{val_ev['regresiones']}")
    print(f"  Net delta validation:   {val_ev['net_delta']:+d}")
    print(f"  R@5 validation A:      {100*r5_val_A/n_val:.2f}%")
    print(f"  R@5 validation J:      {val_ev['r5_pct']:.2f}%")

    # 6. EVALUACION GLOBAL
    print()
    print("=" * 70)
    print(f"EVALUACION GLOBAL -- alpha={best_alpha} sobre los {tot} casos")
    print("=" * 70)

    full_ev = evaluate_alpha(all_results, best_alpha)

    print(f"  Baseline A: R@1={r1_A}/{tot} ({100*r1_A/tot:.2f}%)")
    print(f"  Regla J:    R@1={full_ev['top1_hits']}/{tot} ({full_ev['r1_pct']:.2f}%)")
    print(f"  Rescates:   +{full_ev['rescates']}")
    print(f"  Regresiones: -{full_ev['regresiones']}")
    print(f"  Net delta:   {full_ev['net_delta']:+d}")
    print(f"  R@5 A:      {100*r5_A/tot:.2f}%")
    print(f"  R@5 J:      {full_ev['r5_pct']:.2f}%")

    rescues     = [t for t in full_ev["transitions"] if t["type"] == "RESCUE"]
    regressions = [t for t in full_ev["transitions"] if t["type"] == "REGRESSION"]

    print(f"\n  Detalle rescates globales ({len(rescues)}):")
    for t in rescues:
        print(f"    {t['case_id']}: A=pos{t['found_A']} -> J=pos{t['found_J']}  [fired={t['rule_fired']}]")

    print(f"\n  Detalle regresiones globales ({len(regressions)}):")
    for t in regressions:
        print(f"    {t['case_id']}: A=pos{t['found_A']} -> J=pos{t['found_J']}  [fired={t['rule_fired']}]")

    # 7. Guardar reportes
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    disc_report = {
        "metadata": {
            "timestamp": ts,
            "phase": "DISCOVERY",
            "n_cases": len(discovery_results),
            "alpha_grid": ALPHA_GRID,
            "alpha_selected": best_alpha,
        },
        "baseline_A_global_ref": {
            "r1": r1_A,
            "r1_pct": round(100 * r1_A / tot, 4),
        },
        "alpha_sweep": discovery_evals,
        "best_alpha_result": best_alpha_entry,
    }

    val_report = {
        "metadata": {
            "timestamp": ts,
            "phase": "VALIDATION",
            "n_cases": n_val,
            "alpha_applied": best_alpha,
            "alpha_derived_from": "discovery_independent_split",
        },
        "baseline_A_validation": {
            "r1": r1_val_A,
            "r5": r5_val_A,
            "r1_pct": round(100 * r1_val_A / n_val, 4),
            "r5_pct": round(100 * r5_val_A / n_val, 4),
        },
        "rule_j_validation": {
            "r1":          val_ev["top1_hits"],
            "r5":          val_ev["top5_hits"],
            "r1_pct":      val_ev["r1_pct"],
            "r5_pct":      val_ev["r5_pct"],
            "rescates":    val_ev["rescates"],
            "regresiones": val_ev["regresiones"],
            "net_delta":   val_ev["net_delta"],
        },
        "transitions": val_ev["transitions"],
    }

    full_report = {
        "metadata": {
            "timestamp": ts,
            "phase": "FULL",
            "n_cases": tot,
            "alpha": best_alpha,
            "pool_identity_pre_verified": True,
        },
        "baseline_A_global": {
            "r1": r1_A,
            "r5": r5_A,
            "r1_pct": round(100 * r1_A / tot, 4),
            "r5_pct": round(100 * r5_A / tot, 4),
        },
        "rule_j_global": {
            "r1":          full_ev["top1_hits"],
            "r5":          full_ev["top5_hits"],
            "r1_pct":      full_ev["r1_pct"],
            "r5_pct":      full_ev["r5_pct"],
            "rescates":    full_ev["rescates"],
            "regresiones": full_ev["regresiones"],
            "net_delta":   full_ev["net_delta"],
            "misses_J":    tot - full_ev["top1_hits"],
        },
        "discovery_summary": {
            "n_cases":              len(discovery_results),
            "alpha_selected":       best_alpha,
            "net_delta_discovery":  best_alpha_entry["net_delta"],
        },
        "validation_summary": {
            "n_cases":               n_val,
            "net_delta_validation":  val_ev["net_delta"],
            "r1_delta_pct":          round(val_ev["r1_pct"] - 100 * r1_val_A / n_val, 4),
        },
        "transitions_rescue":     rescues,
        "transitions_regression": regressions,
    }

    out_dir = os.path.join(BASE_DIR, "docs")
    os.makedirs(out_dir, exist_ok=True)

    for name, rpt in [
        ("experiment_j_discovery_report.json", disc_report),
        ("experiment_j_validation_report.json", val_report),
        ("experiment_j_full_report.json", full_report),
    ]:
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rpt, fh, indent=2, ensure_ascii=False)
        print(f"\nReporte guardado: {path}")

    print()
    print("=" * 70)
    print("EXPERIMENTO J COMPLETO")
    print("=" * 70)
    print(f"alpha derivado en Discovery: {best_alpha}")
    print(f"R@1 global A -> J: {100*r1_A/tot:.2f}% -> {full_ev['r1_pct']:.2f}%")
    print(f"Neto global: {full_ev['net_delta']:+d}  (rescates={full_ev['rescates']}, regresiones={full_ev['regresiones']})")
    print(f"R@5 A -> J: {100*r5_A/tot:.2f}% -> {full_ev['r5_pct']:.2f}%")
    print()
    print("SIGUIENTE PASO (solo si validation_net_delta > 0):")
    print("  Reportar al auditor. No modificar produccion aun.")
    print("  Si R@5 cae, analizar tradeoff antes de cualquier decision.")


if __name__ == "__main__":
    main()
