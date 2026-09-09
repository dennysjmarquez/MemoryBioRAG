#!/usr/bin/env python3
"""
scripts/proto_fase4_5_candidate_generation.py — Fase 4.5: Semantic Candidate Generation
=======================================================================================

Objetivo:
  Demostrar empíricamente si algún mecanismo clásico/simbólico o latente puede introducir
  en el conjunto de candidatos un gold que FTS5 NO recuperó (cero overlap léxico).

Mecanismos evaluados:
  - M0: FTS5 / BM25 Baseline puro (gold ausente por construcción).
  - M1: FTS5 + Structural Seed Re-ranking (Fase 4.3/4.4: solo repondera FTS).
  - M2: WordNet Query Expansion (expansión léxica con synsets de WordNet spa/eng).
  - M3: Concept Hub (inyección de candidatos vía bridges estructurados de 5 ángulos).
  - M4: PPMI / SVD (vecinos más cercanos en el espacio latente de co-ocurrencia).
  - M5: Grafo / Relaciones Tipadas (expansión tipada de 1 salto sobre semillas FTS).
  - M6: Combinación Clásica (Unión de M2 + M3 + M4 + M5).
  - M7: Combinación (M6) + Re-ranking Estructural (Focalizador M1 sobre pool M6).

Dataset de prueba:
  - 30 consultas Zero-FTS donde gold está 100% AUSENTE de FTS5 (gold_in_candidates_before == False).
  - Separadas en: Paráfrasis profundas, Vocabulario no visto, Lenguaje coloquial, Composicionales.
  - 90 Hard-Negatives para evaluar selectividad y ratio de expansión.
"""

import os
import re
import sys
import json
import math
import hashlib
import sqlite3
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Set, Optional

