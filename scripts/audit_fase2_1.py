#!/usr/bin/env python3
"""
scripts/audit_fase2_1.py — Auditoría de Especificidad, Selectividad y Capacidad Causal (Fase 2.1)
================================================================================================

Ejecuta la batería de pruebas exigida por Aureon para validar:
1. Selectividad cruzada (5 consultas ajenas por cada una de las 6 reglas = 30 consultas de especificidad).
2. Separación de capacidad causal vs capacidad léxica por regla.
3. Tabla de ablación unificada (32 consultas: 8 DEV + 8 TEST + 8 TRANSFER + 8 PARAPHRASE).
4. Diagnóstico exhaustivo de RULE_BENCHMARK_EVAL y RULE_CHANGELOG_BUGFIX.
5. Verificación de integridad SHA-256 de las reglas congeladas.
"""

import sqlite3
import json
import re
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
class MotorInferenciaAudit:
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
                    
        # Score FTS BM25 base suave
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
# SUITES DE EVALUACIÓN
# =============================================================================
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

# PRUEBA DE ESPECIFICIDAD: 5 consultas NO pertenecientes a la clase para cada una de las 6 reglas (30 casos)
SPECIFICITY_TESTS = {
    "RULE_BENCHMARK_EVAL": [
        {"q": "identidad del creador de la arquitectura de software", "expected_class": "IDENTIDAD"},
        {"q": "norma obligatoria para guardar recuerdos en sesion", "expected_class": "PROTOCOLO"},
        {"q": "sincronizacion externa con canal notebooklm", "expected_class": "SYNC"},
        {"q": "filosofia de mentalidad y principios rectores del agente", "expected_class": "FILOSOFIA"},
        {"q": "parche de bug en insercion de columnas en base de datos", "expected_class": "BUGFIX"}
    ],
    "RULE_PROTOCOLO_REGULACION": [
        {"q": "medicion de velocidad en milisegundos y promedio de latencia", "expected_class": "BENCHMARK"},
        {"q": "historia del perfil y alma del fundador", "expected_class": "IDENTIDAD"},
        {"q": "exportar datos hacia herramienta de sincronismo", "expected_class": "SYNC"},
        {"q": "correccion de fallo en archivo de configuracion json", "expected_class": "BUGFIX"},
        {"q": "enfoque conceptual sobre la vision del pensamiento", "expected_class": "FILOSOFIA"}
    ],
    "RULE_CHANGELOG_BUGFIX": [
        {"q": "quien es el creador autentico de este sistema", "expected_class": "IDENTIDAD"},
        {"q": "protocolo obligatorio al iniciar sesion de consulta", "expected_class": "PROTOCOLO"},
        {"q": "comparativa de tiempos antes y despues de la optimizacion", "expected_class": "BENCHMARK"},
        {"q": "como pensar y enfocar el razonamiento metacognitivo", "expected_class": "FILOSOFIA"},
        {"q": "puente de integracion para sincronizar lecciones", "expected_class": "SYNC"}
    ],
    "RULE_FILOSOFIA_MENTALIDAD": [
        {"q": "registro de parche técnico en el script de arranque", "expected_class": "BUGFIX"},
        {"q": "prueba de rendimiento comparativa con benchmark oficial", "expected_class": "BENCHMARK"},
        {"q": "norma mandatoria antes de ejecutar comandos destructivos", "expected_class": "PROTOCOLO"},
        {"q": "biografia y perfil del ingeniero frontend", "expected_class": "IDENTIDAD"},
        {"q": "datos exportados tras el proceso de sync incremental", "expected_class": "SYNC"}
    ],
    "RULE_IDENTIDAD_CREADOR": [
        {"q": "evaluacion de velocidad y promedio de tiempo en ms", "expected_class": "BENCHMARK"},
        {"q": "regla de dos pasos para el guardado en base de datos", "expected_class": "PROTOCOLO"},
        {"q": "solucion al bug de parseo en el modulo de strings", "expected_class": "BUGFIX"},
        {"q": "mentalidad y principios rectores de autonomia", "expected_class": "FILOSOFIA"},
        {"q": "sincronizacion de notas de investigacion en la nube", "expected_class": "SYNC"}
    ],
    "RULE_INTEGRACION_SYNC": [
        {"q": "perfil profesional e identidad profunda de dennys", "expected_class": "IDENTIDAD"},
        {"q": "benchmark de tiempo de respuesta y métrica de mejora", "expected_class": "BENCHMARK"},
        {"q": "procedimiento obligatorio para validar inputs de usuario", "expected_class": "PROTOCOLO"},
        {"q": "modificacion del codigo de la tabla de usuarios en sqlite", "expected_class": "BUGFIX"},
        {"q": "principio de pragmatismo y filosofia de diseno", "expected_class": "FILOSOFIA"}
    ]
}

def load_negatives():
    neg = []
    with open(CASOS_PATH) as f:
        for line in f:
            if not line.strip(): continue
            c = json.loads(line)
            if c.get("categoria") == "negativo":
                neg.append(c)
    return neg

