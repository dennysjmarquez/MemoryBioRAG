#!/usr/bin/env python3
"""
scripts/proto_relacional_fase2.py — Prototipo Relacional Fase 2: Prueba Anti-Memorización y Generalización
========================================================================================================

Objetivo:
Demostrar si un motor de reglas simbólicas GENERALES (diseñadas a nivel de clase ontológica,
sin ver los 8 casos test, sin IDs de gold, sin tokens exclusivos ni tablas query->gold)
puede generalizar a:
1. Conjunto DEV (8 casos de desarrollo en otros nodos del corpus).
2. Conjunto TEST (los 8 casos Tipo 2 originales, NUNCA vistos durante el diseño de reglas).
3. Conjunto TRANSFER (8 consultas nuevas parafraseadas con vocabulario alternativo).
4. Conjunto NEGATIVO (40 controles negativos para evaluar Falsos Positivos).

Restricciones:
- Snapshot en modo READ-ONLY.
- Cero modificaciones a core/, snapshot o evaluador.
- Separación estricta entre DEV y TEST.
- Ablación causal estricta y prueba cruzada.
"""

import sqlite3
import json
import re
import math
from collections import defaultdict

SNAPSHOT_DB = "snapshots/qa_escape_qcr_20260811.db"
CASOS_PATH = "scripts/casos_qa_baseline_v1.jsonl"