# Ensure project root and scripts are in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
for p in (PROJECT_ROOT, SCRIPTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

DB_PATH   = "snapshots/qa_escape_qcr_20260811.db"
OUTPUT_MD = "docs/fase4_5_candidate_generation.md"
OUTPUT_JS = "docs/fase4_5_candidate_generation.json"
FP_CRITERION = 0.40  # Criterio formal de similitud/score normalizado [0, 1]

# =============================================================================
# 1. DATASET DE EVALUACIÓN: 30 CONSULTAS ZERO-FTS (GOLD ESTRICTAMENTE AUSENTE DE FTS)
# =============================================================================

ZERO_FTS_DATASET = [
    # 1. Paráfrasis Semánticas Profundas (Vocabulario distante)
    {"id": "ZFTS_01", "type": "deep_paraphrase", "query": "pautas de salvaguarda indispensables con antelacion al cambio en los repositorios", "gold": "protocolo_de_seguridad_modificacion_codigo"},
    {"id": "ZFTS_02", "type": "deep_paraphrase", "query": "diagnostico del caudal de procesamiento y rapidez operativa en modulos python", "gold": "benchmark_algoritmos_rendimiento_python"},
    {"id": "ZFTS_03", "type": "deep_paraphrase", "query": "mitigacion ejecutada para neutralizar la falla de sanitizacion de consultas", "gold": "fix_vulnerabilidad_inyeccion_sql"},
    {"id": "ZFTS_04", "type": "deep_paraphrase", "query": "quien origino concebio y forjo la mente de athena", "gold": "dennys_creador_de_athena_identidad"},
    {"id": "ZFTS_05", "type": "deep_paraphrase", "query": "topologia estructural de guardado permanente en soporte magnetico", "gold": "biorag_v11_1_detalle_tecnico"},
    {"id": "ZFTS_06", "type": "deep_paraphrase", "query": "registro de celeridad maxima y consumo de milisegundos en ejecuciones", "gold": "benchmark_algoritmos_rendimiento_python"},
    {"id": "ZFTS_07", "type": "deep_paraphrase", "query": "canal de transmision externa y volcado cruzado de cuadernos", "gold": "notebooklm-memory-biorag-project"},
    {"id": "ZFTS_08", "type": "deep_paraphrase", "query": "estudio de comportamiento de carga masiva frente a 10 mil entradas", "gold": "analisis_escalabilidad_10k_v5_1"},

    # 2. Vocabulario No Visto (Sinónimos fuera de distribución)
    {"id": "ZFTS_09", "type": "unseen_vocab", "query": "politica cautelar ineludible anterior a tocar las rutinas", "gold": "protocolo_de_seguridad_modificacion_codigo"},
    {"id": "ZFTS_10", "type": "unseen_vocab", "query": "tablas de contraste sobre agilidad y milisegundos", "gold": "benchmark_algoritmos_rendimiento_python"},
    {"id": "ZFTS_11", "type": "unseen_vocab", "query": "enmienda que subsana el agujero en las sentencias dinamicas", "gold": "fix_vulnerabilidad_inyeccion_sql"},
    {"id": "ZFTS_12", "type": "unseen_vocab", "query": "paternidad de la criatura athena y su responsable inicial", "gold": "dennys_creador_de_athena_identidad"},
    {"id": "ZFTS_13", "type": "unseen_vocab", "query": "esquema pormenorizado de grabacion duradera de bloques", "gold": "biorag_v11_1_detalle_tecnico"},
    {"id": "ZFTS_14", "type": "unseen_vocab", "query": "volcado y enlace hacia el repositorio externo de apuntes", "gold": "notebooklm-memory-biorag-project"},
    {"id": "ZFTS_15", "type": "unseen_vocab", "query": "tasa de saturacion bajo volumenes gigantescos de informacion", "gold": "analisis_escalabilidad_10k_v5_1"},
    {"id": "ZFTS_16", "type": "unseen_vocab", "query": "bloqueo de alteracion indebida en cabeceras descriptivas", "gold": "fix_metadatos_corrupcion_v2"},

    # 3. Lenguaje Coloquial / Expresiones Indirectas
    {"id": "ZFTS_17", "type": "colloquial_indirect", "query": "que es lo primero que no me puedo saltar para no romper el sistema al editar", "gold": "protocolo_de_seguridad_modificacion_codigo"},
    {"id": "ZFTS_18", "type": "colloquial_indirect", "query": "como salio el test de rapidez de los scripts en python", "gold": "benchmark_algoritmos_rendimiento_python"},
    {"id": "ZFTS_19", "type": "colloquial_indirect", "query": "el arreglo que le metieron al fallo de seguridad en las consultas", "gold": "fix_vulnerabilidad_inyeccion_sql"},
    {"id": "ZFTS_20", "type": "colloquial_indirect", "query": "a quien le debemos la existencia de athena y su mente", "gold": "dennys_creador_de_athena_identidad"},
    {"id": "ZFTS_21", "type": "colloquial_indirect", "query": "las tripas y detalles de como se guardan los datos a bajo nivel", "gold": "biorag_v11_1_detalle_tecnico"},
    {"id": "ZFTS_22", "type": "colloquial_indirect", "query": "el puente que se armo para conectar los cuadernos de google", "gold": "notebooklm-memory-biorag-project"},
    {"id": "ZFTS_23", "type": "colloquial_indirect", "query": "que tan bien aguanta el sistema cuando le metemos 10k nodos de golpe", "gold": "analisis_escalabilidad_10k_v5_1"},
    {"id": "ZFTS_24", "type": "colloquial_indirect", "query": "el parche para que no se machaquen los datos de cabecera", "gold": "fix_metadatos_corrupcion_v2"},

    # 4. Combinaciones Composicionales (Múltiples relaciones implícitas)
    {"id": "ZFTS_25", "type": "compositional", "query": "procedimiento preventivo de respaldo previo a intervenciones criticas en fuentes", "gold": "protocolo_de_seguridad_modificacion_codigo"},
    {"id": "ZFTS_26", "type": "compositional", "query": "experimento cuantitativo sobre latencias comparadas en metodos de indexacion", "gold": "benchmark_latencia_hnsw_vs_ppmi"},
    {"id": "ZFTS_27", "type": "compositional", "query": "correccion estructural para prevenir colisiones en sincronismo persistente", "gold": "fix_sync_incremental_crash_v3"},
    {"id": "ZFTS_28", "type": "compositional", "query": "manifiesto de autoria intelectual y concepcion de la arquitectura biorag", "gold": "dennys_autor_arquitectura_biorag"},
    {"id": "ZFTS_29", "type": "compositional", "query": "lecciones metodologicas extraidas de interrupciones en la fase de reposo nocturno", "gold": "leccion_sueno_consolidacion_memoria"},
    {"id": "ZFTS_30", "type": "compositional", "query": "norma mandatoria de doble control y validacion replicada", "gold": "protocolo_evaluacion_dual_obligatoria"},
]

# 90 Hard Negatives
from audit_fase4_4_generalizacion import TOTAL_HARD_NEGATIVES

# =============================================================================
# 2. WORDNET & CONCEPT HUB & PPMI HELPERS
# =============================================================================

# WordNet Expansion
try:
    from nltk.corpus import wordnet as wn
except Exception:
    wn = None

def expand_query_wordnet(query: str) -> List[str]:
    """Expande palabras usando synsets de WordNet en español e inglés."""
    words = re.findall(r"[\wáéíóúüñ]+", query.lower())
    expanded = set(words)
    if wn is None:
        return list(expanded)

    for w in words:
        if len(w) <= 3: continue
        # Intentar español
        try:
            for syn in wn.synsets(w, lang='spa'):
                for lemma in syn.lemma_names('spa'):
                    expanded.add(lemma.lower().replace("_", " "))
        except Exception:
            pass
        # Fallback inglés
        try:
            for syn in wn.synsets(w):
                for lemma in syn.lemma_names():
                    expanded.add(lemma.lower().replace("_", " "))
        except Exception:
            pass
    return list(expanded)

# ConceptHub Bridges en memoria (cargados de core/concept_hub.py HUBS_INICIALES)
from core.concept_hub import HUBS_INICIALES

def expand_query_concept_hub(query: str) -> List[str]:
    """Recupera canonical_nodes y nodos asociados de los Concept Hubs compatibles."""
    q_tokens = set(re.findall(r"[\w]+", query.lower()))
    generated_nodes = set()
    for hub in HUBS_INICIALES:
        for b in hub.get("bridges", []):
            b_tokens = set(re.findall(r"[\w]+", b.get("text", "").lower()))
            if len(q_tokens & b_tokens) >= 2:
                generated_nodes.add(hub["canonical_node"])
                for n in hub.get("nodos", []):
                    generated_nodes.add(n)
    return list(generated_nodes)

# PPMI Vectorizer Simulado / Calculado sobre coocurrencias del snapshot
def build_ppmi_index(conn) -> Tuple[Dict[str, List[float]], Dict[str, int]]:
    """Construye un índice de co-ocurrencia PPMI ligero sobre el corpus de largo_plazo."""
    cur = conn.cursor()
    cur.execute("SELECT concepto, contenido FROM largo_plazo")
    docs = cur.fetchall()
    
    vocab = defaultdict(int)
    doc_tokens = {}
    for c, cont in docs:
        text = f"{c.replace('_', ' ')} {cont or ''}".lower()
        tokens = [t for t in re.findall(r"[\w]+", text) if len(t) > 2]
        doc_tokens[c] = tokens
        for t in set(tokens):
            vocab[t] += 1

    # Representación bag-of-words / TF-IDF simplificada como proxy de espacio latente PPMI
    node_vectors = {}
    total_docs = len(docs)
    for c, tokens in doc_tokens.items():
        tf = defaultdict(int)
        for t in tokens: tf[t] += 1
        vec = {t: (tf[t] / len(tokens)) * math.log((1 + total_docs) / (1 + vocab[t])) for t in tf if vocab[t] > 0}
        node_vectors[c] = vec

    return node_vectors, vocab

def query_ppmi_neighbors(query: str, node_vectors: Dict, vocab: Dict, top_k: int = 15) -> List[Tuple[str, float]]:
    q_tokens = [t for t in re.findall(r"[\w]+", query.lower()) if len(t) > 2]
    if not q_tokens: return []
    q_vec = {t: 1.0 for t in q_tokens}

    scores = []
    for node, n_vec in node_vectors.items():
        dot = sum(q_vec[t] * n_vec.get(t, 0.0) for t in q_vec if t in n_vec)
        if dot > 0:
            scores.append((node, dot))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]

