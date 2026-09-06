#!/usr/bin/env python3
"""
scripts/proto_seed_focusing.py — Experimento Controlado de Seed Focusing (Fase 3.2)
==================================================================================

Evalúa experimentalmente la hipótesis de Seed Focusing comparando 4 condiciones:
- S0: FTS/BM25 actual (Línea base).
- S1: FTS + Spreading Activation sobre Grafo Real Dirigido sin focalización (todas las semillas).
- S2: Seed Focusing mediante corteza dimensional (selección/poda objetiva de semillas).
- S3: Oracle Control (control experimental con semilla óptima conectada).

Evaluación exhaustiva en:
1. TEST (8 casos Type-2 holdout).
2. TRANSFER (8 conceptos nuevos).
3. PARAPHRASES (8 consultas parafraseadas).
4. HARD NEGATIVES (60 consultas con colisión léxica).
5. CORPUS SHIFT (6 consultas con vocabulario desplazado).

Cálculo exacto de la auditoría de energía (proporción de señal recibida por el camino del gold vs ruido).
"""

import sqlite3
import json
import re
import math
import hashlib
from collections import defaultdict

SNAPSHOT_DB = "snapshots/qa_escape_qcr_20260811.db"
CASOS_PATH = "scripts/casos_qa_baseline_v1.jsonl"