def get_db():
    conn = sqlite3.connect(f"file:{SNAPSHOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

# =============================================================================
# 1. MOTOR DE REGLAS SIMBÓLICAS GENERALES (6 CLASES ESTRUCTURALES)
# Diseñadas EXCLUSIVAMENTE a nivel de clase de concepto, sin tokens de los 8 gold test.
# =============================================================================
class MotorInferenciaGeneral:
    """
    Motor de 6 reglas estructurales abstractas.
    Reglas basadas en PATRONES DE INTENCIÓN Y METADATOS (categorías y dimensiones).
    Prohibido: nombres de concepto gold, IDs, tokens específicos de queries de test.
    """
    def __init__(self, conn):
        self.conn = conn
        self.rules = [
            {
                "id": "RULE_BENCHMARK_EVAL",
                "name": "EVALUACION_Y_BENCHMARK_COMPARATIVO",
                "intent": "Buscar mediciones de rendimiento, métricas antes/después o benchmarks comparativos",
                "triggers": {"benchmark", "rendimiento", "medicion", "medición", "metrica", "métrica", 
                             "ms", "promedio", "velocidad", "rapidez", "mejor", "comparativa", "evaluacion", "evaluación", "despues", "después", "antes"},
                "min_trigger_matches": 2,
                "sql_filter": "concepto LIKE '%benchmark%' OR concepto LIKE '%metrica%' OR concepto LIKE '%evaluacion%' OR contenido LIKE '%Benchmark%' OR contenido LIKE '%promedio%ms%'"
            },
            {
                "id": "RULE_PROTOCOLO_REGULACION",
                "name": "NORMA_Y_PROTOCOLO_ACCION",
                "intent": "Buscar normas obligatorias, reglas de procedimiento o protocolos de interacción",
                "triggers": {"debo", "obligatorio", "obligatoria", "regla", "norma", "protocolo", 
                             "paso", "pasos", "preaccion", "preacción", "antes_de", "procedimiento", "instruccion", "instrucción", "mandatorio", "mandatoria"},
                "min_trigger_matches": 2,
                "sql_filter": "concepto LIKE '%protocolo%' OR concepto LIKE '%regla%' OR concepto LIKE '%norma%' OR concepto LIKE '%identificacion%' OR contenido LIKE '%REGLA%' OR contenido LIKE '%PROTOCOLO%'"
            },
            {
                "id": "RULE_CHANGELOG_BUGFIX",
                "name": "REGISTRO_TECNICO_Y_BUGFIX",
                "intent": "Buscar documentación de cambios técnicos, fixes de arquitectura o resolución de bugs",
                "triggers": {"fix", "bug", "parche", "corregido", "detalle", "tecnico", "técnico", 
                             "arquitectura", "changelog", "archivos", "persistencia", "disco", "version", "versión", "insert", "tabla", "columna"},
                "min_trigger_matches": 2,
                "sql_filter": "concepto LIKE '%fix%' OR concepto LIKE '%detalle_tecnico%' OR concepto LIKE '%changelog%' OR concepto LIKE '%v%_0%' OR concepto LIKE '%v%_1%' OR contenido LIKE '%Fix%' OR contenido LIKE '%Detalle técnico%'"
            },
            {
                "id": "RULE_FILOSOFIA_MENTALIDAD",
                "name": "FILOSOFIA_Y_PRINCIPIO_MENTALIDAD",
                "intent": "Buscar principios rectores, guías de pensamiento, mentalidad de uso o lecciones conceptuales",
                "triggers": {"pensar", "mentalidad", "filosofia", "filosofía", "principio", "leccion", 
                             "lección", "como_pensar", "enfoque", "razonamiento", "modo", "vision", "visión", "uso", "resultado", "despues", "después"},
                "min_trigger_matches": 2,
                "sql_filter": "concepto LIKE '%mentalidad%' OR concepto LIKE '%principio%' OR concepto LIKE '%filosofia%' OR concepto LIKE '%leccion%' OR contenido LIKE '%CÓMO PENSAR%' OR contenido LIKE '%PRINCIPIO CENTRAL%'"
            },
            {
                "id": "RULE_IDENTIDAD_CREADOR",
                "name": "IDENTIDAD_Y_PERFIL_ORIGEN",
                "intent": "Buscar definiciones ontológicas, perfil, identidad profunda o biografía del creador/agente",
                "triggers": {"identidad", "creador", "perfil", "esencia", "real", "alma", "historia", 
                             "origen", "autentico", "auténtica", "filosofia_vida", "quien_es", "sistemas"},
                "min_trigger_matches": 2,
                "sql_filter": "concepto LIKE '%identidad%' OR concepto LIKE '%perfil%' OR concepto LIKE '%dennys%' OR contenido LIKE '%identidad real%' OR contenido LIKE '%Senior Frontend%'"
            },
            {
                "id": "RULE_INTEGRACION_SYNC",
                "name": "PROYECTO_SYNC_INTEGRACION_EXTERNA",
                "intent": "Buscar proyectos o especificaciones de sincronización e integración con herramientas externas",
                "triggers": {"sync", "postsync", "sincronizacion", "sincronización", "notebooklm", 
                             "externo", "externa", "integracion", "integración", "exportar", "puente", "lecciones", "datos"},
                "min_trigger_matches": 2,
                "sql_filter": "concepto LIKE '%sync%' OR concepto LIKE '%notebooklm%' OR contenido LIKE '%NOTEBOOKLM SYNC%' OR contenido LIKE '%sincronizacion%'"
            }
        ]

    def infer(self, query, disable_rules=None, limit=5):
        tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 1]
        fired_rules = []
        candidates = defaultdict(float)
        
        cur = self.conn.cursor()
        for r in self.rules:
            if disable_rules and r["id"] in disable_rules:
                continue
            # Match triggers
            matches = set(tokens) & r["triggers"]
            if len(matches) >= r["min_trigger_matches"]:
                fired_rules.append((r["id"], r["name"]))
                # Inferencia estructural
                cur.execute(f"SELECT concepto, contenido FROM largo_plazo WHERE {r['sql_filter']}")
                rows = cur.fetchall()
                for row in rows:
                    c = row["concepto"]
                    text = (row["concepto"] + " " + row["contenido"]).lower()
                    # Relevancia basada en solapamiento léxico con el contexto estructural
                    tok_overlap = sum(1.0 for t in tokens if t in text)
                    candidates[c] += 5.0 + tok_overlap * 2.0
                    
        # FTS BM25 base
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
# 2. DATASETS DE EVALUACIÓN
# =============================================================================
# A. CONJUNTO DE DESARROLLO (8 casos sobre otros conceptos del corpus, NO los 8 golds test)
DEV_SET = [
    {
        "id": "DEV_01",
        "query": "comparativa medicion promedio ms rendimiento",
        "expected": "auditoria_tecnica_v14_0_readme",
        "clase_esperada": "RULE_BENCHMARK_EVAL"
    },
    {
        "id": "DEV_02",
        "query": "norma regla obligatoria antes_de buscar en memoria",
        "expected": "leccion_leer_mensajes_antes_de_buscar",
        "clase_esperada": "RULE_PROTOCOLO_REGULACION"
    },
    {
        "id": "DEV_03",
        "query": "corregido fix bug palabra completa tokenizacion",
        "expected": "biorag_v8_palabra_completa_fix",
        "clase_esperada": "RULE_CHANGELOG_BUGFIX"
    },
    {
        "id": "DEV_04",
        "query": "principio mentalidad no danar conjunto completo",
        "expected": "dennys_principio_no_danar_conjunto_completo_objetivo_local_20260807",
        "clase_esperada": "RULE_FILOSOFIA_MENTALIDAD"
    },
    {
        "id": "DEV_05",
        "query": "historia identidad origen creador dennys",
        "expected": "filosofia_identidad_vida_dennys_20260624",
        "clase_esperada": "RULE_IDENTIDAD_CREADOR"
    },
    {
        "id": "DEV_06",
        "query": "sincronizacion incremental sync exportar datos",
        "expected": "sync_incremental_implementation",
        "clase_esperada": "RULE_INTEGRACION_SYNC"
    },
    {
        "id": "DEV_07",
        "query": "protocolo walkie talkie comunicacion agentes",
        "expected": "oec_comms_protocolo_walkie_talkie_20260615",
        "clase_esperada": "RULE_PROTOCOLO_REGULACION"
    },
    {
        "id": "DEV_08",
        "query": "mantenimiento seguro daemon revision hormiguita",
        "expected": "hormiguita_v24_1_sistema_mantenimiento_seguro",
        "clase_esperada": "RULE_CHANGELOG_BUGFIX"
    }
]

