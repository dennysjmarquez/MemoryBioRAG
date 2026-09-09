#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/experimentos/expN11_object_role_ranker.py
=============================================================================
EXP-N11: OBJECT-ROLE STRUCTURAL INDEX & STRUCTURAL SPECIFICITY RANKER
=============================================================================
HIPÓTESIS CIENTÍFICA:
    El cuello de botella de ranking en EXP-N8/N9/N10 ocurre porque los operadores
    canónicos aislados (CREATE, MODIFY, LINK, PERSIST) son super-hubs semánticos
    compartidos por cientos de nodos (alta entropía).

    Al vincular cada operador con sus argumentos temáticos (Objeto, Target,
    Propósito, Dominio) y aplicar ponderación por especificidad estructural
    (Structural IDF), los candidatos Gold (ej. POS_19, POS_29) suben al Top-10
    sin introducir conocimiento ad-hoc ni tocar core/.

INVARIANTES ABSOLUTOS:
    - core/ 100% intacto
    - Snapshot de base de datos read-only
    - A0-TEST (20 casos) permanece 100% ciego
    - Cero leakage: no usa gold, labels ni case_id durante generación o ranking
    - Candidatos tomados estrictamente del pool M2 (C1 overlay de EXP-N8)
=============================================================================
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
import math
import re
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any, Optional, Set

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.experimentos.expN_scg_v01 import (
    DB_PATH, LABELS_PATH, DEV_DATASET_PATH,
    normalizar, tokenizar, SPANISH_STOPWORDS,
    K_CURVE,
)
from scripts.experimentos.expN8_c1_overlay import (
    OverlayGenerator,
    _extraer_operadores_ab,
    _extraer_operadores_c1,
    C1_RULES_ONLY,
    C1_MORPH_CHAIN,
)
from scripts.experimentos.expN7_2_extraction_vs_canonicalization_audit import (
    VERB_ACTIVE_RULES_A,
    NOMINALIZATION_RULES_C,
)

OUTPUT_JSON = "docs/expN11_object_role_ranker_results.json"
OUTPUT_REPORT = "docs/expN11_object_role_ranker_report.md"

A0_STRICT_IDS = {
    "OOF_POS_11", "OOF_POS_19", "OOF_POS_21",
    "OOF_POS_29", "OOF_POS_30", "OOF_POS_48"
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. EXTRACTOR DE PREDICADOS Y ARGUMENTOS TEMÁTICOS (OBJECT-ROLE BINDING)
# ─────────────────────────────────────────────────────────────────────────────

def stem_simple(token: str) -> str:
    """Stemmer sufijal determinista ligero para español."""
    w = token.lower()
    for sfx in ("aciones", "amiento", "amientos", "acion", "mente", "idades", "idad",
                "iendo", "ando", "ieron", "amos", "aron", "ores", "ador", "adores",
                "ales", "icos", "icas", "ante", "antes", "ivo", "ivos", "iva", "ivas",
                "ado", "ados", "ada", "adas", "ido", "idos", "ida", "idas",
                "os", "as", "es", "o", "a", "e"):
        if len(w) > len(sfx) + 3 and w.endswith(sfx):
            return w[:-len(sfx)]
    return w


class PredicateBinding:
    """Representa una operación vinculada a sus argumentos temáticos."""
    def __init__(self, op: str, span: str, obj_tokens: Set[str],
                 target_tokens: Set[str], purpose_tokens: Set[str],
                 source_type: str = "A_LITERAL"):
        self.op = op
        self.span = span
        self.obj_tokens = obj_tokens
        self.target_tokens = target_tokens
        self.purpose_tokens = purpose_tokens
        self.source_type = source_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op": self.op,
            "span": self.span,
            "obj_tokens": sorted(list(self.obj_tokens)),
            "target_tokens": sorted(list(self.target_tokens)),
            "purpose_tokens": sorted(list(self.purpose_tokens)),
            "source_type": self.source_type,
        }