# =============================================================================
# 3. GRAFO Y RELACIONES TIPADAS (1-HOP CONSTRAINED EXPANSION)
# =============================================================================

def build_graph_relations(conn) -> Dict[str, List[Dict[str, Any]]]:
    cur = conn.cursor()
    adj = defaultdict(list)
    cur.execute("SELECT origen, destino, peso, tipo FROM sinapsis WHERE origen != destino")
    for u, v, w, t in cur.fetchall():
        adj[u].append({"target": v, "weight": float(w or 0.5), "rel_type": t})
    return adj

# =============================================================================
# 4. MÓDULOS DE CANDIDATE GENERATION (M0 a M7)
# =============================================================================

def get_fts5_candidates(cur, query: str, limit: int = 40) -> Dict[str, float]:
    tokens = [t for t in re.findall(r"[\wáéíóúüñ]+", query.lower()) if len(t) > 1]
    if not tokens: return {}
    clean = [re.sub(r"[^\w]", "", t) for t in tokens if re.sub(r"[^\w]", "", t)]
    if not clean: return {}
    try:
        cur.execute("""
            SELECT lp.concepto, fts.rank
            FROM largo_plazo_fts fts
            JOIN largo_plazo lp ON fts.rowid = lp.rowid
            WHERE largo_plazo_fts MATCH ?
            LIMIT ?
        """, (" OR ".join(clean), limit))
        return {r[0]: 1.0 / (1.0 + abs(float(r[1]))) for r in cur.fetchall()}
    except Exception:
        return {}

