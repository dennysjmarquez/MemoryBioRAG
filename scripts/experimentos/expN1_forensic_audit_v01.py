#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expN1_forensic_audit_v01.py
=============================================================================
EXP-N1: AUDITORÍA FORENSE COMPLETA DE SCG-v0.1 SOBRE LOS 8 CASOS A0-DEV
=============================================================================
Protocolo Aureon/Arcadia:
    1. Estructura canónica completa de cada query A0-DEV.
    2. Operaciones, roles, relaciones y propiedades detectadas.
    3. Todas las hipótesis composicionales generadas por caso.
    4. Regla exacta que generó cada candidato del pool.
    5. Componentes y relaciones que hicieron compatible a cada candidato.
    6. Para el Gold: exactamente qué evidencia produjo su admisión o rechazo.
    7. Top-20 candidatos no-Gold y por qué fueron admitidos.
    8. Dependencia de lexical stems, aliases, sinonimia textual, Concept Hubs,
       synapsis directas o mappings Gold-conditioned.
    9. Score de generación antes del scoring final.
    10. Candidate Generation Recall y CandidatePool.
    11. Flag explícito `lexical_dependency=true/false` para cada transformación.
    12. Auditoría focalizada sobre OOF_POS_30: ¿composición real o relajación amplia?
=============================================================================
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
import re
import unicodedata
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional, Set, FrozenSet
import numpy as np

sys.path.insert(0, os.path.abspath("."))

# Reutilizar el motor SCG-v0.1 existente sin modificarlo
from scripts.experimentos.expN_scg_v01 import (
    SCGEngine,
    StructuralForm,
    ComposedHypothesis,
    parsear_query,
    generar_hipotesis,
    normalizar,
    tokenizar,
    OPERATION_DETECTORS,
    RELATION_DETECTORS,
    PROPERTY_DETECTORS,
    SPANISH_STOPWORDS,
    DB_PATH,
    LABELS_PATH,
    DEV_DATASET_PATH,
)

OUTPUT_AUDIT_PATH = "docs/expN1_forensic_audit_results.json"

A0_STRICT_CASES = {"OOF_POS_11", "OOF_POS_19", "OOF_POS_21",
                   "OOF_POS_29", "OOF_POS_30", "OOF_POS_48"}
NO_A0_CASES = {"OOF_POS_40", "OOF_POS_49"}


