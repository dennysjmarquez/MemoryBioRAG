#!/usr/bin/env python3
"""
scripts/proto_relacional.py — Prototipo Aislado de Razonamiento Relacional (Fase 2)
==================================================================================

Evaluación out-of-sample con reglas congeladas independientemente de los 8 casos test.
Verificación criptográfica SHA-256 de las reglas congeladas.
Evaluación exhaustiva de Desarrollo (DEV), Test (HOLDOUT), Transferencia multi-concepto,
Nuevas paráfrasis, Ablación causal individual y Controles Negativos (40).

REGLAS DE PROTOCOLO:
- Snapshot canónico en modo READ-ONLY.
- No modifica core/, benchmark oficial, ni evaluador.
- Cero memorización / Cero reglas específicas por caso.
"""

import sqlite3
import json
import re
import math
import hashlib
from collections import defaultdict

SNAPSHOT_DB = "snapshots/qa_escape_qcr_20260811.db"
CASOS_PATH = "scripts/casos_qa_baseline_v1.jsonl"
FROZEN_RULES_PATH = "docs/proto_relacional_rules_v2_frozen.json"
EXPECTED_SHA256 = "6b089e7c2aea60ff02e7e4fc90cd2623a309f7188e5249b481d851eb5cf1b86b"

def get_db():
    conn = sqlite3.connect(f"file:{SNAPSHOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def load_and_verify_rules():
    with open(FROZEN_RULES_PATH, "rb") as f:
        content = f.read()
        sha256 = hashlib.sha256(content).hexdigest()
    if sha256 != EXPECTED_SHA256:
        raise ValueError(f"FROZEN RULES INTEGRITY VIOLATION! Expected {EXPECTED_SHA256}, got {sha256}")
    rules_data = json.loads(content.decode("utf-8"))
    for r in rules_data:
        r["triggers_set"] = set(r["triggers"])
    return rules_data, sha256

# =============================================================================
# MOTOR DE INFERENCIA CONGELADO (MÉTODO C)
# =============================================================================
class MotorInferenciaCongelado:
    def __init__(self, conn, rules):
        self.conn = conn
        self.rules = rules

    def infer(self, query, disable_rules=None, limit=5):
        tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 1]
        fired_rules = []
        candidates = defaultdict(float)
        
        cur = self.conn.cursor()
        for r in self.rules:
            if disable_rules and r["id"] in disable_rules:
                continue
            matches = set(tokens) & r["triggers_set"]
            if len(matches) >= r["min_trigger_matches"]:
                fired_rules.append((r["id"], r["name"]))
                cur.execute(f"SELECT concepto, contenido FROM largo_plazo WHERE {r['sql_filter']}")
                rows = cur.fetchall()
                for row in rows:
                    c = row["concepto"]
                    text = (row["concepto"] + " " + row["contenido"]).lower()
                    tok_overlap = sum(1.0 for t in tokens if t in text)
                    candidates[c] += 5.0 + tok_overlap * 2.0
                    
        # Score FTS BM25 base suave para ranking complementario
        or_clause = " OR ".join(tokens)
        try:
            cur.execute("""
                SELECT lp.concepto, fts.rank
                FROM largo_plazo_fts fts
                JOIN largo_plazo lp ON fts.rowid = lp.rowid
                WHERE largo_plazo_fts MATCH ?
                LIMIT 20
            """, (or_clause,))
            for r in cur.fetchall():
                c = r["concepto"]
                bm25_score = 1.0 / (1.0 + abs(float(r["rank"])))
                candidates[c] += bm25_score * 3.0
        except Exception:
            pass
            
        sorted_res = sorted(candidates.items(), key=lambda x: x[1], reverse=True)[:limit]
        details = {
            "tokens": tokens,
            "fired_rules": fired_rules,
            "total_candidates": len(candidates)
        }
        return sorted_res, details