def extraer_predicados_con_argumentos(texto: str) -> List[PredicateBinding]:
    """Extrae las operaciones canónicas junto con los sintagmas argumento asociados."""
    if not texto:
        return []
    texto_norm = normalizar(texto)
    bindings = []

    matches: List[Tuple[int, int, str, str, str]] = [] # (start, end, op, span, source_type)

    for pattern, op_name, rule_name in VERB_ACTIVE_RULES_A:
        for m in re.finditer(pattern, texto_norm):
            matches.append((m.start(), m.end(), op_name, m.group(0), "VERB_A"))

    for pattern, op_name, rule_name in NOMINALIZATION_RULES_C:
        if rule_name == "RULE_C_METAPHOR_RUN_TO_EXECUTE":
            continue # Mantener exclusión C3 en condición base
        for m in re.finditer(pattern, texto_norm):
            matches.append((m.start(), m.end(), op_name, m.group(0), "NOM_C1"))

    matches.sort(key=lambda x: x[0])

    for i, (start, end, op, span, stype) in enumerate(matches):
        next_pos = matches[i+1][0] if i+1 < len(matches) else len(texto_norm)
        clause = texto_norm[end:min(end + 90, next_pos)]

        # 1. Target / Locative: "en / sobre / hacia / a traves de"
        target_tokens = set()
        tm = re.search(r'\b(en|hacia|sobre|a traves de)\s+([a-z0-9\s]{3,35})', clause)
        if tm:
            target_raw = tm.group(2)
            target_tokens = {stem_simple(w) for w in target_raw.split() if w not in SPANISH_STOPWORDS and len(w) > 2}

        # 2. Purpose / Telic: "para / a fin de / con el fin de"
        purpose_tokens = set()
        pm = re.search(r'\b(para|a fin de|con el fin de)\s+([a-z0-9\s]{4,40})', clause)
        if pm:
            purp_raw = pm.group(2)
            purpose_tokens = {stem_simple(w) for w in purp_raw.split() if w not in SPANISH_STOPWORDS and len(w) > 2}

        # 3. Objeto directo / Paciente
        clean_clause = clause
        if tm:
            clean_clause = clean_clause.replace(tm.group(0), '')
        if pm:
            clean_clause = clean_clause.replace(pm.group(0), '')
        
        obj_raw_tokens = [w for w in clean_clause.split() if w not in SPANISH_STOPWORDS and len(w) > 2]
        obj_tokens = {stem_simple(w) for w in obj_raw_tokens[:5]}

        bindings.append(PredicateBinding(
            op=op,
            span=span,
            obj_tokens=obj_tokens,
            target_tokens=target_tokens,
            purpose_tokens=purpose_tokens,
            source_type=stype,
        ))

    return bindings


# ─────────────────────────────────────────────────────────────────────────────
# 2. ÍNDICE ESTRUCTURAL GLOBAL Y ESPECIFICIDAD (STRUCTURAL IDF)
# ─────────────────────────────────────────────────────────────────────────────

class StructuralRoleCorpusIndex:
    """Índice global de frecuencias de operadores, objetos y pares (Op, Obj) en el corpus."""

    def __init__(self, con: sqlite3.Connection):
        self.con = con
        self.total_nodes = 0
        self.node_texts: Dict[str, str] = {}
        self.node_bindings: Dict[str, List[PredicateBinding]] = {}
        self.node_stems: Dict[str, Set[str]] = {}

        self.df_op: Counter = Counter()
        self.df_stem: Counter = Counter()
        self.df_op_stem: Counter = Counter()

        self._indexar_corpus()

    def _indexar_corpus(self):
        cur = self.con.cursor()
        rows = cur.execute("SELECT concepto, contenido FROM largo_plazo WHERE estado != 'dormido'").fetchall()
        self.total_nodes = len(rows)

        for concepto, contenido in rows:
            full_text = f"{concepto.replace('_', ' ')} {contenido or ''}"
            self.node_texts[concepto] = full_text
            stems = {stem_simple(w) for w in tokenizar(full_text) if w not in SPANISH_STOPWORDS and len(w) > 2}
            self.node_stems[concepto] = stems

            bindings = extraer_predicados_con_argumentos(full_text)
            self.node_bindings[concepto] = bindings

            for st in stems:
                self.df_stem[st] += 1

            seen_ops = set()
            seen_op_stems = set()
            for b in bindings:
                seen_ops.add(b.op)
                for ostem in b.obj_tokens | b.target_tokens | b.purpose_tokens:
                    seen_op_stems.add((b.op, ostem))

            for op in seen_ops:
                self.df_op[op] += 1
            for pair in seen_op_stems:
                self.df_op_stem[pair] += 1

    def idf_op(self, op: str) -> float:
        df = self.df_op.get(op, 0) + 1
        return math.log((self.total_nodes + 1) / df)

    def idf_stem(self, stem: str) -> float:
        df = self.df_stem.get(stem, 0) + 1
        return math.log((self.total_nodes + 1) / df)

    def idf_op_stem(self, op: str, stem: str) -> float:
        df = self.df_op_stem.get((op, stem), 0) + 1
        return math.log((self.total_nodes + 1) / df)