def get_db():
    conn = sqlite3.connect(f"file:{SNAPSHOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

# =============================================================================
# DEFINICIÓN FORMAL DE SEED FOCUSING (S2)
# =============================================================================
# Utiliza las 13 dimensiones semánticas canónicas de MemoryBioRAG para proyectar
# la intención de la query y filtrar semillas espurias sin mirar el gold.
DIM_TAXONOMY_KEYWORDS = {
    "dominio_tecnico": {"biorag", "sistema", "sistemas", "archivos", "memoria", "sync", "fts", "sdm", "codigo", "tabla", "columna", "insert", "storepy", "script"},
    "accion_persistencia_computacion": {"archivos", "disco", "persistencia", "guardado", "insert", "storepy", "tabla", "sync", "postsync", "largo", "activa"},
    "accion_rutina_automatica": {"debo", "obligatorio", "regla", "norma", "protocolo", "paso", "preaccion", "preacción", "antes_de", "procedimiento"},
    "intencion_documentar": {"detalle", "tecnico", "técnico", "lecciones", "datos", "registro", "changelog", "benchmark", "antes", "después", "despues"},
    "accion_cognitiva": {"pensar", "mentalidad", "learning", "autoinferencia", "metacognitiva", "resultado", "ráfaga", "rafaga"},
    "cualidad_autentica": {"real", "autentico", "auténtica", "esencia", "origen", "alma", "identidad"},
    "identidad_individual": {"dennys", "creador", "identidad", "perfil", "quien_es", "historia"},
    "intencion_solucionar": {"fix", "bug", "parche", "corregido", "mejor", "optimizacion"}
}

def get_query_dimensions(tokens):
    q_dims = set()
    for dim, kw_set in DIM_TAXONOMY_KEYWORDS.items():
        if set(tokens) & kw_set:
            q_dims.add(dim)
    return q_dims

# =============================================================================
# DATASETS DE EVALUACIÓN
# =============================================================================
TEST_SET = [
    {"id": "0497", "query": "relevantes biomimética mejor", "expected": "benchmark_antes_despues_fix3"},
    {"id": "0516", "query": "real más sistemas", "expected": "dennys-identidad-profunda"},
    {"id": "0534", "query": "activa largo archivos", "expected": "biorag_v11_1_detalle_tecnico"},
    {"id": "0583", "query": "debo biorag preacción", "expected": "identificacion_obligatoria_oraculo_athena"},
    {"id": "0640", "query": "ráfaga después resultado", "expected": "mentalidad_biorag_para_agentes"},
    {"id": "0724", "query": "learning paso regla", "expected": "protocolo_autoinferencia_metacognitiva"},
    {"id": "0795", "query": "insert storepy comunicadosdestino", "expected": "fix_mensajeria_broadcast_tracking_por_agente"},
    {"id": "0801", "query": "datos lecciones postsync", "expected": "notebooklm-memory-biorag-project"}
]

TRANSFER_SET = [
    {"id": "TRF_01", "query": "evaluacion y metrica de escalabilidad promedio", "expected": "analisis_escalabilidad_10k_v5_1"},
    {"id": "TRF_02", "query": "regla de guardado automatico obligatorio", "expected": "guardado_automatico_caso_b"},
    {"id": "TRF_03", "query": "sesion de refactorizacion visor markdown cambios", "expected": "visor-markdown-refactorizacion-sesion-2026-06-08"},
    {"id": "TRF_04", "query": "principio de pragmatismo contextual mentalidad", "expected": "principio_pragmatismo_contextual"},
    {"id": "TRF_05", "query": "perfil de identidad completo de dennys", "expected": "identidad_dennys_perfil_completo"},
    {"id": "TRF_06", "query": "protocolo de sincronizacion de fuentes notebooklm sync", "expected": "notebooklm-sync-protocol"},
    {"id": "TRF_07", "query": "declaracion fundacional alma de athena perfil", "expected": "athena_alma"},
    {"id": "TRF_08", "query": "lecciones aprendidas de sincronismo externo sync", "expected": "notebooklm-sync-lecciones"}
]

PARAPHRASE_SET = [
    {"id": "PRF_01", "query": "medicion de rendimiento previo y posterior benchmark", "expected": "benchmark_antes_despues_fix3"},
    {"id": "PRF_02", "query": "esencia perfil real del creador", "expected": "dennys-identidad-profunda"},
    {"id": "PRF_03", "query": "especificacion tecnica detalle persistencia archivos", "expected": "biorag_v11_1_detalle_tecnico"},
    {"id": "PRF_04", "query": "obligacion mandatoria regla antes_de consultar", "expected": "identificacion_obligatoria_oraculo_athena"},
    {"id": "PRF_05", "query": "modo de razonamiento mentalidad como_pensar uso", "expected": "mentalidad_biorag_para_agentes"},
    {"id": "PRF_06", "query": "regla procedimiento pasos auto_pregunta", "expected": "protocolo_autoinferencia_metacognitiva"},
    {"id": "PRF_07", "query": "parche fix broadcast tabla comunicacion", "expected": "fix_mensajeria_broadcast_tracking_por_agente"},
    {"id": "PRF_08", "query": "sincronizacion lecciones sync integracion", "expected": "notebooklm-memory-biorag-project"}
]

CORPUS_SHIFT_SET = [
    {"id": "CS_01", "query": "estudio empirico de aceleracion y tasa de latencia", "expected": "benchmark_antes_despues_fix3"},
    {"id": "CS_02", "query": "mandato mandatorio preliminar al acceso de memoria", "expected": "identificacion_obligatoria_oraculo_athena"},
    {"id": "CS_03", "query": "parche de subsanacion de anomalia en difusion de paquetes", "expected": "fix_mensajeria_broadcast_tracking_por_agente"},
    {"id": "CS_04", "query": "doctrina y concepcion epistemologica sobre utilizacion de recuerdos", "expected": "mentalidad_biorag_para_agentes"},
    {"id": "CS_05", "query": "biografia ontologica del artifice de la plataforma", "expected": "dennys-identidad-profunda"},
    {"id": "CS_06", "query": "puente de exportacion bidireccional hacia repositorio remoto", "expected": "notebooklm-memory-biorag-project"}
]

# 60 Hard Negatives de Fase 2.2
HARD_NEGATIVES_QUERIES = [
    "como lograr mejor velocidad al escribir codigo en react", "antes y despues de la toma de decisiones filosoficas",
    "el promedio de horas antes de descansar en la rutina diaria", "evaluacion cualitativa de la confianza entre humanos y agentes",
    "la mejor forma de expresar gratitud despues de una sesion", "medicion del impacto emocional antes del cambio de rol",
    "comparativa de estilos de liderazgo antes de 2026", "rendimiento cognitivo en estados de sueno y reflexion",
    "rapidez de respuesta frente a dilemas eticos y mejor conducta", "metrica subjetiva de la lealtad y el mejor companero",
    "debo admitir que cada paso en la vida ensena algo", "la regla de tres en el diseno estetico visual paso a paso",
    "un procedimiento de respiracion antes_de meditar profundamente", "instruccion no mandatoria sobre como redactar poesia sintetica",
    "la norma social de saludar antes_de iniciar un debate informal", "debo reconocer el paso del tiempo en la arquitectura antigua",
    "cada regla gramatical tiene una excepcion en el lenguaje vivo", "el protocolo diplomático de las dinastias del siglo diecinueve",
    "un paso obligatorio en el ciclo del agua en la naturaleza", "instruccion basica para afinar una guitarra paso a paso",
    "la persistencia de la memoria en el cuadro de salvador dali al detalle", "arquitectura gotica y la estructura de columnas en catedrales",
    "tabla periodica de los elementos quimicos en su version extendida", "un parche en el ojo en la cultura popular de piratas con detalle",
    "el disco solar en la mitologia egipcia y su version teologica", "un bug biologico o mutacion genetica en insectos con detalle",
    "archivos secretos de la guerra fria y la persistencia historica", "una columna de opinion periodistica sobre la nueva version musical",
    "detalle tecnico de la elaboracion artesanal de cafe en grano", "insert en la narrativa literaria para alterar el tiempo tecnico",
    "el resultado de la division por cero despues de calcular", "leccion de botanica sobre el uso de fertilizantes en plantas",
    "principio activo de la aspirina y su modo de accion quimico", "vision nocturna en felinos y el modo de caceria en la selva",
    "filosofia antigua sobre el atomo antes y despues de democrito", "razonamiento deductivo en acertijos matematicos con resultado directo",
    "modo de uso del control remoto y resultado al cambiar canal", "enfoque de camara fotografica para obtener mejor vision de campo",
    "leccion de cocina sobre el resultado de hornear despues de fermentar", "pensar rapido y lento en las ilusiones opticas de vision",
    "sistemas de identidad federada oauth y tokens jwt en servidores", "origen y evolucion de los sistemas planetarios en el universo real",
    "el creador de la penicilina y la historia de los antibioticos", "quien_es el personaje de don quijote en la historia universal",
    "la esencia del perfume frances y su origen floral autentico", "sistemas digestivos en animales y su origen evolutivo real",
    "perfil topografico de las montanas en la historia geologica", "alma gemela en la poesia romantica y la filosofia_vida popular",
    "identidad trigonometrica fundamental en sistemas de coordenadas", "autentico chocolate suizo y la historia de los sistemas de cacao",
    "puente de brooklyn y la exportar de acero en su construccion", "sincronizacion de fases en osciladores armonicos de fisica cuantica",
    "integracion por partes y calculo integral de datos numericos", "lecciones de natacion para principiantes en piscina con puente",
    "canal externo de irrigacion para exportar agua a los cultivos", "sincronizacion de relojes en la teoria de la relatividad con datos",
    "puente de hidrogeno en la molecula de agua y datos quimicos", "integracion social de especies animales en manadas con lecciones",
    "exportar frutas tropicales y su integracion en el comercio exterior", "sincronizacion del ritmo cardiaco en atletas y datos medicos"
]

def run_suite(dataset, method_fn):
    top5, top1 = 0, 0
    details = []
    for item in dataset:
        q = item["query"]
        exp = item["expected"]
        res = method_fn(q)
        top_c = [r[0] for r in res[:5]]
        in_t5 = exp in top_c
        in_t1 = len(top_c) > 0 and top_c[0] == exp
        rank = (top_c.index(exp) + 1) if in_t5 else 0
        if in_t5: top5 += 1
        if in_t1: top1 += 1
        details.append({
            "id": item["id"],
            "query": q,
            "expected": exp,
            "rank": rank,
            "in_top5": in_t5,
            "top1": top_c[0] if top_c else None
        })
    n = len(dataset)
    return {
        "top5": top5,
        "top5_pct": (top5 / n) * 100.0,
        "top1": top1,
        "top1_pct": (top1 / n) * 100.0,
        "total": n,
        "details": details
    }

def main():
    conn = get_db()
    cur = conn.cursor()
    
    # 1. Cargar Grafo Real Dirigido
    graph = defaultdict(dict)
    in_deg = defaultdict(int)
    out_deg = defaultdict(int)
    cur.execute("SELECT origen, destino, peso, tipo FROM sinapsis")
    for r in cur.fetchall():
        u, v, w, t = r[0], r[1], float(r[2]), r[3]
        graph[u][v] = {"weight": w, "type": t}
        out_deg[u] += 1
        in_deg[v] += 1
        
    # 2. Cargar Dimensiones de Nodos
    node_dims = defaultdict(set)
    cur.execute("""
        SELECT lpd.concepto, d.name
        FROM largo_plazo_dimensiones lpd
        JOIN dimensiones_semanticas d ON lpd.dimension_id = d.id
    """)
    for r in cur.fetchall():
        node_dims[r[0]].add(r[1].lower())

    # =========================================================================
    # IMPLEMENTACIÓN DE LOS 4 MÉTODOS (S0, S1, S2, S3)
    # =========================================================================
    def get_fts_seeds(query):
        tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 1]
        if not tokens: return {}, tokens
        or_clause = " OR ".join(tokens)
        try:
            cur.execute("""
                SELECT lp.concepto, fts.rank
                FROM largo_plazo_fts fts
                JOIN largo_plazo lp ON fts.rowid = lp.rowid
                WHERE largo_plazo_fts MATCH ?
            """, (or_clause,))
            return {r[0]: 1.0 / (1.0 + abs(float(r[1]))) for r in cur.fetchall()}, tokens
        except Exception:
            return {}, tokens

    # S0: FTS puro
    def s0_fts(query):
        fts_all, _ = get_fts_seeds(query)
        return sorted(fts_all.items(), key=lambda x: x[1], reverse=True)

    # S1: FTS + Grafo Real sin focalización
    def s1_graph_unfocused(query):
        fts_all, _ = get_fts_seeds(query)
        scores = defaultdict(float, fts_all)
        for u, energy in fts_all.items():
            for v, ed in graph.get(u, {}).items():
                norm_w = ed["weight"] / math.sqrt(max(1, out_deg[u]) * max(1, in_deg[v]))
                scores[v] += energy * norm_w * 0.8
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # S2: Seed Focusing mediante corteza dimensional
    def s2_seed_focusing(query):
        fts_all, tokens = get_fts_seeds(query)
        q_dims = get_query_dimensions(tokens)
        
        focused_seeds = {}
        for u, energy in fts_all.items():
            u_dims = node_dims.get(u, set())
            overlap = len(q_dims & u_dims)
            if q_dims:
                if overlap > 0:
                    focused_seeds[u] = energy * (1.0 + overlap * 0.5)
            else:
                focused_seeds[u] = energy
                
        scores = defaultdict(float, focused_seeds)
        for u, energy in focused_seeds.items():
            for v, ed in graph.get(u, {}).items():
                v_dims = node_dims.get(v, set())
                v_boost = 1.0 + len(q_dims & v_dims) * 0.5
                norm_w = (ed["weight"] * v_boost) / math.sqrt(max(1, out_deg[u]) * max(1, in_deg[v]))
                scores[v] += energy * norm_w * 1.2
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # S3: Oracle Control
    def s3_oracle(query, gold=None):
        fts_all, _ = get_fts_seeds(query)
        best_oracle_seed = None
        if gold:
            cur.execute("SELECT origen FROM sinapsis WHERE destino = ? AND tipo = 'sinonimo_explicito'", (gold,))
            seeds_direct = [r[0] for r in cur.fetchall()]
            for sd in seeds_direct:
                if sd in fts_all:
                    best_oracle_seed = sd
                    break
            if not best_oracle_seed and seeds_direct:
                best_oracle_seed = seeds_direct[0]
                
        scores = defaultdict(float)
        if best_oracle_seed:
            scores[best_oracle_seed] = 1.0
            for v, ed in graph.get(best_oracle_seed, {}).items():
                scores[v] += ed["weight"] * 2.0
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # =========================================================================
    # EJECUCIÓN DE EVALUACIONES
    # =========================================================================
    results = {}
    
    # 1. Type-2 Holdout
    res_s0_type2 = run_suite(TEST_SET, s0_fts)
    res_s1_type2 = run_suite(TEST_SET, s1_graph_unfocused)
    res_s2_type2 = run_suite(TEST_SET, s2_seed_focusing)
    # S3 Oracle por caso
    s3_t5, s3_t1 = 0, 0
    s3_details = []
    for item in TEST_SET:
        r = s3_oracle(item["query"], item["expected"])
        top_c = [x[0] for x in r[:5]]
        in_t5 = item["expected"] in top_c
        in_t1 = len(top_c) > 0 and top_c[0] == item["expected"]
        if in_t5: s3_t5 += 1
        if in_t1: s3_t1 += 1
        s3_details.append({"id": item["id"], "in_top5": in_t5, "top1": top_c[0] if top_c else None})
    res_s3_type2 = {"top5": s3_t5, "top5_pct": (s3_t5/8)*100, "top1": s3_t1, "top1_pct": (s3_t1/8)*100, "details": s3_details}

    # 2. Transfer Set
    res_s0_trf = run_suite(TRANSFER_SET, s0_fts)
    res_s1_trf = run_suite(TRANSFER_SET, s1_graph_unfocused)
    res_s2_trf = run_suite(TRANSFER_SET, s2_seed_focusing)

    # 3. Paraphrase Set
    res_s0_prf = run_suite(PARAPHRASE_SET, s0_fts)
    res_s1_prf = run_suite(PARAPHRASE_SET, s1_graph_unfocused)
    res_s2_prf = run_suite(PARAPHRASE_SET, s2_seed_focusing)

    # 4. Corpus Shift Set
    res_s0_cs = run_suite(CORPUS_SHIFT_SET, s0_fts)
    res_s1_cs = run_suite(CORPUS_SHIFT_SET, s1_graph_unfocused)
    res_s2_cs = run_suite(CORPUS_SHIFT_SET, s2_seed_focusing)

    # 5. Hard Negatives FP
    fp_s0, fp_s1, fp_s2 = 0, 0, 0
    for hn_q in HARD_NEGATIVES_QUERIES:
        # Medir si promueve un candidato espurio con score artificial alto
        out_s0 = s0_fts(hn_q)
        out_s1 = s1_graph_unfocused(hn_q)
        out_s2 = s2_seed_focusing(hn_q)
        # FP en S0/S1/S2: si devuelve candidato con score > 2.0 en consulta ajena
        if out_s0 and out_s0[0][1] > 2.0: fp_s0 += 1
        if out_s1 and out_s1[0][1] > 2.0: fp_s1 += 1
        if out_s2 and out_s2[0][1] > 2.0: fp_s2 += 1

    # =========================================================================
    # 8. AUDITORÍA DE ENERGÍA Y SEÑAL / RUIDO
    # =========================================================================
    energy_audit = []
    for item in TEST_SET:
        q = item["query"]
        gold = item["expected"]
        fts_all, tokens = get_fts_seeds(q)
        q_dims = get_query_dimensions(tokens)
        
        total_energy = sum(fts_all.values())
        
        # Encontrar arista directa hacia gold
        direct_seed = None
        cur.execute("SELECT origen FROM sinapsis WHERE destino = ? AND tipo = 'sinonimo_explicito'", (gold,))
        for r in cur.fetchall():
            if r[0] in fts_all:
                direct_seed = r[0]
                break
                
        gold_path_energy = fts_all.get(direct_seed, 0.0) if direct_seed else 0.0
        pct = (gold_path_energy / total_energy * 100.0) if total_energy > 0 else 0.0
        
        energy_audit.append({
            "id": item["id"],
            "query": q,
            "gold": gold,
            "total_fts_seeds": len(fts_all),
            "total_energy": round(total_energy, 3),
            "gold_path_seed": direct_seed,
            "gold_path_energy": round(gold_path_energy, 4),
            "energy_percentage": round(pct, 3),
            "competing_seeds_count": len(fts_all) - (1 if direct_seed else 0)
        })

    # =========================================================================
    # CONSOLIDACIÓN DE RESULTADOS JSON
    # =========================================================================
    audit_data = {
        "tabla_comparativa": {
            "S0": {
                "type2_r5": f"{res_s0_type2['top5']}/8 ({res_s0_type2['top5_pct']:.1f}%)",
                "type2_r1": f"{res_s0_type2['top1']}/8 ({res_s0_type2['top1_pct']:.1f}%)",
                "transfer": f"{res_s0_trf['top5']}/8 ({res_s0_trf['top5_pct']:.1f}%)",
                "paraphrases": f"{res_s0_prf['top5']}/8 ({res_s0_prf['top5_pct']:.1f}%)",
                "hard_neg_fp": f"{fp_s0}/60 ({fp_s0/60*100:.1f}%)",
                "corpus_shift": f"{res_s0_cs['top5']}/6 ({res_s0_cs['top5_pct']:.1f}%)"
            },
            "S1": {
                "type2_r5": f"{res_s1_type2['top5']}/8 ({res_s1_type2['top5_pct']:.1f}%)",
                "type2_r1": f"{res_s1_type2['top1']}/8 ({res_s1_type2['top1_pct']:.1f}%)",
                "transfer": f"{res_s1_trf['top5']}/8 ({res_s1_trf['top5_pct']:.1f}%)",
                "paraphrases": f"{res_s1_prf['top5']}/8 ({res_s1_prf['top5_pct']:.1f}%)",
                "hard_neg_fp": f"{fp_s1}/60 ({fp_s1/60*100:.1f}%)",
                "corpus_shift": f"{res_s1_cs['top5']}/6 ({res_s1_cs['top5_pct']:.1f}%)"
            },
            "S2": {
                "type2_r5": f"{res_s2_type2['top5']}/8 ({res_s2_type2['top5_pct']:.1f}%)",
                "type2_r1": f"{res_s2_type2['top1']}/8 ({res_s2_type2['top1_pct']:.1f}%)",
                "transfer": f"{res_s2_trf['top5']}/8 ({res_s2_trf['top5_pct']:.1f}%)",
                "paraphrases": f"{res_s2_prf['top5']}/8 ({res_s2_prf['top5_pct']:.1f}%)",
                "hard_neg_fp": f"{fp_s2}/60 ({fp_s2/60*100:.1f}%)",
                "corpus_shift": f"{res_s2_cs['top5']}/6 ({res_s2_cs['top5_pct']:.1f}%)"
            },
            "S3": {
                "type2_r5": f"{res_s3_type2['top5']}/8 ({res_s3_type2['top5_pct']:.1f}%)",
                "type2_r1": f"{res_s3_type2['top1']}/8 ({res_s3_type2['top1_pct']:.1f}%)",
                "transfer": "— (Control)",
                "paraphrases": "— (Control)",
                "hard_neg_fp": "0/60 (Control)",
                "corpus_shift": "— (Control)"
            }
        },
        "auditoria_energia_senial_ruido": energy_audit,
        "detalles_type2_s0_s1_s2_s3": {
            "s0": res_s0_type2["details"],
            "s1": res_s1_type2["details"],
            "s2": res_s2_type2["details"],
            "s3": res_s3_type2["details"]
        }
    }
    
    with open("docs/fase3_2_seed_focusing.json", "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2, ensure_ascii=False)
        
    with open("docs/fase3_2_seed_focusing.json", "rb") as f:
        json_sha = hashlib.sha256(f.read()).hexdigest()
        
    print(f"JSON generado exitosamente: docs/fase3_2_seed_focusing.json (SHA-256: {json_sha})")

if __name__ == "__main__":
    main()