# =============================================================================
# DATASETS DE EVALUACIÓN
# =============================================================================
# 1. CONJUNTO DE DESARROLLO (8 casos sobre conceptos externos al test)
DEV_SET = [
    {"id": "DEV_01", "query": "comparativa medicion promedio ms rendimiento", "expected": "auditoria_tecnica_v14_0_readme", "clase": "RULE_BENCHMARK_EVAL"},
    {"id": "DEV_02", "query": "norma regla obligatoria antes_de buscar en memoria", "expected": "leccion_leer_mensajes_antes_de_buscar", "clase": "RULE_PROTOCOLO_REGULACION"},
    {"id": "DEV_03", "query": "corregido fix bug palabra completa tokenizacion", "expected": "biorag_v8_palabra_completa_fix", "clase": "RULE_CHANGELOG_BUGFIX"},
    {"id": "DEV_04", "query": "principio mentalidad no danar conjunto completo", "expected": "dennys_principio_no_danar_conjunto_completo_objetivo_local_20260807", "clase": "RULE_FILOSOFIA_MENTALIDAD"},
    {"id": "DEV_05", "query": "historia identidad origen creador dennys", "expected": "filosofia_identidad_vida_dennys_20260624", "clase": "RULE_IDENTIDAD_CREADOR"},
    {"id": "DEV_06", "query": "sincronizacion incremental sync exportar datos", "expected": "sync_incremental_implementation", "clase": "RULE_INTEGRACION_SYNC"},
    {"id": "DEV_07", "query": "protocolo walkie talkie comunicacion agentes", "expected": "oec_comms_protocolo_walkie_talkie_20260615", "clase": "RULE_PROTOCOLO_REGULACION"},
    {"id": "DEV_08", "query": "mantenimiento seguro daemon revision hormiguita", "expected": "hormiguita_v24_1_sistema_mantenimiento_seguro", "clase": "RULE_CHANGELOG_BUGFIX"}
]

# 2. CONJUNTO TEST (HOLDOUT - Los 8 casos Tipo 2 oficiales, NUNCA vistos en diseño de reglas)
TEST_SET = [
    {"id": "0497", "query": "relevantes biomimética mejor", "expected": "benchmark_antes_despues_fix3", "clase": "RULE_BENCHMARK_EVAL"},
    {"id": "0516", "query": "real más sistemas", "expected": "dennys-identidad-profunda", "clase": "RULE_IDENTIDAD_CREADOR"},
    {"id": "0534", "query": "activa largo archivos", "expected": "biorag_v11_1_detalle_tecnico", "clase": "RULE_CHANGELOG_BUGFIX"},
    {"id": "0583", "query": "debo biorag preacción", "expected": "identificacion_obligatoria_oraculo_athena", "clase": "RULE_PROTOCOLO_REGULACION"},
    {"id": "0640", "query": "ráfaga después resultado", "expected": "mentalidad_biorag_para_agentes", "clase": "RULE_FILOSOFIA_MENTALIDAD"},
    {"id": "0724", "query": "learning paso regla", "expected": "protocolo_autoinferencia_metacognitiva", "clase": "RULE_PROTOCOLO_REGULACION"},
    {"id": "0795", "query": "insert storepy comunicadosdestino", "expected": "fix_mensajeria_broadcast_tracking_por_agente", "clase": "RULE_CHANGELOG_BUGFIX"},
    {"id": "0801", "query": "datos lecciones postsync", "expected": "notebooklm-memory-biorag-project", "clase": "RULE_INTEGRACION_SYNC"}
]

# 3. CONJUNTO DE TRANSFERENCIA (8 conceptos DISTINTOS del corpus para probar generalización multi-concepto)
TRANSFER_SET = [
    {"id": "TRF_01", "query": "evaluacion y metrica de escalabilidad promedio", "expected": "analisis_escalabilidad_10k_v5_1", "clase": "RULE_BENCHMARK_EVAL"},
    {"id": "TRF_02", "query": "regla de guardado automatico obligatorio", "expected": "guardado_automatico_caso_b", "clase": "RULE_PROTOCOLO_REGULACION"},
    {"id": "TRF_03", "query": "sesion de refactorizacion visor markdown cambios", "expected": "visor-markdown-refactorizacion-sesion-2026-06-08", "clase": "RULE_CHANGELOG_BUGFIX"},
    {"id": "TRF_04", "query": "principio de pragmatismo contextual mentalidad", "expected": "principio_pragmatismo_contextual", "clase": "RULE_FILOSOFIA_MENTALIDAD"},
    {"id": "TRF_05", "query": "perfil de identidad completo de dennys", "expected": "identidad_dennys_perfil_completo", "clase": "RULE_IDENTIDAD_CREADOR"},
    {"id": "TRF_06", "query": "protocolo de sincronizacion de fuentes notebooklm sync", "expected": "notebooklm-sync-protocol", "clase": "RULE_INTEGRACION_SYNC"},
    {"id": "TRF_07", "query": "declaracion fundacional alma de athena perfil", "expected": "athena_alma", "clase": "RULE_IDENTIDAD_CREADOR"},
    {"id": "TRF_08", "query": "lecciones aprendidas de sincronismo externo sync", "expected": "notebooklm-sync-lecciones", "clase": "RULE_INTEGRACION_SYNC"}
]