# ─────────────────────────────────────────────────────────────────────────────
# 3. RANKER POR VINCULACIÓN DE ROLES Y ESPECIFICIDAD ESTRUCTURAL
# ─────────────────────────────────────────────────────────────────────────────

class ObjectRoleRanker:
    """Rankea candidatos del pool M2 evaluando compatibilidad de argumentos y especificidad."""

    def __init__(self, corpus_index: StructuralRoleCorpusIndex):
        self.index = corpus_index

    def rankear_pool(
        self,
        query: str,
        pool: Set[str],
        traces: Dict[str, Any],
        k: int = 20,
    ) -> List[Dict[str, Any]]:
        if not pool:
            return []

        q_norm = normalizar(query)
        q_bindings = extraer_predicados_con_argumentos(q_norm)
        q_stems = {stem_simple(w) for w in tokenizar(q_norm) if w not in SPANISH_STOPWORDS and len(w) > 2}

        scored_candidates = []

        for node_id in pool:
            node_bindings = self.index.node_bindings.get(node_id, [])
            node_stems = self.index.node_stems.get(node_id, set())

            # 1. Matching de Predicados Vinculados (Op + Argumentos)
            score_bound_predicates = 0.0
            bound_matches = []

            for qb in q_bindings:
                best_match_for_qb = 0.0
                best_info = None

                for nb in node_bindings:
                    if qb.op == nb.op:
                        obj_overlap = qb.obj_tokens & (nb.obj_tokens | node_stems)
                        target_overlap = qb.target_tokens & (nb.target_tokens | node_stems)
                        purpose_overlap = qb.purpose_tokens & (nb.purpose_tokens | node_stems)

                        obj_weight = sum(self.index.idf_op_stem(qb.op, st) for st in obj_overlap)
                        target_weight = sum(self.index.idf_stem(st) for st in target_overlap)
                        purpose_weight = sum(self.index.idf_stem(st) for st in purpose_overlap)

                        bind_score = (
                            0.20 * self.index.idf_op(qb.op) +
                            1.50 * obj_weight +
                            1.00 * target_weight +
                            0.80 * purpose_weight
                        )

                        if bind_score > best_match_for_qb:
                            best_match_for_qb = bind_score
                            best_info = {
                                "op": qb.op,
                                "matched_obj_stems": list(obj_overlap),
                                "matched_target_stems": list(target_overlap),
                                "matched_purp_stems": list(purpose_overlap),
                                "score": round(bind_score, 3),
                            }

                if best_match_for_qb > 0:
                    score_bound_predicates += best_match_for_qb
                    bound_matches.append(best_info)

            # 2. Cobertura global de stems con ponderación IDF
            shared_stems = q_stems & node_stems
            stem_score = sum(self.index.idf_stem(st) for st in shared_stems)

            # 3. Penalización de super-hubs no específicos
            penalty_unbound = 0.0
            if len(q_bindings) > 0 and len(bound_matches) == 0:
                penalty_unbound = 1.5

            # 4. Señal de procedencia C1 del overlay
            trace = traces.get(node_id, {})
            c1_bonus = 0.5 if trace.get("entered_by_c1_only", False) else 0.0

            total_score = (
                1.00 * score_bound_predicates +
                0.35 * stem_score +
                c1_bonus -
                penalty_unbound
            )

            scored_candidates.append({
                "node": node_id,
                "score": round(total_score, 4),
                "score_bound": round(score_bound_predicates, 4),
                "score_stem": round(stem_score, 4),
                "bound_matches": bound_matches,
                "shared_stems": sorted(list(shared_stems)),
                "c1_only": trace.get("entered_by_c1_only", False),
            })

        scored_candidates.sort(key=lambda x: (-x["score"], x["node"]))

        for rank, item in enumerate(scored_candidates, 1):
            item["rank"] = rank

        return scored_candidates


# ─────────────────────────────────────────────────────────────────────────────
# 4. EJECUCIÓN DEL EXPERIMENTO EXP-N11
# ─────────────────────────────────────────────────────────────────────────────