def auditar_lexical_leakage(query: str, nodo: str, sinonimos: Set[str], conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Audita exhaustivamente si existe coincidencia léxica directa, parcial o por sinónimos
    entre los tokens de la query y el nodo Gold (nombre, sinónimos, contenido en DB).
    """
    q_tokens = tokenizar(query)
    node_tokens = tokenizar(nodo)
    syn_tokens = sinonimos

    # Contenido del nodo en DB
    c = conn.cursor()
    row = c.execute("SELECT contenido, categoria FROM largo_plazo WHERE concepto = ?", (nodo,)).fetchone()
    content_text = str(row[0]) if row and row[0] is not None else ""
    cat_text = str(row[1]) if row and row[1] is not None else ""
    content_tokens = tokenizar(content_text)
    cat_tokens = tokenizar(cat_text)

    direct_title_overlap = q_tokens.intersection(node_tokens)
    synonym_overlap = q_tokens.intersection(syn_tokens)
    content_overlap = q_tokens.intersection(content_tokens)
    category_overlap = q_tokens.intersection(cat_tokens)

    # Coincidencia de prefijos de 4+ caracteres
    prefix_overlap = set()
    for qt in q_tokens:
        if len(qt) >= 4:
            for nt in node_tokens.union(syn_tokens):
                if len(nt) >= 4 and (qt.startswith(nt[:4]) or nt.startswith(qt[:4])):
                    prefix_overlap.add(f"{qt}~{nt}")

    has_leakage = bool(direct_title_overlap or synonym_overlap)
    return {
        "lexical_dependency": has_leakage,
        "direct_title_overlap": sorted(direct_title_overlap),
        "synonym_overlap": sorted(synonym_overlap),
        "prefix_stem_overlap": sorted(prefix_overlap),
        "content_overlap_tokens_count": len(content_overlap),
        "category_overlap": sorted(category_overlap),
        "is_strict_a0": len(direct_title_overlap) == 0 and len(synonym_overlap) == 0 and len(prefix_overlap) == 0
    }


def ejecutar_auditoria_forense():
    print("=============================================================================")
    print("EXP-N1: AUDITORÍA FORENSE COMPLETA DE SCG-v0.1 SOBRE A0-DEV (8 CASOS)")
    print("=============================================================================")

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels = json.load(f)
    with open(DEV_DATASET_PATH, "r", encoding="utf-8") as f:
        dev_cases = json.load(f)["cases"]

    engine = SCGEngine(con, labels)
    c = con.cursor()

    reporte_casos = []

    for cs in dev_cases:
        cid = cs["id"]
        q = cs["query"]
        gold = cs["gold"]
        is_strict = cid in A0_STRICT_CASES

        print(f"\n─────────────────────────────────────────────────────────────────────────────")
        print(f"CASE [{cid}] (Strict A0: {is_strict}) — Query: \"{q}\"")
        print(f"Gold Target: {gold}")
        print(f"─────────────────────────────────────────────────────────────────────────────")

        # 1. Parsing estructural
        sf = parsear_query(q)
        hypotheses = generar_hipotesis(sf)

        # 2. Generación de candidatos y trazas
        pool, trazabilidad, meta = engine.generar_candidate_pool(q)
        ranked = engine.rankear_candidate_pool(q, pool, trazabilidad, k=20)

        # 3. Auditoría del Gold
        gold_row = c.execute("SELECT concepto, categoria, sinonimos, estado FROM largo_plazo WHERE concepto = ?", (gold,)).fetchone()
        gold_exists = gold_row is not None
        gold_dims = engine.dims_por_nodo.get(gold, set())
        gold_accion_dims = engine.accion_dims_por_nodo.get(gold, set())
        gold_syns = engine.sinonimos_por_nodo.get(gold, set())
        gold_degree = len(engine.sinapsis_out.get(gold, {}))

        gold_in_pool = gold in pool
        gold_best_h = None
        gold_best_sc = 0.0
        gold_trails = []

        if gold_exists:
            for h in hypotheses:
                sc, tr = engine.evaluar_compatibilidad_hipotesis(gold, h)
                if sc > gold_best_sc:
                    gold_best_sc = sc
                    gold_best_h = h.name
                    gold_trails = tr

        # 4. Auditoría de Fuga Léxica
        leakage_audit = auditar_lexical_leakage(q, gold, gold_syns, con)

        # 5. Top-20 no-Gold admitidos y razones
        top20_audit = []
        for rk_item in ranked[:20]:
            cand = rk_item["node"]
            cand_dims = sorted(list(engine.dims_por_nodo.get(cand, set())))
            cand_traz = trazabilidad.get(cand, {})
            top20_audit.append({
                "rank": rk_item["rank"],
                "node": cand,
                "is_gold": cand == gold,
                "score_final": rk_item["score"],
                "score_compatibilidad": cand_traz.get("score_compatibilidad", 0.0),
                "mejor_hipotesis": cand_traz.get("mejor_hipotesis"),
                "dims_sample": [f"{t}:{d}" for t, d in cand_dims[:4]],
                "trails": cand_traz.get("trails", [])[:3]
            })

        # 6. Distribución de hipótesis que admitieron candidatos en el pool
        hip_counts = defaultdict(int)
        for cand, tr in trazabilidad.items():
            hip_counts[tr.get("mejor_hipotesis", "UNKNOWN")] += 1

        # 7. Diagnóstico formal del caso
        diag = {
            "case_id": cid,
            "is_strict_a0": is_strict,
            "query": q,
            "gold": gold,
            "gold_metadata": {
                "exists": gold_exists,
                "estado": gold_row[3] if gold_row else None,
                "categoria": gold_row[1] if gold_row else None,
                "degree": gold_degree,
                "action_dims": sorted(gold_accion_dims),
                "all_dims": [f"{t}:{d}" for t, d in sorted(gold_dims)],
                "synonyms": sorted(gold_syns)[:6]
            },
            "structural_parse": {
                "raw_tokens": sorted(sf.raw_tokens),
                "operations": sorted(sf.operations),
                "relations": sorted(sf.relations),
                "properties": sorted(sf.properties),
                "modality": sf.modality,
                "polarity": sf.polarity,
                "confidence": sf.confidence,
                "missing": sf.missing
            },
            "hypotheses_generated": [
                {
                    "name": h.name,
                    "ops_req": sorted(h.ops_req),
                    "rels_req": sorted(h.rels_req),
                    "props_req": sorted(h.props_req),
                    "db_dim_req": sorted(h.db_dim_req),
                    "score_base": h.score_base
                } for h in hypotheses
            ],
            "generation_metrics": {
                "pool_size": len(pool),
                "pool_pct_corpus": meta["pool_pct_corpus"],
                "gold_in_pool": gold_in_pool,
                "gold_compat_score": round(gold_best_sc, 4),
                "gold_best_hypothesis": gold_best_h,
                "gold_trails": gold_trails,
                "gold_rank": next((x["rank"] for x in ranked if x["node"] == gold), None),
            },
            "hypothesis_admission_breakdown": dict(hip_counts),
            "lexical_audit": leakage_audit,
            "top20_non_gold_sample": top20_audit[:5]
        }
        reporte_casos.append(diag)

        # Print resumen de consola
        print(f"• Parse: Ops={sorted(sf.operations)} | Rels={sorted(sf.relations)} | Props={sorted(sf.properties)}")
        print(f"• Hipótesis ({len(hypotheses)}): {[h.name for h in hypotheses]}")
        print(f"• Pool Size: {len(pool)} ({meta['pool_pct_corpus']}%) | Gold in Pool: {gold_in_pool}")
        print(f"• Gold Compat Score: {gold_best_sc:.4f} (Threshold=1.20) | Best H: {gold_best_h}")
        print(f"• Gold Trails: {gold_trails}")
        print(f"• Lexical Leakage Audit: dependency={leakage_audit['lexical_dependency']} | Strict A0={leakage_audit['is_strict_a0']}")

    # =========================================================================
    # AUDITORÍA FOCALIZADA: OOF_POS_30
    # =========================================================================
    print("\n=============================================================================")
    print("AUDITORÍA FOCALIZADA: OOF_POS_30 (activos_dormidos_hermana)")
    print("=============================================================================")
    c30 = next(c for c in reporte_casos if c["case_id"] == "OOF_POS_30")
    print(f"Query: \"{c30['query']}\"")
    print(f"Gold: {c30['gold']}")
    print(f"Gold Dims en DB: {c30['gold_metadata']['all_dims']}")
    print(f"Gold Action Dims: {c30['gold_metadata']['action_dims']}")
    print(f"Operaciones detectadas en query: {c30['structural_parse']['operations']}")
    print(f"Propiedades detectadas en query: {c30['structural_parse']['properties']}")
    print(f"Hipótesis que admitió a OOF_POS_30: {c30['generation_metrics']['gold_best_hypothesis']}")
    print(f"Trails de coincidencia: {c30['generation_metrics']['gold_trails']}")
    print(f"Score de compatibilidad: {c30['generation_metrics']['gold_compat_score']}")

    # Guardar reporte
    with open(OUTPUT_AUDIT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "experiment": "EXP-N1: Forensic Audit of SCG-v0.1 on A0-DEV",
            "hashes": {
                "db_snapshot": hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest(),
                "labels": hashlib.sha256(open(LABELS_PATH, "rb").read()).hexdigest(),
            },
            "cases": reporte_casos
        }, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Auditoría guardada en: {OUTPUT_AUDIT_PATH}")
    con.close()


if __name__ == "__main__":
    ejecutar_auditoria_forense()