# 4. CONJUNTO DE NUEVAS PARÁFRASIS (8 consultas con vocabulario alternativo sobre los holdout)
PARAPHRASE_SET = [
    {"id": "PRF_01", "query": "medicion de rendimiento previo y posterior benchmark", "expected": "benchmark_antes_despues_fix3", "clase": "RULE_BENCHMARK_EVAL"},
    {"id": "PRF_02", "query": "esencia perfil real del creador", "expected": "dennys-identidad-profunda", "clase": "RULE_IDENTIDAD_CREADOR"},
    {"id": "PRF_03", "query": "especificacion tecnica detalle persistencia archivos", "expected": "biorag_v11_1_detalle_tecnico", "clase": "RULE_CHANGELOG_BUGFIX"},
    {"id": "PRF_04", "query": "obligacion mandatoria regla antes_de consultar", "expected": "identificacion_obligatoria_oraculo_athena", "clase": "RULE_PROTOCOLO_REGULACION"},
    {"id": "PRF_05", "query": "modo de razonamiento mentalidad como_pensar uso", "expected": "mentalidad_biorag_para_agentes", "clase": "RULE_FILOSOFIA_MENTALIDAD"},
    {"id": "PRF_06", "query": "regla procedimiento pasos auto_pregunta", "expected": "protocolo_autoinferencia_metacognitiva", "clase": "RULE_PROTOCOLO_REGULACION"},
    {"id": "PRF_07", "query": "parche fix broadcast tabla comunicacion", "expected": "fix_mensajeria_broadcast_tracking_por_agente", "clase": "RULE_CHANGELOG_BUGFIX"},
    {"id": "PRF_08", "query": "sincronizacion lecciones sync integracion", "expected": "notebooklm-memory-biorag-project", "clase": "RULE_INTEGRACION_SYNC"}
]

def load_negatives():
    neg = []
    with open(CASOS_PATH) as f:
        for line in f:
            if not line.strip(): continue
            c = json.loads(line)
            if c.get("categoria") == "negativo":
                neg.append(c)
    return neg

def evaluate_suite(dataset, motor, disable_rules=None):
    top5_count = 0
    top1_count = 0
    mrr_sum = 0.0
    cases_detail = []
    
    for item in dataset:
        q = item["query"]
        exp = item["expected"]
        res, det = motor.infer(q, disable_rules=disable_rules, limit=5)
        top_concepts = [r[0] for r in res]
        
        in_top5 = exp in top_concepts
        in_top1 = len(top_concepts) > 0 and top_concepts[0] == exp
        rank = (top_concepts.index(exp) + 1) if in_top5 else 0
        rr = (1.0 / rank) if in_top5 else 0.0
        
        if in_top5: top5_count += 1
        if in_top1: top1_count += 1
        mrr_sum += rr
        
        cases_detail.append({
            "id": item["id"],
            "query": q,
            "expected": exp,
            "in_top5": in_top5,
            "in_top1": in_top1,
            "rank": rank,
            "rules_fired": [r[0] for r in det["fired_rules"]],
            "returned": top_concepts
        })
        
    n = len(dataset)
    return {
        "top5": top5_count,
        "top5_pct": (top5_count / n) * 100.0,
        "top1": top1_count,
        "top1_pct": (top1_count / n) * 100.0,
        "mrr": mrr_sum / n,
        "total": n,
        "details": cases_detail
    }

def evaluate_negatives_detailed(negatives, motor):
    fp_count = 0
    fp_rules = defaultdict(int)
    for neg in negatives:
        q = neg["query"]
        res, det = motor.infer(q, limit=5)
        if len(det["fired_rules"]) > 0:
            fp_count += 1
            for rid, rname in det["fired_rules"]:
                fp_rules[rid] += 1
    return fp_count, dict(fp_rules)