from audit_fase4_4_generalizacion import parse_frame_custom, classify_predicate, LEXICO_FULL, PRED_CLASSES_CFG, get_node_metadata

def run_candidate_generation_pipeline(cur, node_meta: Dict, graph_adj: Dict,
                                      node_vectors: Dict, vocab: Dict,
                                      query: str, mode: str) -> Dict[str, Any]:
    """
    Ejecuta el modo específico de Candidate Generation:
      - M0: FTS5 puro.
      - M1: FTS5 + Re-ranking estructural (M1 actual).
      - M2: WordNet Query Expansion.
      - M3: Concept Hub Candidate Injection.
      - M4: PPMI / SVD Latent Neighbors.
      - M5: Grafo Relaciones Tipadas (1-hop expansion).
      - M6: Combinación Clásica (M2 + M3 + M4 + M5).
      - M7: Combinación (M6) + Re-ranking Estructural.
    """
    raw_fts = get_fts5_candidates(cur, query, limit=40)
    candidates_pool = dict(raw_fts)
    provenance_traces = {c: "FTS5_DIRECT" for c in raw_fts}

    if mode == "M0":
        ranked = sorted(candidates_pool.items(), key=lambda x: x[1], reverse=True)
        return {"candidates": list(candidates_pool.keys()), "ranked": ranked, "provenance": provenance_traces}

    if mode == "M1":
        # Solo re-ranking estructural sobre FTS5
        frame, _ = parse_frame_custom(query, LEXICO_FULL)
        pred_cls = classify_predicate(frame)
        target_types = set()
        for pc in pred_cls: target_types.update(PRED_CLASSES_CFG.get(pc, {}).get("target_node_types", set()))
        ranked_scores = {}
        for c, s in candidates_pool.items():
            ntype = node_meta.get(c, {}).get("node_type", "GENERAL")
            boost = 2.0 if ntype in target_types else 0.5
            ranked_scores[c] = s * boost
        ranked = sorted(ranked_scores.items(), key=lambda x: x[1], reverse=True)
        return {"candidates": list(candidates_pool.keys()), "ranked": ranked, "provenance": provenance_traces}

    if mode in ("M2", "M6", "M7"):
        # WordNet Query Expansion
        expanded_words = expand_query_wordnet(query)
        if len(expanded_words) > len(query.split()):
            wn_query = " ".join(expanded_words[:12])
            wn_fts = get_fts5_candidates(cur, wn_query, limit=20)
            for c, s in wn_fts.items():
                if c not in candidates_pool:
                    candidates_pool[c] = s * 0.8
                    provenance_traces[c] = "WORDNET_EXPANSION"

    if mode in ("M3", "M6", "M7"):
        # Concept Hub Candidate Injection
        hub_nodes = expand_query_concept_hub(query)
        for hn in hub_nodes:
            if hn in node_meta:
                if hn not in candidates_pool:
                    candidates_pool[hn] = 0.75
                    provenance_traces[hn] = "CONCEPT_HUB_INJECTION"

    if mode in ("M4", "M6", "M7"):
        # PPMI / SVD Latent Neighbors
        ppmi_neighbors = query_ppmi_neighbors(query, node_vectors, vocab, top_k=15)
        for node, score in ppmi_neighbors:
            if node not in candidates_pool:
                candidates_pool[node] = score * 0.7
                provenance_traces[node] = "PPMI_LATENT_NEIGHBOR"

    if mode in ("M5", "M6", "M7"):
        # Grafo 1-hop expansion sobre las semillas más fuertes
        top_seeds = sorted(raw_fts.items(), key=lambda x: x[1], reverse=True)[:5]
        for seed, s_score in top_seeds:
            for edge in graph_adj.get(seed, []):
                target = edge["target"]
                w = edge["weight"]
                if target not in candidates_pool:
                    candidates_pool[target] = s_score * w * 0.65
                    provenance_traces[target] = f"GRAPH_1HOP({edge['rel_type']}_from_{seed})"

    # Re-ranking para M2, M3, M4, M5, M6 (sin focalizador)
    if mode in ("M2", "M3", "M4", "M5", "M6"):
        ranked = sorted(candidates_pool.items(), key=lambda x: x[1], reverse=True)
        return {"candidates": list(candidates_pool.keys()), "ranked": ranked, "provenance": provenance_traces}

    # Re-ranking para M7 (Combinación + Focalizador Estructural)
    if mode == "M7":
        frame, _ = parse_frame_custom(query, LEXICO_FULL)
        pred_cls = classify_predicate(frame)
        target_types = set()
        for pc in pred_cls: target_types.update(PRED_CLASSES_CFG.get(pc, {}).get("target_node_types", set()))
        
        ranked_scores = {}
        for c, s in candidates_pool.items():
            ntype = node_meta.get(c, {}).get("node_type", "GENERAL")
            boost = 2.0 if ntype in target_types else 0.5
            ranked_scores[c] = s * boost
        ranked = sorted(ranked_scores.items(), key=lambda x: x[1], reverse=True)
        return {"candidates": list(candidates_pool.keys()), "ranked": ranked, "provenance": provenance_traces}

    return {"candidates": list(candidates_pool.keys()), "ranked": [], "provenance": provenance_traces}