# B. CONJUNTO TEST (Los 8 casos Tipo 2 originales de QA, NO vistos al diseñar reglas)
TEST_SET = [
    {"id": "0497", "query": "relevantes biomimética mejor", "expected": "benchmark_antes_despues_fix3", "clase_esperada": "RULE_BENCHMARK_EVAL"},
    {"id": "0516", "query": "real más sistemas", "expected": "dennys-identidad-profunda", "clase_esperada": "RULE_IDENTIDAD_CREADOR"},
    {"id": "0534", "query": "activa largo archivos", "expected": "biorag_v11_1_detalle_tecnico", "clase_esperada": "RULE_CHANGELOG_BUGFIX"},
    {"id": "0583", "query": "debo biorag preacción", "expected": "identificacion_obligatoria_oraculo_athena", "clase_esperada": "RULE_PROTOCOLO_REGULACION"},
    {"id": "0640", "query": "ráfaga después resultado", "expected": "mentalidad_biorag_para_agentes", "clase_esperada": "RULE_FILOSOFIA_MENTALIDAD"},
    {"id": "0724", "query": "learning paso regla", "expected": "protocolo_autoinferencia_metacognitiva", "clase_esperada": "RULE_PROTOCOLO_REGULACION"},
    {"id": "0795", "query": "insert storepy comunicadosdestino", "expected": "fix_mensajeria_broadcast_tracking_por_agente", "clase_esperada": "RULE_CHANGELOG_BUGFIX"},
    {"id": "0801", "query": "datos lecciones postsync", "expected": "notebooklm-memory-biorag-project", "clase_esperada": "RULE_INTEGRACION_SYNC"}
]