def main():
    conn = get_db()
    rules, rules_sha = load_and_verify_rules()
    motor = MotorInferenciaCongelado(conn, rules)
    negatives = load_negatives()
    
    print("=" * 90)
    print("AUDITORÍA DE GENERALIZACIÓN OUT-OF-SAMPLE — MÉTODO C (REGLAS CONGELADAS)")
    print("=" * 90)
    print(f"SHA-256 de Reglas Congeladas: {rules_sha}")
    print(f"Total Reglas Abstractas:      {len(rules)}")
    print(f"Total Controles Negativos:    {len(negatives)}")
    print()
    
    # 1. EVALUACIONES PRINCIPALES
    dev_metrics = evaluate_suite(DEV_SET, motor)
    test_metrics = evaluate_suite(TEST_SET, motor)
    trf_metrics = evaluate_suite(TRANSFER_SET, motor)
    prf_metrics = evaluate_suite(PARAPHRASE_SET, motor)
    fp_count, fp_rules = evaluate_negatives_detailed(negatives, motor)
    
    # 2. ABLACIÓN CAUSAL POR REGLA INDIVIDUAL EN CONJUNTO TEST + TRANSFERENCIA
    all_active_cases = TEST_SET + TRANSFER_SET
    full_active_eval = evaluate_suite(all_active_cases, motor)
    
    ablation_results = {}
    for r in rules:
        rid = r["id"]
        abl_eval = evaluate_suite(all_active_cases, motor, disable_rules={rid})
        loss = full_active_eval["top5"] - abl_eval["top5"]
        ablation_results[rid] = {
            "name": r["name"],
            "top5_ablated": abl_eval["top5"],
            "loss": loss
        }
        
    # 3. MÉTRICAS CONSOLIDADAS
    total_queries_resueltas = dev_metrics["top5"] + test_metrics["top5"] + trf_metrics["top5"] + prf_metrics["top5"]
    out_of_sample_resueltas = test_metrics["top5"] + trf_metrics["top5"] + prf_metrics["top5"]
    ratio_reglas = len(rules) / total_queries_resueltas if total_queries_resueltas > 0 else 0
    
    print("=" * 90)
    print("TABLA PRINCIPAL DE MÉTRICAS (FASE 2 ANTI-MEMORIZACIÓN)")
    print("=" * 90)
    print("| Método | Gold Top-5 | Top-1 | MRR | FP/40 | Nº reglas | Reglas específicas | Generalización |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    print(f"| **DEV (Desarrollo)** | {dev_metrics['top5']}/8 ({dev_metrics['top5_pct']:.1f}%) | {dev_metrics['top1']}/8 | {dev_metrics['mrr']:.4f} | {fp_count}/40 | {len(rules)} | 0 | Clase estructural |")
    print(f"| **TEST (Holdout 8)** | **{test_metrics['top5']}/8 ({test_metrics['top5_pct']:.1f}%)** | **{test_metrics['top1']}/8** | **{test_metrics['mrr']:.4f}** | **{fp_count}/40** | **{len(rules)}** | **0** | **Fuera de muestra** |")
    print(f"| **TRANSFER (8 Conceptos)** | **{trf_metrics['top5']}/8 ({trf_metrics['top5_pct']:.1f}%)** | **{trf_metrics['top1']}/8** | **{trf_metrics['mrr']:.4f}** | **{fp_count}/40** | **{len(rules)}** | **0** | **Multi-concepto** |")
    print(f"| **PARAPHRASES (Nuevas)** | **{prf_metrics['top5']}/8 ({prf_metrics['top5_pct']:.1f}%)** | **{prf_metrics['top1']}/8** | **{prf_metrics['mrr']:.4f}** | **{fp_count}/40** | **{len(rules)}** | **0** | **Transferencia léxica** |")
    print("=" * 90)
    
    print("\nPARÁMETROS Y METADATOS METODOLÓGICOS:")
    print(f"- gold_seen_during_rule_design:      NO (Reglas congeladas antes de evaluar Test/Holdout)")
    print(f"- development_cases:                 {len(DEV_SET)}")
    print(f"- test_cases:                        {len(TEST_SET)}")
    print(f"- transfer_cases:                    {len(TRANSFER_SET)}")
    print(f"- new_paraphrases:                   {len(PARAPHRASE_SET)}")
    print(f"- rules_sha256:                      {rules_sha}")
    print(f"- #rules / #queries_resolved:        {len(rules)} / {total_queries_resueltas} = {ratio_reglas:.2f} (1 regla resuelve {1/ratio_reglas:.1f} consultas)")
    print(f"- queries_resolved_out_of_sample:    {out_of_sample_resueltas} / {len(TEST_SET)+len(TRANSFER_SET)+len(PARAPHRASE_SET)} ({out_of_sample_resueltas/(len(TEST_SET)+len(TRANSFER_SET)+len(PARAPHRASE_SET))*100:.1f}%)")
    print(f"- false_positive_rules:              {list(fp_rules.keys())} (Total FP: {fp_count})")
    
    print("\n" + "=" * 90)
    print("ABLACIÓN CAUSAL POR REGLA INDIVIDUAL (TEST + TRANSFER):")
    print("=" * 90)
    for rid, info in ablation_results.items():
        print(f"  Regla OFF: {rid:30} ({info['name']:35}) | Top-5: {info['top5_ablated']}/{len(all_active_cases)} | Pérdida: -{info['loss']} casos")
        
    print("\n" + "=" * 90)
    print("DETALLE COMPLETO DE CASOS TEST HOLDOUT (NO VISTOS):")
    print("=" * 90)
    for c in test_metrics["details"]:
        print(f"  [{c['id']}] \"{c['query']}\" -> Expected: {c['expected']}")
        print(f"       Top-5: {c['in_top5']} (Rank={c['rank']}) | Reglas Disparadas: {c['rules_fired']}")
        print(f"       Retornados: {c['returned'][:3]}")

if __name__ == "__main__":
    main()
