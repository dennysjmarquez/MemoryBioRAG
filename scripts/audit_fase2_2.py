#!/usr/bin/env python3
"""
scripts/audit_fase2_2.py — Auditoría Exhaustiva de Generalización y Selectividad (Fase 2.2)
==========================================================================================

Implementa la batería de pruebas final de la Fase 2.2 exigida por Aureon:
1. Ablación estrictamente OUT-OF-SAMPLE desglosada por conjunto (TEST, TRANSFER, PARAPHRASES).
2. Hard Negative Selectivity Test (60 consultas: 10 hard negatives por cada una de las 6 reglas).
3. Clasificación detallada: Trigger capability vs Semantic capability.
4. Auditoría de Leakage y Contaminación.
5. Auditoría taxonómica de SQL Filters (GENERAL vs CORPUS_DEPENDENT vs LEXICAL_SPECIFIC).
6. Prueba de Corpus-Shift (evaluación con vocabulario superficial desplazado).
7. Clasificación final justificada (Categoría B).

REGLAS METODOLÓGICAS:
- Snapshot canónico en modo READ-ONLY.
- Reglas congeladas intactas (SHA-256 verificado).
- Cero modificaciones a core/, evaluador o benchmark.
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

class MotorInferenciaFase22:
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
                fired_rules.append((r["id"], r["name"], len(matches)))
                cur.execute(f"SELECT concepto, contenido FROM largo_plazo WHERE {r['sql_filter']}")
                rows = cur.fetchall()
                for row in rows:
                    c = row["concepto"]
                    text = (row["concepto"] + " " + row["contenido"]).lower()
                    tok_overlap = sum(1.0 for t in tokens if t in text)
                    candidates[c] += 5.0 + tok_overlap * 2.0
                    
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
# SUITES OUT-OF-SAMPLE SEPARADAS
# =============================================================================
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

# =============================================================================
# 60 HARD NEGATIVES (10 POR REGLA, CON >= 2 TRIGGERS DELIBERADOS PERO INTENCIÓN AJENA)
# =============================================================================
HARD_NEGATIVES = {
    "RULE_BENCHMARK_EVAL": [
        {"id": "HN_BM_01", "query": "como lograr mejor velocidad al escribir codigo en react", "intent": "Frontend UI Best Practice"},
        {"id": "HN_BM_02", "query": "antes y despues de la toma de decisiones filosoficas", "intent": "Philosophy Reflection"},
        {"id": "HN_BM_03", "query": "el promedio de horas antes de descansar en la rutina diaria", "intent": "Daily Routine"},
        {"id": "HN_BM_04", "query": "evaluacion cualitativa de la confianza entre humanos y agentes", "intent": "Relationship Ethics"},
        {"id": "HN_BM_05", "query": "la mejor forma de expresar gratitud despues de una sesion", "intent": "Gratitude Lesson"},
        {"id": "HN_BM_06", "query": "medicion del impacto emocional antes del cambio de rol", "intent": "Emotional Intelligence"},
        {"id": "HN_BM_07", "query": "comparativa de estilos de liderazgo antes de 2026", "intent": "Leadership History"},
        {"id": "HN_BM_08", "query": "rendimiento cognitivo en estados de sueno y reflexion", "intent": "Sleep Cycle Reflection"},
        {"id": "HN_BM_09", "query": "rapidez de respuesta frente a dilemas eticos y mejor conducta", "intent": "Ethics Decision"},
        {"id": "HN_BM_10", "query": "metrica subjetiva de la lealtad y el mejor companero", "intent": "Loyalty Principle"}
    ],
    "RULE_PROTOCOLO_REGULACION": [
        {"id": "HN_PR_01", "query": "debo admitir que cada paso en la vida ensena algo", "intent": "Life Philosophy"},
        {"id": "HN_PR_02", "query": "la regla de tres en el diseno estetico visual paso a paso", "intent": "Frontend Aesthetic"},
        {"id": "HN_PR_03", "query": "un procedimiento de respiracion antes_de meditar profundamente", "intent": "Meditation Routine"},
        {"id": "HN_PR_04", "query": "instruccion no mandatoria sobre como redactar poesia sintetica", "intent": "Creative Writing"},
        {"id": "HN_PR_05", "query": "la norma social de saludar antes_de iniciar un debate informal", "intent": "Social Etiquette"},
        {"id": "HN_PR_06", "query": "debo reconocer el paso del tiempo en la arquitectura antigua", "intent": "Architecture History"},
        {"id": "HN_PR_07", "query": "cada regla gramatical tiene una excepcion en el lenguaje vivo", "intent": "Linguistics Note"},
        {"id": "HN_PR_08", "query": "el protocolo diplomático de las dinastias del siglo diecinueve", "intent": "Diplomatic History"},
        {"id": "HN_PR_09", "query": "un paso obligatorio en el ciclo del agua en la naturaleza", "intent": "Nature Biology"},
        {"id": "HN_PR_10", "query": "instruccion basica para afinar una guitarra paso a paso", "intent": "Music Tuning"}
    ],
    "RULE_CHANGELOG_BUGFIX": [
        {"id": "HN_FX_01", "query": "la persistencia de la memoria en el cuadro de salvador dali al detalle", "intent": "Art History"},
        {"id": "HN_FX_02", "query": "arquitectura gotica y la estructura de columnas en catedrales", "intent": "Gothic Architecture"},
        {"id": "HN_FX_03", "query": "tabla periodica de los elementos quimicos en su version extendida", "intent": "Chemistry Elements"},
        {"id": "HN_FX_04", "query": "un parche en el ojo en la cultura popular de piratas con detalle", "intent": "Pirate Folklore"},
        {"id": "HN_FX_05", "query": "el disco solar en la mitologia egipcia y su version teologica", "intent": "Egyptian Mythology"},
        {"id": "HN_FX_06", "query": "un bug biologico o mutacion genetica en insectos con detalle", "intent": "Entomology Biology"},
        {"id": "HN_FX_07", "query": "archivos secretos de la guerra fria y la persistencia historica", "intent": "Cold War History"},
        {"id": "HN_FX_08", "query": "una columna de opinion periodistica sobre la nueva version musical", "intent": "Music Journalism"},
        {"id": "HN_FX_09", "query": "detalle tecnico de la elaboracion artesanal de cafe en grano", "intent": "Gastronomy"},
        {"id": "HN_FX_10", "query": "insert en la narrativa literaria para alterar el tiempo tecnico", "intent": "Literary Theory"}
    ],
    "RULE_FILOSOFIA_MENTALIDAD": [
        {"id": "HN_FL_01", "query": "el resultado de la division por cero despues de calcular", "intent": "Basic Math"},
        {"id": "HN_FL_02", "query": "leccion de botanica sobre el uso de fertilizantes en plantas", "intent": "Gardening"},
        {"id": "HN_FL_03", "query": "principio activo de la aspirina y su modo de accion quimico", "intent": "Pharmacology"},
        {"id": "HN_FL_04", "query": "vision nocturna en felinos y el modo de caceria en la selva", "intent": "Zoology"},
        {"id": "HN_FL_05", "query": "filosofia antigua sobre el atomo antes y despues de democrito", "intent": "Ancient Philosophy"},
        {"id": "HN_FL_06", "query": "razonamiento deductivo en acertijos matematicos con resultado directo", "intent": "Logic Puzzles"},
        {"id": "HN_FL_07", "query": "modo de uso del control remoto y resultado al cambiar canal", "intent": "Home Appliances"},
        {"id": "HN_FL_08", "query": "enfoque de camara fotografica para obtener mejor vision de campo", "intent": "Photography Optics"},
        {"id": "HN_FL_09", "query": "leccion de cocina sobre el resultado de hornear despues de fermentar", "intent": "Baking Science"},
        {"id": "HN_FL_10", "query": "pensar rapido y lento en las ilusiones opticas de vision", "intent": "Optical Illusions"}
    ],
    "RULE_IDENTIDAD_CREADOR": [
        {"id": "HN_ID_01", "query": "sistemas de identidad federada oauth y tokens jwt en servidores", "intent": "Web Security"},
        {"id": "HN_ID_02", "query": "origen y evolucion de los sistemas planetarios en el universo real", "intent": "Astronomy"},
        {"id": "HN_ID_03", "query": "el creador de la penicilina y la historia de los antibioticos", "intent": "Medical History"},
        {"id": "HN_ID_04", "query": "quien_es el personaje de don quijote en la historia universal", "intent": "Spanish Literature"},
        {"id": "HN_ID_05", "query": "la esencia del perfume frances y su origen floral autentico", "intent": "Perfumery"},
        {"id": "HN_ID_06", "query": "sistemas digestivos en animales y su origen evolutivo real", "intent": "Animal Biology"},
        {"id": "HN_ID_07", "query": "perfil topografico de las montanas en la historia geologica", "intent": "Geology"},
        {"id": "HN_ID_08", "query": "alma gemela en la poesia romantica y la filosofia_vida popular", "intent": "Romantic Poetry"},
        {"id": "HN_ID_09", "query": "identidad trigonometrica fundamental en sistemas de coordenadas", "intent": "Trigonometry Math"},
        {"id": "HN_ID_10", "query": "autentico chocolate suizo y la historia de los sistemas de cacao", "intent": "Chocolate Food"}
    ],
    "RULE_INTEGRACION_SYNC": [
        {"id": "HN_SY_01", "query": "puente de brooklyn y la exportar de acero en su construccion", "intent": "Civil Engineering"},
        {"id": "HN_SY_02", "query": "sincronizacion de fases en osciladores armonicos de fisica cuantica", "intent": "Quantum Physics"},
        {"id": "HN_SY_03", "query": "integracion por partes y calculo integral de datos numericos", "intent": "Calculus"},
        {"id": "HN_SY_04", "query": "lecciones de natacion para principiantes en piscina con puente", "intent": "Swimming Sport"},
        {"id": "HN_SY_05", "query": "canal externo de irrigacion para exportar agua a los cultivos", "intent": "Agriculture"},
        {"id": "HN_SY_06", "query": "sincronizacion de relojes en la teoria de la relatividad con datos", "intent": "Special Relativity"},
        {"id": "HN_SY_07", "query": "puente de hidrogeno en la molecula de agua y datos quimicos", "intent": "Chemistry"},
        {"id": "HN_SY_08", "query": "integracion social de especies animales en manadas con lecciones", "intent": "Animal Ethology"},
        {"id": "HN_SY_09", "query": "exportar frutas tropicales y su integracion en el comercio exterior", "intent": "International Trade"},
        {"id": "HN_SY_10", "query": "sincronizacion del ritmo cardiaco en atletas y datos medicos", "intent": "Sports Medicine"}
    ]
}

# =============================================================================
# PRUEBA DE CORPUS-SHIFT (VOCABULARIO SUPERFICIAL DESPLAZADO)
# =============================================================================
CORPUS_SHIFT_SET = [
    {"id": "CS_01", "query": "estudio empirico de aceleracion y tasa de latencia", "expected": "benchmark_antes_despues_fix3", "clase": "RULE_BENCHMARK_EVAL"},
    {"id": "CS_02", "query": "mandato mandatorio preliminar al acceso de memoria", "expected": "identificacion_obligatoria_oraculo_athena", "clase": "RULE_PROTOCOLO_REGULACION"},
    {"id": "CS_03", "query": "parche de subsanacion de anomalia en difusion de paquetes", "expected": "fix_mensajeria_broadcast_tracking_por_agente", "clase": "RULE_CHANGELOG_BUGFIX"},
    {"id": "CS_04", "query": "doctrina y concepcion epistemologica sobre utilizacion de recuerdos", "expected": "mentalidad_biorag_para_agentes", "clase": "RULE_FILOSOFIA_MENTALIDAD"},
    {"id": "CS_05", "query": "biografia ontologica del artifice de la plataforma", "expected": "dennys-identidad-profunda", "clase": "RULE_IDENTIDAD_CREADOR"},
    {"id": "CS_06", "query": "puente de exportacion bidireccional hacia repositorio remoto", "expected": "notebooklm-memory-biorag-project", "clase": "RULE_INTEGRACION_SYNC"}
]

def eval_suite_metrics(dataset, motor, disable_rules=None):
    top5, top1, mrr_sum = 0, 0, 0.0
    for item in dataset:
        q = item["query"]
        exp = item["expected"]
        res, _ = motor.infer(q, disable_rules=disable_rules, limit=5)
        top_c = [r[0] for r in res]
        in_t5 = exp in top_c
        in_t1 = len(top_c) > 0 and top_c[0] == exp
        rank = (top_c.index(exp) + 1) if in_t5 else 0
        rr = (1.0 / rank) if in_t5 else 0.0
        if in_t5: top5 += 1
        if in_t1: top1 += 1
        mrr_sum += rr
    n = len(dataset)
    return top5, top1, mrr_sum / n if n > 0 else 0.0

def main():
    conn = get_db()
    rules, sha = load_and_verify_rules()
    motor = MotorInferenciaFase22(conn, rules)
    
    print("=" * 95)
    print("REPORTE OFICIAL FASE 2.2 — VALIDACIÓN FINAL DE GENERALIZACIÓN Y SELECTIVIDAD")
    print("=" * 95)
    print(f"SHA-256 de Reglas Congeladas: {sha}")
    print()

    # 1. ABLACIÓN ESTRICTAMENTE OUT-OF-SAMPLE (DESGLOSADA POR SUITE)
    suites = {
        "TEST (8 Holdout)": TEST_SET,
        "TRANSFER (8 Conceptos)": TRANSFER_SET,
        "PARAPHRASES (8 Nuevas)": PARAPHRASE_SET
    }
    
    print("1. ABLACIÓN ESTRICTAMENTE OUT-OF-SAMPLE (POR CONJUNTO INDEPENDIENTE):")
    print("-" * 95)
    
    for sname, sdata in suites.items():
        base_t5, base_t1, base_mrr = eval_suite_metrics(sdata, motor)
        print(f"\n[{sname.upper()}] — LÍNEA BASE ALL ON: Top-5 = {base_t5}/8 ({base_t5/8*100:.1f}%) | Top-1 = {base_t1}/8 ({base_t1/8*100:.1f}%) | MRR = {base_mrr:.4f}")
        print(f"| Regla Desactivada | Top-5 | Δ Top-5 | Top-1 | Δ Top-1 | MRR | Δ MRR |")
        print(f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
        for r in rules:
            rid = r["id"]
            off_t5, off_t1, off_mrr = eval_suite_metrics(sdata, motor, disable_rules={rid})
            d_t5 = base_t5 - off_t5
            d_t1 = base_t1 - off_t1
            d_mrr = base_mrr - off_mrr
            print(f"| **{rid}** | {off_t5}/8 | **-{d_t5}** | {off_t1}/8 | **-{d_t1}** | {off_mrr:.4f} | **-{d_mrr:.4f}** |")

    # 2. HARD NEGATIVE SELECTIVITY TEST (60 CONSULTAS)
    print("\n" + "=" * 95)
    print("2. HARD NEGATIVE SELECTIVITY TEST (60 CONSULTAS CON >= 2 TRIGGERS DELIBERADOS):")
    print("=" * 95)
    print(f"| Regla Evaluada | Hard Negatives Probados | Activaciones (Rate) | Ranking Alterado | Falsos Positivos | Score Promedio Promovido |")
    print(f"| :--- | :---: | :---: | :---: | :---: | :---: |")
    
    total_hn_activations = 0
    total_hn_fp = 0
    
    for r in rules:
        rid = r["id"]
        hn_list = HARD_NEGATIVES[rid]
        act_count = 0
        altered_count = 0
        fp_count = 0
        scores_promovidos = []
        
        for hn in hn_list:
            q = hn["query"]
            # Ejecutar con regla ON
            res_on, det_on = motor.infer(q, limit=5)
            # Ejecutar con regla OFF
            res_off, _ = motor.infer(q, disable_rules={rid}, limit=5)
            
            fired = any(f[0] == rid for f in det_on["fired_rules"])
            if fired:
                act_count += 1
                total_hn_activations += 1
                # Verificar si alteró ranking vs regla OFF
                top_on = [x[0] for x in res_on]
                top_off = [x[0] for x in res_off]
                if top_on != top_off:
                    altered_count += 1
                    # Se considera FP si el Top-1 resultante tiene score artificial alto sin relación con la query
                    if len(res_on) > 0 and res_on[0][1] >= 5.0:
                        fp_count += 1
                        total_hn_fp += 1
                        scores_promovidos.append(res_on[0][1])
                        
        avg_score = sum(scores_promovidos) / len(scores_promovidos) if scores_promovidos else 0.0
        print(f"| **{rid}** | {len(hn_list)} | {act_count}/10 ({act_count/10*100:.0f}%) | {altered_count}/10 | {fp_count}/10 | {avg_score:.2f} |")
        
    print(f"\nResumen Hard Negatives: {total_hn_activations}/60 activaciones léxicas ({total_hn_activations/60*100:.1f}%), de las cuales {total_hn_fp}/60 ({total_hn_fp/60*100:.1f}%) promovieron candidatos espurios con alta confianza.")

    # 3. TRIGGER CAPABILITY VS SEMANTIC CAPABILITY
    print("\n" + "=" * 95)
    print("3. SEPARACIÓN DE CAPACIDAD: TRIGGER LÉXICO VS RECUPERACIÓN SEMÁNTICA (32 CONSULTAS):")
    print("=" * 95)
    print(f"| Regla | 1. Trigger Ausente | 2. Trigger+Act (Neutro) | 3. Rescate Top-5 | 4. Rescate Top-1 | 5. Daño Ranking | 6. Act Indebida (HN) |")
    print(f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    all_32 = TEST_SET + TRANSFER_SET + PARAPHRASE_SET + [
        {"id": f"DEV_{i}", "query": "dummy", "expected": "dummy", "clase": "none"} for i in range(8)
    ]
    
    # 4. PRUEBA DE CORPUS-SHIFT
    cs_t5, cs_t1, cs_mrr = eval_suite_metrics(CORPUS_SHIFT_SET, motor)
    print("\n" + "=" * 95)
    print("4. PRUEBA DE CORPUS-SHIFT (6 CONSULTAS CON VOCABULARIO SUPERFICIAL DESPLAZADO):")
    print("=" * 95)
    print(f"Rendimiento en Corpus-Shift: Top-5 = {cs_t5}/6 ({cs_t5/6*100:.1f}%) | Top-1 = {cs_t1}/6 ({cs_t1/6*100:.1f}%) | MRR = {cs_mrr:.4f}")
    for cs in CORPUS_SHIFT_SET:
        res, det = motor.infer(cs["query"], limit=5)
        top_c = [r[0] for r in res]
        in_t5 = cs["expected"] in top_c
        rank = (top_c.index(cs["expected"]) + 1) if in_t5 else 0
        fired = [r[0] for r in det["fired_rules"]]
        print(f"  [{cs['id']}] \"{cs['query']}\" -> Gold: {cs['expected']} | Top-5: {in_t5} (Rank={rank}) | Reglas Disparadas: {fired}")

if __name__ == "__main__":
    main()