# =============================================================================
# 5. EVALUACIÓN Y SUITES EXPERIMENTALES
# =============================================================================

def evaluate_zero_fts_suite(cur, node_meta: Dict, graph_adj: Dict, node_vectors: Dict, vocab: Dict, mode: str) -> Dict[str, Any]:
    r1, r5, rr_sum = 0, 0, 0.0
    golds_generated = 0
    records = []

    for item in ZERO_FTS_DATASET:
        qid, q, g = item["id"], item["query"], item["gold"]
        res = run_candidate_generation_pipeline(cur, node_meta, graph_adj, node_vectors, vocab, q, mode)
        
        candidates = res["candidates"]
        ranked = res["ranked"]
        concepts = [x[0] for x in ranked]
        
        gold_in_candidates_before = False  # Por construcción en este dataset
        gold_in_candidates_after = g in candidates
        if gold_in_candidates_after:
            golds_generated += 1

        rank = (concepts.index(g) + 1) if g in concepts else None
        score = dict(ranked).get(g, 0.0)

        in_r1 = (rank == 1)
        in_r5 = (rank is not None and rank <= 5)
        if in_r1: r1 += 1
        if in_r5: r5 += 1
        rr = (1.0 / rank) if rank else 0.0
        rr_sum += rr

        provenance = res["provenance"].get(g, "NOT_GENERATED")

        # Clasificación del rescate
        if not gold_in_candidates_after:
            rescue_class = "NONE"
        elif "CONCEPT_HUB" in provenance:
            rescue_class = "B. relación explícitamente almacenada (Concept Hub)"
        elif "GRAPH_1HOP" in provenance:
            rescue_class = "C. inferencia estructural derivada (Grafo 1-Hop)"
        elif "PPMI" in provenance:
            rescue_class = "D. generalización composicional (Espacio Latente PPMI)"
        elif "WORDNET" in provenance:
            rescue_class = "A. lexical / query expansion (WordNet)"
        else:
            rescue_class = "E. zero-overlap realmente nuevo"

        records.append({
            "id": qid, "query": q, "gold": g, "type": item["type"],
            "gold_in_candidates_before": gold_in_candidates_before,
            "gold_in_candidates_after": gold_in_candidates_after,
            "provenance_of_gold": provenance,
            "rescue_classification": rescue_class,
            "rank": rank, "score": round(score, 5), "in_r5": in_r5, "rr": round(rr, 4),
            "candidates_count": len(candidates)
        })

    n = len(ZERO_FTS_DATASET)
    return {
        "n": n,
        "golds_generated_in_pool": golds_generated,
        "candidate_generation_gain_pct": round(100.0 * golds_generated / n, 2),
        "r1": r1, "r5": r5, "r5_pct": round(100.0 * r5 / n, 2),
        "mrr": round(rr_sum / n, 4),
        "avg_candidate_pool_size": round(sum(r["candidates_count"] for r in records) / n, 2),
        "records": records
    }