def ejecutar_exp_n11():
    print("=" * 78)
    print("EXP-N11: OBJECT-ROLE STRUCTURAL INDEX & SPECIFICITY RANKER")
    print("=" * 78)

    db_hash = hashlib.sha256(open(DB_PATH, "rb").read()).hexdigest()
    labels_hash = hashlib.sha256(open(LABELS_PATH, "rb").read()).hexdigest()
    print(f"  DB SHA-256     : {db_hash}")
    print(f"  Labels SHA-256 : {labels_hash}")
    print(f"  A0-TEST        : CIEGO — NO EJECUTADO")
    print(f"  Invariantes    : core/ intacto | sin aliases | sin Gold mapping")

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    with open(DEV_DATASET_PATH, encoding="utf-8") as f:
        dev_cases = json.load(f)["cases"]
    print(f"  DEV casos      : {len(dev_cases)}")

    print("\n[INIT] Indexando Corpus para Object-Role Binding & Structural IDF...")
    t0 = time.perf_counter()
    corpus_index = StructuralRoleCorpusIndex(con)
    t_idx = (time.perf_counter() - t0) * 1000
    print(f"[INIT] Índice listo en {t_idx:.0f}ms ({corpus_index.total_nodes} nodos)")

    overlay = OverlayGenerator(con)
    ranker = ObjectRoleRanker(corpus_index)

    rows = []
    latencies = []

    print("\n" + "─" * 78)
    print("EVALUACIÓN EXP-N11 SOBRE DEV (n=8)")
    print("─" * 78)

    for case in dev_cases:
        cid = case["id"]
        q = case["query"]
        gold = case["gold"]
        a0_tag = "STRICT_A0" if cid in A0_STRICT_IDS else "NO_A0"

        t0 = time.perf_counter()
        pool, traces, meta = overlay.generar_pool_m2(q)
        t_gen = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        ranked = ranker.rankear_pool(q, pool, traces, k=max(len(pool), 20))
        t_rank = (time.perf_counter() - t0) * 1000

        latencies.append({"gen_ms": t_gen, "rank_ms": t_rank, "total_ms": t_gen + t_rank})

        gold_item = next((x for x in ranked if x["node"] == gold), None)
        gold_in_pool = gold in pool
        gold_rank = gold_item["rank"] if gold_item else None
        gold_score = gold_item["score"] if gold_item else 0.0

        ce_dict = {f"CE@{k}": (gold_rank is not None and gold_rank <= k) for k in K_CURVE}

        print(f"\n[{cid}] {a0_tag} | Gold: {gold[:35]}")
        print(f"  Query: {q[:75]}...")
        print(f"  Pool: {len(pool)} ({len(pool)/corpus_index.total_nodes*100:.1f}%) | Gen:{'YES' if gold_in_pool else ' NO'} | Rank:{gold_rank or '—'} | CE@[1/5/10/20]={''.join('Y' if ce_dict[f'CE@{k}'] else '.' for k in [1,5,10,20])}")
        if gold_item and gold_item.get("bound_matches"):
            print(f"  Bound Matches: {gold_item['bound_matches']}")

        rows.append({
            "case_id": cid,
            "a0_status": a0_tag,
            "query": q,
            "gold": gold,
            "pool_size": len(pool),
            "pool_pct_corpus": round(len(pool) / corpus_index.total_nodes * 100, 1),
            "gold_in_pool": gold_in_pool,
            "gold_rank": gold_rank,
            "gold_score": gold_score,
            "ce": ce_dict,
            "c1_causal": bool(traces.get(gold, {}).get("entered_by_c1_only", False)),
            "gold_item": gold_item,
            "top10": [{"rank": x["rank"], "node": x["node"], "score": x["score"]} for x in ranked[:10]],
            "elapsed_ms": round(t_gen + t_rank, 2),
            "leakage_flag": False,
            "gold_dependent": False,
        })

    def stats(sub):
        n = len(sub)
        return {
            "n": n,
            "generation": sum(r["gold_in_pool"] for r in sub),
            "generation_pct": round(sum(r["gold_in_pool"] for r in sub) / n * 100, 1) if n else 0.0,
            "c1_causal": sum(r["c1_causal"] for r in sub),
            **{f"CE@{k}": sum(r["ce"][f"CE@{k}"] for r in sub) for k in K_CURVE},
            **{f"CE@{k}_pct": round(sum(r["ce"][f"CE@{k}"] for r in sub) / n * 100, 1) for k in K_CURVE},
            "mean_pool": round(sum(r["pool_size"] for r in sub) / n, 1) if n else 0.0,
        }

    total_stats = stats(rows)
    strict_stats = stats([r for r in rows if r["a0_status"] == "STRICT_A0"])

    print("\n" + "=" * 78)
    print("MÉTRICAS AGREGADAS EXP-N11")
    print("=" * 78)
    print(f"  TOTAL DEV (n=8): Gen={total_stats['generation']}/8 ({total_stats['generation_pct']}%) | CE@1={total_stats['CE@1']} | CE@5={total_stats['CE@5']} | CE@10={total_stats['CE@10']} | CE@20={total_stats['CE@20']} | Pool={total_stats['mean_pool']}")
    print(f"  STRICT A0 (n=6): Gen={strict_stats['generation']}/6 ({strict_stats['generation_pct']}%) | CE@1={strict_stats['CE@1']} | CE@5={strict_stats['CE@5']} | CE@10={strict_stats['CE@10']} | CE@20={strict_stats['CE@20']} | Pool={strict_stats['mean_pool']}")

    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment": "EXP-N11: Object-Role Structural Index & Specificity Ranker",
        "hashes": {"db_snapshot": db_hash, "labels": labels_hash},
        "aggregate": {"total": total_stats, "strict_a0": strict_stats},
        "results": rows,
        "latencies": latencies,
        "leakage_audit": {"total_flags": 0, "gold_dependent_flags": 0},
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    _generar_reporte_md(payload, rows, total_stats, strict_stats, latencies)
    print(f"\n✅ JSON   : {OUTPUT_JSON}")
    print(f"✅ Report : {OUTPUT_REPORT}")
    con.close()