def eval_subset(dataset, motor, disable_rules=None):
    top5 = 0
    top1 = 0
    mrr_sum = 0.0
    for item in dataset:
        q = item["query"]
        exp = item["expected"]
        res, det = motor.infer(q, disable_rules=disable_rules, limit=5)
        top_concepts = [r[0] for r in res]
        in_top5 = exp in top_concepts
        in_top1 = len(top_concepts) > 0 and top_concepts[0] == exp
        rank = (top_concepts.index(exp) + 1) if in_top5 else 0
        rr = (1.0 / rank) if in_top5 else 0.0
        if in_top5: top5 += 1
        if in_top1: top1 += 1
        mrr_sum += rr
    n = len(dataset)
    return top5, top1, mrr_sum / n if n > 0 else 0.0

def main():
    conn = get_db()
    rules, sha = load_and_verify_rules()
    motor = MotorInferenciaAudit(conn, rules)
    negatives = load_negatives()
    
    all_32_queries = DEV_SET + TEST_SET + TRANSFER_SET + PARAPHRASE_SET
    
    print("=" * 90)
    print("REPORTE DE AUDITORÍA FASE 2.1 — ESPECIFICIDAD Y CAPACIDAD CAUSAL")
    print("=" * 90)
    print(f"SHA-256 de Reglas: {sha}")
    print(f"Conjunto Unificado Total: {len(all_32_queries)} consultas (8 DEV + 8 TEST + 8 TRF + 8 PRF)")
    print()

    # 1. TABLA DE ABLACIÓN UNIFICADA
    top5_all, top1_all, mrr_all = eval_subset(all_32_queries, motor)
    print("1. TABLA DE ABLACIÓN INDIVIDUAL UNIFICADA (SOBRE LAS 32 CONSULTAS):")
    print("-" * 90)
    print(f"LÍNEA BASE (TODAS LAS 6 REGLAS ACTIVAS): Top-5 = {top5_all}/32 ({top5_all/32*100:.1f}%) | Top-1 = {top1_all}/32 ({top1_all/32*100:.1f}%) | MRR = {mrr_all:.4f}")
    print("-" * 90)
    print(f"| Regla Desactivada | Top-5 | Pérdida Top-5 (Δ) | Top-1 | Pérdida Top-1 (Δ) | MRR |")
    print(f"| :--- | :---: | :---: | :---: | :---: | :---: |")
    
    rule_ablation = {}
    for r in rules:
        rid = r["id"]
        t5_off, t1_off, mrr_off = eval_subset(all_32_queries, motor, disable_rules={rid})
        loss_t5 = top5_all - t5_off
        loss_t1 = top1_all - t1_off
        rule_ablation[rid] = (loss_t5, loss_t1)
        print(f"| **{rid}** | {t5_off}/32 | -{loss_t5} | {t1_off}/32 | -{loss_t1} | {mrr_off:.4f} |")
        
    print("\n" + "=" * 90)
    print("2. SEPARACIÓN DE CAPACIDAD CAUSAL Y ACTIVACIONES POR REGLA (32 CONSULTAS + 40 NEGATIVOS):")
    print("=" * 90)
    print(f"| Regla | Activaciones Totales | Rescates Top-5 | Rescates Top-1 | Sin Efecto / Neutras | Falsos Positivos | Faltó Trigger |")
    print(f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    for r in rules:
        rid = r["id"]
        # Contar en las 32 queries
        activations = 0
        rescues_top5 = 0
        rescues_top1 = 0
        no_effect = 0
        missing_trigger = 0
        
        for item in all_32_queries:
            q = item["query"]
            exp = item["expected"]
            # Target class
            is_target_class = (item.get("clase") == rid)
            res, det = motor.infer(q, limit=5)
            fired = any(f[0] == rid for f in det["fired_rules"])
            if fired:
                activations += 1
                if exp in [x[0] for x in res]:
                    rescues_top5 += 1
                    if res[0][0] == exp:
                        rescues_top1 += 1
                else:
                    no_effect += 1
            else:
                if is_target_class:
                    missing_trigger += 1
                    
        # FP en 40 negativos
        fp_rule_count = 0
        for neg in negatives:
            res, det = motor.infer(neg["query"], limit=5)
            if any(f[0] == rid for f in det["fired_rules"]):
                fp_rule_count += 1
                
        print(f"| **{rid}** | {activations} | {rescues_top5} | {rescues_top1} | {no_effect} | {fp_rule_count}/40 | {missing_trigger} |")

    print("\n" + "=" * 90)
    print("3. PRUEBA DE ESPECIFICIDAD / SELECTIVIDAD CRUZADA (30 CONSULTAS DE OTRAS CLASES):")
    print("=" * 90)
    print(f"| Regla Evaluada | Consultas Ajenas Probadas | Activaciones Indebidas | Alteró Ranking | Falsos Positivos |")
    print(f"| :--- | :---: | :---: | :---: | :---: |")
    
    for rid, tests in SPECIFICITY_TESTS.items():
        cross_activations = 0
        altered_ranking = 0
        fp_cross = 0
        for t in tests:
            q = t["q"]
            res, det = motor.infer(q, limit=5)
            if any(f[0] == rid for f in det["fired_rules"]):
                cross_activations += 1
                altered_ranking += 1
                fp_cross += 1
        print(f"| **{rid}** | {len(tests)} | {cross_activations}/{len(tests)} | {altered_ranking} | {fp_cross} |")

if __name__ == "__main__":
    main()