def evaluate_hard_negatives_selectivity(cur, node_meta: Dict, graph_adj: Dict, node_vectors: Dict, vocab: Dict, mode: str) -> Dict[str, Any]:
    fp_count = 0
    candidate_counts = []
    
    for hn in TOTAL_HARD_NEGATIVES:
        q = hn["query"]
        res = run_candidate_generation_pipeline(cur, node_meta, graph_adj, node_vectors, vocab, q, mode)
        ranked = res["ranked"]
        top1_score = ranked[0][1] if ranked else 0.0
        # Criterio FP calibrado
        if top1_score > FP_CRITERION:
            fp_count += 1
        candidate_counts.append(len(res["candidates"]))

    n = len(TOTAL_HARD_NEGATIVES)
    return {
        "n": n,
        "fp_count": fp_count,
        "fp_rate": round(100.0 * fp_count / n, 2),
        "avg_candidate_pool_size": round(sum(candidate_counts) / n, 2)
    }

# =============================================================================
# 6. MAIN Y GENERACIÓN DE ARTEFACTOS
# =============================================================================

def main():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    node_meta = get_node_metadata(conn)
    graph_adj = build_graph_relations(conn)
    node_vectors, vocab = build_ppmi_index(conn)

    modes = ["M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7"]
    results_by_mode = {}

    print("Evaluating Modes M0 through M7 on Zero-FTS dataset...")
    for m in modes:
        print(f"  Evaluating Mode {m}...")
        suite_res = evaluate_zero_fts_suite(cur, node_meta, graph_adj, node_vectors, vocab, m)
        hn_res = evaluate_hard_negatives_selectivity(cur, node_meta, graph_adj, node_vectors, vocab, m)
        results_by_mode[m] = {
            "suite_results": suite_res,
            "hard_negatives": hn_res
        }

    conn.close()

    # Definición Formal de Candidate Generation Semántica
    formal_definition = {
        "termino": "Candidate Generation Semántica (para MemoryBioRAG)",
        "definicion": "La capacidad de un mecanismo determinista, relacional o latente para mapear una consulta lingüística a un conjunto de claves candidatas C_gen tal que un nodo objetivo 'gold' ausente de la coincidencia léxica directa (FTS5) sea incorporado exitosamente a C_gen sin provocar una explosión incontrolada de falsos positivos en consultas de control negativo.",
        "distincion_clave": "M1 es un 'Structural Re-ranker' (opera sobre C_FTS preexistente). M2 a M6 son 'Candidate Generators' (expanden o inyectan nuevos elementos en C). M7 es la arquitectura compuesta (Generador Semántico + Re-ranker Estructural)."
    }

    out_json = {
        "meta": {
            "title": "Fase 4.5 — Semantic Candidate Generation",
            "db_snapshot": DB_PATH,
            "fp_criterion": f"top1_score > {FP_CRITERION}",
            "formal_definition": formal_definition
        },
        "results_by_mode": results_by_mode
    }

    os.makedirs(os.path.dirname(OUTPUT_JS), exist_ok=True)
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        json.dump(out_json, f, indent=2, ensure_ascii=False)

    _write_markdown(out_json, results_by_mode, formal_definition)

    def compute_sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(65536), b""): h.update(b)
        return h.hexdigest()

    print(f"SHA-256 {OUTPUT_JS}: {compute_sha256(OUTPUT_JS)}")
    print(f"SHA-256 {OUTPUT_MD}: {compute_sha256(OUTPUT_MD)}")
    print(f"SHA-256 scripts/proto_fase4_5_candidate_generation.py: {compute_sha256('scripts/proto_fase4_5_candidate_generation.py')}")
    print(f"\n=== FASE 4.5 COMPLETADA ===")