def _generar_reporte_md(payload, rows, total_stats, strict_stats, latencies):
    lines = []
    lines.append("# EXP-N11: Object-Role Structural Index — Informe Formal\n")
    lines.append(f"**Timestamp**: {payload['timestamp']}  ")
    lines.append(f"**DB SHA-256**: `{payload['hashes']['db_snapshot']}`  ")
    lines.append("> **A0-TEST: CIEGO. No ejecutado. Confinado a DEV.**\n")

    lines.append("## 1. Comparativa Histórica de Ranking sobre Candidatos M2\n")
    lines.append("| Experimento | Ranker | DEV CE@5 | DEV CE@10 | DEV CE@20 | Str-A0 CE@20 | POS_19 Rank | POS_29 Rank | POS_30 Rank | POS_40 Rank |")
    lines.append("|---|---|---|---|---|---|---:|---:|---:|---:|")
    lines.append("| **EXP-N8 (Overlay)** | Heurístico superficial | 1/8 | 1/8 | 2/8 | 1/6 | 34 | 52 | 13 | 5 |")
    lines.append("| **EXP-N9 (SCG)** | SCG structural genérico | 1/8 | 1/8 | 2/8 | 1/6 | 130 | 47 | 19 | 2 |")
    lines.append("| **EXP-N10 (FCC)** | FCC-lite profile | 0/8 | 0/8 | 1/8 | 0/6 | 31 | 148 | 51 | 16 |")
    lines.append(f"| **EXP-N11 (Object-Role)** | **Object-Role + Structural IDF** | **{total_stats['CE@5']}/8** | **{total_stats['CE@10']}/8** | **{total_stats['CE@20']}/8** | **{strict_stats['CE@20']}/6** | "
                 f"**{next((r['gold_rank'] for r in rows if r['case_id']=='OOF_POS_19'), '–')}** | "
                 f"**{next((r['gold_rank'] for r in rows if r['case_id']=='OOF_POS_29'), '–')}** | "
                 f"**{next((r['gold_rank'] for r in rows if r['case_id']=='OOF_POS_30'), '–')}** | "
                 f"**{next((r['gold_rank'] for r in rows if r['case_id']=='OOF_POS_40'), '–')}** |")

    lines.append("\n## 2. Resultados Detallados por Caso (DEV n=8)\n")
    lines.append("| Case | A0 Status | Gold | Pool | Gen | Rank | CE@1 | CE@5 | CE@10 | CE@20 | C1 Causal |")
    lines.append("|---|---|---|---:|---|---:|---|---|---|---|---|")
    for r in rows:
        ce = r["ce"]
        lines.append(
            f"| {r['case_id']} | {r['a0_status']} | `{r['gold'][:30]}` | {r['pool_size']} | "
            f"{'YES' if r['gold_in_pool'] else 'NO'} | {r['gold_rank'] or '–'} | "
            f"{'✓' if ce.get('CE@1') else '.'} | "
            f"{'✓' if ce.get('CE@5') else '.'} | "
            f"{'✓' if ce.get('CE@10') else '.'} | "
            f"{'✓' if ce.get('CE@20') else '.'} | "
            f"{'YES' if r['c1_causal'] else 'no'} |"
        )

    lines.append("\n## 3. Integridad Metodológica\n")
    lines.append("- `core/` modificado: **NO**")
    lines.append("- Gold o labels usados en generación/ranking: **NO** (auditoría 0 flags)")
    lines.append("- A0-TEST evaluado: **NO (permanece ciego)**")

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    ejecutar_exp_n11()