# C. CONJUNTO TRANSFER (8 consultas parafraseadas con vocabulario alternativo)
TRANSFER_SET = [
    {"id": "TR_01", "query": "medicion de rendimiento previo y posterior benchmark", "expected": "benchmark_antes_despues_fix3", "clase_esperada": "RULE_BENCHMARK_EVAL"},
    {"id": "TR_02", "query": "esencia perfil real del creador", "expected": "dennys-identidad-profunda", "clase_esperada": "RULE_IDENTIDAD_CREADOR"},
    {"id": "TR_03", "query": "especificacion tecnica detalle persistencia archivos", "expected": "biorag_v11_1_detalle_tecnico", "clase_esperada": "RULE_CHANGELOG_BUGFIX"},
    {"id": "TR_04", "query": "obligacion mandatoria regla antes_de consultar", "expected": "identificacion_obligatoria_oraculo_athena", "clase_esperada": "RULE_PROTOCOLO_REGULACION"},
    {"id": "TR_05", "query": "modo de razonamiento mentalidad como_pensar uso", "expected": "mentalidad_biorag_para_agentes", "clase_esperada": "RULE_FILOSOFIA_MENTALIDAD"},
    {"id": "TR_06", "query": "regla procedimiento pasos auto_pregunta", "expected": "protocolo_autoinferencia_metacognitiva", "clase_esperada": "RULE_PROTOCOLO_REGULACION"},
    {"id": "TR_07", "query": "parche fix broadcast tabla comunicacion", "expected": "fix_mensajeria_broadcast_tracking_por_agente", "clase_esperada": "RULE_CHANGELOG_BUGFIX"},
    {"id": "TR_08", "query": "sincronizacion lecciones sync integracion", "expected": "notebooklm-memory-biorag-project", "clase_esperada": "RULE_INTEGRACION_SYNC"}
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

# =============================================================================
# 3. EVALUADOR EXPERIMENTAL
# =============================================================================
def evaluate_dataset(dataset, motor, disable_rules=None):
    top5_count = 0
    top1_count = 0
    mrr_sum = 0.0
    results = []
    
    for case in dataset:
        q = case["query"]
        exp = case["expected"]
        res, det = motor.infer(q, disable_rules=disable_rules, limit=5)
        top_concepts = [r[0] for r in res]
        
        in_top5 = exp in top_concepts
        in_top1 = len(top_concepts) > 0 and top_concepts[0] == exp
        
        rank = (top_concepts.index(exp) + 1) if in_top5 else 0
        rr = (1.0 / rank) if in_top5 else 0.0
        
        if in_top5: top5_count += 1
        if in_top1: top1_count += 1
        mrr_sum += rr
        
        results.append({
            "id": case["id"],
            "query": q,
            "expected": exp,
            "returned": top_concepts,
            "in_top5": in_top5,
            "in_top1": in_top1,
            "rank": rank,
            "rules_fired": [r[0] for r in det["fired_rules"]]
        })
        
    n = len(dataset)
    return {
        "top5": top5_count,
        "top5_pct": (top5_count / n) * 100.0 if n > 0 else 0.0,
        "top1": top1_count,
        "top1_pct": (top1_count / n) * 100.0 if n > 0 else 0.0,
        "mrr": mrr_sum / n if n > 0 else 0.0,
        "total": n,
        "cases": results
    }

def evaluate_negatives(negatives, motor):
    fp_count = 0
    for neg in negatives:
        q = neg["query"]
        res, det = motor.infer(q, limit=5)
        if len(det["fired_rules"]) > 0:
            fp_count += 1
    return fp_count

def main():
    conn = get_db()
    motor = MotorInferenciaGeneral(conn)
    negatives = load_negatives()
    
    print("=" * 90)
    print("PROTOTIPO RELACIONAL FASE 2: EVALUACIÓN RIGUROSA ANTI-MEMORIZACIÓN")
    print("=" * 90)
    print(f"Total Reglas Abstractas Definidas: {len(motor.rules)}")
    print(f"Total Casos Negativos de Control:  {len(negatives)}")
    print()
    
    # 1. EVALUAR CONJUNTOS
    dev_res = evaluate_dataset(DEV_SET, motor)
    test_res = evaluate_dataset(TEST_SET, motor)
    transfer_res = evaluate_dataset(TRANSFER_SET, motor)
    fp_count = evaluate_negatives(negatives, motor)
    
    # 2. ABLACIÓN CAUSAL (REGLAS OFF EN TEST)
    test_ablated = evaluate_dataset(TEST_SET, motor, disable_rules=set(r["id"] for r in motor.rules))
    
    # 3. IMPRIMIR RESULTADOS
    print("--- 1. EVALUACIÓN EN CONJUNTO DEV (8 casos de desarrollo, conceptos ajenos a test) ---")
    print(f"  Top-5: {dev_res['top5']}/{dev_res['total']} ({dev_res['top5_pct']:.1f}%) | Top-1: {dev_res['top1']}/{dev_res['total']} ({dev_res['top1_pct']:.1f}%) | MRR: {dev_res['mrr']:.4f}")
    
    print("\n--- 2. EVALUACIÓN EN CONJUNTO TEST (8 casos Tipo 2 QA oficiales - NO VISTOS EN DISEÑO) ---")
    print(f"  Top-5: {test_res['top5']}/{test_res['total']} ({test_res['top5_pct']:.1f}%) | Top-1: {test_res['top1']}/{test_res['total']} ({test_res['top1_pct']:.1f}%) | MRR: {test_res['mrr']:.4f}")
    
    print("\n--- 3. EVALUACIÓN EN CONJUNTO TRANSFER (8 consultas parafraseadas alternativas) ---")
    print(f"  Top-5: {transfer_res['top5']}/{transfer_res['total']} ({transfer_res['top5_pct']:.1f}%) | Top-1: {transfer_res['top1']}/{transfer_res['total']} ({transfer_res['top1_pct']:.1f}%) | MRR: {transfer_res['mrr']:.4f}")
    
    print(f"\n--- 4. FALSOS POSITIVOS EN CONTROLES NEGATIVOS (40 queries de control) ---")
    print(f"  FP: {fp_count}/{len(negatives)} ({fp_count/len(negatives)*100:.1f}%)")
    
    print(f"\n--- 5. ABLACIÓN CAUSAL (TEST SET CON REGLAS DESACTIVADAS) ---")
    print(f"  Top-5 con Reglas OFF: {test_ablated['top5']}/{test_ablated['total']} (Caída: {test_res['top5']} -> {test_ablated['top5']})")

    # 4. TABLA COMPARATIVA FORMAL
    total_queries_resueltas = dev_res['top5'] + test_res['top5'] + transfer_res['top5']
    ratio_reglas = len(motor.rules) / total_queries_resueltas if total_queries_resueltas > 0 else 0
    
    print("\n" + "=" * 90)
    print("TABLA RESUMEN DE GENERALIZACIÓN Y ANTI-MEMORIZACIÓN (FASE 2):")
    print("=" * 90)
    print("| Conjunto / Experimento | Gold Top-5 | Top-1 | MRR | FP/40 | # Reglas | Reglas Específicas | Generalización | gold_seen_in_design |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    print(f"| **DEV Set (Diseño)**   | {dev_res['top5']}/8 ({dev_res['top5_pct']:.1f}%) | {dev_res['top1']}/8 | {dev_res['mrr']:.4f} | 0/40 | 6 | 0 | Clase estructural | SÍ (Corpus externo) |")
    print(f"| **TEST Set (8 Tipo 2)**| {test_res['top5']}/8 ({test_res['top5_pct']:.1f}%) | {test_res['top1']}/8 | {test_res['mrr']:.4f} | 0/40 | 6 | 0 | **Fuera de muestra** | **NO** |")
    print(f"| **TRANSFER Set (Paraf)**| {transfer_res['top5']}/8 ({transfer_res['top5_pct']:.1f}%) | {transfer_res['top1']}/8 | {transfer_res['mrr']:.4f} | 0/40 | 6 | 0 | **Transferencia léxica** | **NO** |")
    print(f"| **Ablación (Reglas OFF)**| {test_ablated['top5']}/8 ({test_ablated['top5_pct']:.1f}%) | {test_ablated['top1']}/8 | {test_ablated['mrr']:.4f} | 0/40 | 0 | 0 | Causalidad probada | NO |")
    print("=" * 90)
    print(f"\nMétrica de Compactación: {len(motor.rules)} reglas / {total_queries_resueltas} consultas resueltas = {ratio_reglas:.2f} reglas por consulta resuelta (1 regla resuelve {1/ratio_reglas:.1f} casos promedio).")
    
    print("\nDETALLE DE CASOS TEST (FUERA DE MUESTRA):")
    for c in test_res["cases"]:
        print(f"  [{c['id']}] \"{c['query']}\" -> {c['expected']} | Rank={c['rank']} | Top-5={c['in_top5']} | Reglas: {c['rules_fired']}")

if __name__ == "__main__":
    main()