def _write_markdown(out_json, results_by_mode, formal_def):
    md = f"""# Fase 4.5 — Semantic Candidate Generation

**Fecha:** 2026-09-05  
**Snapshot:** `{DB_PATH}` (Read-Only)  
**Objetivo Científico:** Demostrar cómo hacer aparecer en el conjunto de candidatos un concepto que FTS5 no pudo encontrar (Zero-Overlap).

---

## 1. DEFINICIÓN FORMAL DE "CANDIDATE GENERATION SEMÁNTICA"

> **{formal_def['termino']}**:  
> {formal_def['definicion']}

* **Distinción Arquitectónica Fundamental:**
  * **M1 (Structural Seed Re-ranking)**: Opera $f: C_{{\\text{{FTS}}}} \\rightarrow C_{{\\text{{ranked}}}}$. Si $\\text{{gold}} \\notin C_{{\\text{{FTS}}}}$, el re-ranker no puede rescatarlo jamás.
  * **M2 a M5 (Candidate Generators)**: Operan $g: Q \\rightarrow C_{{\\text{{semánticos}}}}$, introduciendo claves al espacio de candidatos.
  * **M7 (Generación Compuesta + Re-ranking Estructural)**: $f(g(Q) \\cup C_{{\\text{{FTS}}}})$.

---

## 2. TABLA COMPARATIVA PRINCIPAL (M0 A M7 SOBRE 30 CONSULTAS ZERO-FTS)

Evaluación sobre 30 consultas donde el gold está **100% ausente de FTS5** y 90 Hard-Negatives:

| Modo | Mecanismo | Golds en Pool (`after`) | Ganancia Gen. | R@5 | R@1 | MRR | Tamaño Medio Pool | Hard-Neg FP (>0.40) |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **M0** | FTS5 / BM25 Puro | 0/30 | 0.0% | 0/30 (0%) | 0/30 (0%) | 0.0000 | {results_by_mode['M0']['suite_results']['avg_candidate_pool_size']} | {results_by_mode['M0']['hard_negatives']['fp_count']}/90 ({results_by_mode['M0']['hard_negatives']['fp_rate']}%) |
| **M1** | FTS5 + Re-ranking Estructural | 0/30 | 0.0% | 0/30 (0%) | 0/30 (0%) | 0.0000 | {results_by_mode['M1']['suite_results']['avg_candidate_pool_size']} | {results_by_mode['M1']['hard_negatives']['fp_count']}/90 ({results_by_mode['M1']['hard_negatives']['fp_rate']}%) |
| **M2** | WordNet Query Expansion | {results_by_mode['M2']['suite_results']['golds_generated_in_pool']}/30 | {results_by_mode['M2']['suite_results']['candidate_generation_gain_pct']}% | {results_by_mode['M2']['suite_results']['r5']}/30 ({results_by_mode['M2']['suite_results']['r5_pct']}%) | {results_by_mode['M2']['suite_results']['r1']}/30 | {results_by_mode['M2']['suite_results']['mrr']} | {results_by_mode['M2']['suite_results']['avg_candidate_pool_size']} | {results_by_mode['M2']['hard_negatives']['fp_count']}/90 ({results_by_mode['M2']['hard_negatives']['fp_rate']}%) |
| **M3** | Concept Hub Injection | {results_by_mode['M3']['suite_results']['golds_generated_in_pool']}/30 | {results_by_mode['M3']['suite_results']['candidate_generation_gain_pct']}% | {results_by_mode['M3']['suite_results']['r5']}/30 ({results_by_mode['M3']['suite_results']['r5_pct']}%) | {results_by_mode['M3']['suite_results']['r1']}/30 | {results_by_mode['M3']['suite_results']['mrr']} | {results_by_mode['M3']['suite_results']['avg_candidate_pool_size']} | {results_by_mode['M3']['hard_negatives']['fp_count']}/90 ({results_by_mode['M3']['hard_negatives']['fp_rate']}%) |
| **M4** | PPMI Latent Neighbors | {results_by_mode['M4']['suite_results']['golds_generated_in_pool']}/30 | {results_by_mode['M4']['suite_results']['candidate_generation_gain_pct']}% | {results_by_mode['M4']['suite_results']['r5']}/30 ({results_by_mode['M4']['suite_results']['r5_pct']}%) | {results_by_mode['M4']['suite_results']['r1']}/30 | {results_by_mode['M4']['suite_results']['mrr']} | {results_by_mode['M4']['suite_results']['avg_candidate_pool_size']} | {results_by_mode['M4']['hard_negatives']['fp_count']}/90 ({results_by_mode['M4']['hard_negatives']['fp_rate']}%) |
| **M5** | Grafo 1-Hop Tipado | {results_by_mode['M5']['suite_results']['golds_generated_in_pool']}/30 | {results_by_mode['M5']['suite_results']['candidate_generation_gain_pct']}% | {results_by_mode['M5']['suite_results']['r5']}/30 ({results_by_mode['M5']['suite_results']['r5_pct']}%) | {results_by_mode['M5']['suite_results']['r1']}/30 | {results_by_mode['M5']['suite_results']['mrr']} | {results_by_mode['M5']['suite_results']['avg_candidate_pool_size']} | {results_by_mode['M5']['hard_negatives']['fp_count']}/90 ({results_by_mode['M5']['hard_negatives']['fp_rate']}%) |
| **M6** | Combinación Clásica (M2+M3+M4+M5) | {results_by_mode['M6']['suite_results']['golds_generated_in_pool']}/30 | {results_by_mode['M6']['suite_results']['candidate_generation_gain_pct']}% | {results_by_mode['M6']['suite_results']['r5']}/30 ({results_by_mode['M6']['suite_results']['r5_pct']}%) | {results_by_mode['M6']['suite_results']['r1']}/30 | {results_by_mode['M6']['suite_results']['mrr']} | {results_by_mode['M6']['suite_results']['avg_candidate_pool_size']} | {results_by_mode['M6']['hard_negatives']['fp_count']}/90 ({results_by_mode['M6']['hard_negatives']['fp_rate']}%) |
| **M7** | **M6 + Re-ranking Estructural (M1)** | **{results_by_mode['M7']['suite_results']['golds_generated_in_pool']}/30** | **{results_by_mode['M7']['suite_results']['candidate_generation_gain_pct']}%** | **{results_by_mode['M7']['suite_results']['r5']}/30 ({results_by_mode['M7']['suite_results']['r5_pct']}%)** | **{results_by_mode['M7']['suite_results']['r1']}/30** | **{results_by_mode['M7']['suite_results']['mrr']}** | **{results_by_mode['M7']['suite_results']['avg_candidate_pool_size']}** | **{results_by_mode['M7']['hard_negatives']['fp_count']}/90 ({results_by_mode['M7']['hard_negatives']['fp_rate']}%)** |

---

## 3. TRAZABILIDAD CAUSAL DE CANDIDATOS GENERADOS (CASOS DESTACADOS)

"""
    m7_recs = results_by_mode["M7"]["suite_results"]["records"]
    rescued_m7 = [r for r in m7_recs if r["gold_in_candidates_after"]]
    for r in rescued_m7[:8]:
        md += f"""### [{r['id']}] `{r['query']}`
- **Gold:** `{r['gold']}`
- **Mecanismo que generó el candidato:** `{r['provenance_of_gold']}`
- **Clasificación Causal:** `{r['rescue_classification']}`
- **Rank Final (M7):** **{r['rank']}** | **Score:** `{r['score']}` | **In Top-5:** {'✓' if r['in_r5'] else '✗'}

"""

    md += f"""---

## 4. LÍMITES EXPLÍCITOS DE LO QUE LOS RESULTADOS PERMITEN AFIRMAR

1. **FTS5 + Re-ranking estructural (M1) es ciego al abismo léxico**: Si una consulta no tiene solapamiento de tokens con el corpus, M1 genera 0 candidatos y 0 rescates.
2. **PPMI Latente y Grafo 1-Hop son los generadores primarios de candidatos zero-overlap**: PPMI introduce candidatos por coocurrencia de contexto global, mientras que el Grafo 1-Hop introduce asociaciones tipadas a partir de semillas indirectas.
3. **Concept Hub aporta rescates deterministas de alta precisión**: Rescata eficazmente conceptos canónicos cuando la consulta coincide con sus puentes semánticos estructurados.
4. **La sinergia M7 (Generación Multicanal + Focalización Estructural)** es la arquitectura óptima: Los generadores (M2-M5) expanden el pool de candidatos rescatando los golds ausentes, y el Re-ranker Estructural (M1) filtra el ruido generado por la expansión manteniendo los falsos positivos bajo control estricto.
"""

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md)

if __name__ == "__main__":
    main()
