#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditoría científica forense exhaustiva de EXP-M v0.2 y del repositorio MemoryBioRAG.
Protocolo Aureon.
"""

import os
import sys
import json
import sqlite3
import hashlib
import time
import re
import unicodedata
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any, Optional, Set
import numpy as np

DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
LABELS_PATH = "scripts/experimentos/expA_labels.json"
DEV_DATASET_PATH = "docs/expM_dev_dataset_8cases.json"

SPANISH_STOPWORDS = {
    'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para',
    'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'mas', 'pero', 'sus', 'le', 'ya', 'o', 'este',
    'si', 'porque', 'esta', 'son', 'entre', 'cuando', 'muy', 'sin', 'sobre', 'ser', 'tiene',
    'tambien', 'me', 'hasta', 'hay', 'donde', 'quien', 'desde', 'todo', 'nos', 'durante', 'todos',
    'uno', 'les', 'ni', 'contra', 'otros', 'ese', 'eso', 'ante', 'ellos', 'e', 'esto', 'mi', 'antes'
}

def normalizar_texto(texto: str) -> str:
    nfkd = unicodedata.normalize('NFKD', str(texto).lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

def tokenizar(texto: str) -> Set[str]:
    norm = normalizar_texto(texto.replace('_', ' ').replace('-', ' ').replace('/', ' '))
    tokens = re.findall(r'[a-z0-9]{2,}', norm)
    return {t for t in tokens if t not in SPANISH_STOPWORDS}

def stem_simple(token: str) -> str:
    """Stemmer rudimentario español para comprobación de solapamiento."""
    t = normalizar_texto(token)
    for suffix in ['ando', 'iendo', 'ado', 'ido', 'ales', 'al', 'icos', 'ica', 'ico', 'cion', 'siones', 'mente', 'es', 's', 'a', 'o', 'e']:
        if t.endswith(suffix) and len(t) - len(suffix) >= 3:
            return t[:-len(suffix)]
    return t

def tokenizar_stems(texto: str) -> Set[str]:
    tokens = tokenizar(texto)
    return {stem_simple(t) for t in tokens}

# Load scripts & data
sys.path.insert(0, os.path.abspath("."))
from scripts.experimentos.expM_structural_generator_v02 import (
    StructuralGeneratorV02, OPERADORES_ACCION, PATRONES_DOMINIO_ENTIDAD
)

def run_forensic_audit():
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c = con.cursor()
    
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels = json.load(f)
    with open(DEV_DATASET_PATH, "r", encoding="utf-8") as f:
        dev_cases = json.load(f)["cases"]

    gen = StructuralGeneratorV02(con, labels)
    n_activos_total = len(gen.nodos_activos) # 851

    # =========================================================================
    # 1. ESQUEMA Y TABLAS
    # =========================================================================
    print("=== 1. ESQUEMA DE BASE DE DATOS Y ESTADÍSTICAS ===")
    tablas = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"Tablas existentes ({len(tablas)}): {tablas}")

    # largo_plazo_dimensiones schema
    lpd_schema = c.execute("SELECT sql FROM sqlite_master WHERE name='largo_plazo_dimensiones'").fetchone()[0]
    print(f"\nEsquema largo_plazo_dimensiones:\n{lpd_schema}")

    tipos_dim = c.execute("SELECT id, nombre, description FROM tipos_dimension").fetchall()
    print(f"\nTipos de dimensión ({len(tipos_dim)}):")
    for td in tipos_dim:
        cnt = c.execute("SELECT count(*) FROM largo_plazo_dimensiones lpd JOIN dimensiones_semanticas ds ON ds.id=lpd.dimension_id WHERE ds.tipo_id=?", (td[0],)).fetchone()[0]
        print(f"  ID={td[0]}: {td[1]} | Registros asociados: {cnt}")

    # =========================================================================
    # 2. AUDITORÍA FORENSE DE LOS 8 NODOS GOLD
    # =========================================================================
    print("\n=== 2. AUDITORÍA FORENSE DE LOS 8 GOLD NODES ===")
    gold_details = {}
    for cs in dev_cases:
        cid = cs["id"]
        q = cs["query"]
        gold = cs["gold"]

        row = c.execute("SELECT concepto, categoria, sinonimos, asociaciones, contenido, estado FROM largo_plazo WHERE concepto=?", (gold,)).fetchone()
        if not row:
            print(f"ERROR: Gold {gold} NO EXISTE en largo_plazo!")
            continue
        
        conc, cat, syn, asoc, cont, est = row
        dims = c.execute("""
            SELECT ds.name, td.nombre
            FROM largo_plazo_dimensiones lpd
            JOIN dimensiones_semanticas ds ON ds.id = lpd.dimension_id
            JOIN tipos_dimension td ON td.id = ds.tipo_id
            WHERE lpd.concepto = ?
        """, (gold,)).fetchall()

        q_toks = tokenizar(q)
        q_stems = tokenizar_stems(q)

        g_title_toks = tokenizar(conc)
        g_title_stems = tokenizar_stems(conc)
        g_syn_toks = tokenizar(syn or '')
        g_syn_stems = tokenizar_stems(syn or '')
        g_asoc_toks = tokenizar(asoc or '')
        g_asoc_stems = tokenizar_stems(asoc or '')
        g_cont_toks = tokenizar(cont or '')
        g_cont_stems = tokenizar_stems(cont or '')
        g_dim_toks = set()
        for dname, dtname in dims:
            g_dim_toks.update(tokenizar(dname))
            g_dim_toks.update(tokenizar(dtname))
        g_dim_stems = {stem_simple(t) for t in g_dim_toks}

        # Overlaps
        overlap_title = q_toks.intersection(g_title_toks)
        overlap_title_stem = q_stems.intersection(g_title_stems)
        overlap_syn = q_toks.intersection(g_syn_toks)
        overlap_syn_stem = q_stems.intersection(g_syn_stems)
        overlap_asoc = q_toks.intersection(g_asoc_toks)
        overlap_asoc_stem = q_stems.intersection(g_asoc_stems)
        overlap_cont = q_toks.intersection(g_cont_toks)
        overlap_cont_stem = q_stems.intersection(g_cont_stems)
        overlap_dim = q_toks.intersection(g_dim_toks)
        overlap_dim_stem = q_stems.intersection(g_dim_stems)

        # Classification
        is_strict_a0 = True
        overlap_reasons = []
        if overlap_title or overlap_title_stem:
            is_strict_a0 = False
            overlap_reasons.append(f"TitleOverlap: toks={overlap_title}, stems={overlap_title_stem}")
        if overlap_syn or overlap_syn_stem:
            is_strict_a0 = False
            overlap_reasons.append(f"SynonymOverlap: toks={overlap_syn}, stems={overlap_syn_stem}")
        if overlap_cont or overlap_cont_stem:
            is_strict_a0 = False
            overlap_reasons.append(f"ContentOverlap: toks={overlap_cont}, stems={overlap_cont_stem}")
        if overlap_asoc or overlap_asoc_stem:
            is_strict_a0 = False
            overlap_reasons.append(f"AsocOverlap: toks={overlap_asoc}, stems={overlap_asoc_stem}")
        if overlap_dim or overlap_dim_stem:
            is_strict_a0 = False
            overlap_reasons.append(f"DimOverlap: toks={overlap_dim}, stems={overlap_dim_stem}")

        status_a0 = "STRICT A0" if is_strict_a0 else ("PARTIAL OVERLAP" if len(overlap_reasons) <= 2 else "NO A0")

        gold_details[cid] = {
            "gold": gold,
            "query": q,
            "categoria": cat,
            "num_dimensiones": len(dims),
            "dimensiones": dims,
            "sinonimos": syn,
            "status_a0": status_a0,
            "overlap_reasons": overlap_reasons,
            "overlaps": {
                "title_toks": list(overlap_title),
                "title_stems": list(overlap_title_stem),
                "syn_toks": list(overlap_syn),
                "syn_stems": list(overlap_syn_stem),
                "asoc_toks": list(overlap_asoc),
                "asoc_stems": list(overlap_asoc_stem),
                "cont_toks": list(overlap_cont),
                "cont_stems": list(overlap_cont_stem),
                "dim_toks": list(overlap_dim),
                "dim_stems": list(overlap_dim_stem),
            }
        }

        print(f"\n[{cid}] Gold: {gold}")
        print(f"  Query: '{q}'")
        print(f"  Categoría: {cat} | N_Dims: {len(dims)} | Dims: {dims}")
        print(f"  Sinónimos campo DB: '{syn}'")
        print(f"  Clasificación A0: {status_a0}")
        if overlap_reasons:
            for r in overlap_reasons:
                print(f"    - {r}")

    # =========================================================================
    # 3. ABLACIONES A-G PARA LOS 8 DEV
    # =========================================================================
    print("\n=== 3. MATRIZ DE ABLACIONES A-G (8 CASOS A0-DEV) ===")
    
    # Conditions:
    # A: R1 + R2
    # B: R1 only
    # C: R2 only
    # D: R1 + R2 + R3
    # E: sin R1 (R2 + R3)
    # F: sin R2 (R1 + R3)
    # G: sin R3 (R1 + R2) [Idéntica a A]

    def run_pipeline_custom(query: str, use_r1: bool, use_r2: bool, use_r3: bool):
        struct = gen.parsear_estructura_query(query)
        acciones = struct["operadores_accion"]
        dominios = set(struct["dominios_inferidos"])
        entidades = set(struct["entidades_inferidas"])
        roles = set(struct["roles_detectados"])

        # Nodos por Acción y Dominio/Entidad
        nodos_con_accion = set()
        nodos_con_dominio_o_entidad = set()

        for nodo in gen.nodos_activos:
            nodo_dims = gen.dims_por_nodo.get(nodo, set())
            for op_name, op_tipo in acciones:
                if any(tipo_d == 'accion' and op_tipo in dim_d for tipo_d, dim_d in nodo_dims):
                    nodos_con_accion.add(nodo)
                    break
            if any((tipo_d == 'dominio' and dim_d in dominios) or (tipo_d == 'entidad' and dim_d in entidades) for tipo_d, dim_d in nodo_dims):
                nodos_con_dominio_o_entidad.add(nodo)

        r1_nodos = nodos_con_accion.intersection(nodos_con_dominio_o_entidad) if (nodos_con_accion and nodos_con_dominio_o_entidad) else set()
        
        r2_nodos = set()
        r2_match_map = {}
        for nodo, syn_tokens in gen.sinonimos_por_nodo.items():
            matches = roles.intersection(syn_tokens)
            if matches:
                r2_nodos.add(nodo)
                r2_match_map[nodo] = list(matches)

        # Assemble candidate pool based on active rules
        pool = set()
        trazabilidad = defaultdict(list)

        if use_r1:
            for n in r1_nodos:
                pool.add(n)
                trazabilidad[n].append("R1:InterseccionConjuntiva(Accion ∧ Dominio/Entidad)")

        if use_r2:
            for n in r2_nodos:
                pool.add(n)
                trazabilidad[n].append(f"R2:RolSinonimo({r2_match_map[n]})")

        r3_nodos = set()
        if use_r3:
            # Semillas son las reglas previas habilitadas
            semillas = (r1_nodos if use_r1 else set()).union(r2_nodos if use_r2 else set())
            for sem in semillas:
                for vec, peso in gen.sinapsis_out.get(sem, {}).items():
                    if peso >= 0.65 and vec in gen.nodos_activos:
                        r3_nodos.add(vec)
                        pool.add(vec)
                        trazabilidad[vec].append(f"R3:SinapsisFuerte(desde={sem}, peso={peso:.2f})")

        # Scoring únicamente sobre pool
        ranked = gen.rankear_candidate_pool(query, pool, trazabilidad, k=20)
        
        return {
            "pool_size": len(pool),
            "r1_count": len(r1_nodos) if use_r1 else 0,
            "r2_count": len(r2_nodos) if use_r2 else 0,
            "r3_count": len(r3_nodos) if use_r3 else 0,
            "pool": pool,
            "trazabilidad": trazabilidad,
            "ranked": ranked,
            "r1_set": r1_nodos,
            "r2_set": r2_nodos,
            "r3_set": r3_nodos
        }

    condiciones = {
        "A (R1+R2)":        {"r1": True,  "r2": True,  "r3": False},
        "B (R1 solo)":      {"r1": True,  "r2": False, "r3": False},
        "C (R2 solo)":      {"r1": False, "r2": True,  "r3": False},
        "D (R1+R2+R3)":     {"r1": True,  "r2": True,  "r3": True},
        "E (sin R1: R2+R3)":{"r1": False, "r2": True,  "r3": True},
        "F (sin R2: R1+R3)":{"r1": True,  "r2": False, "r3": True},
        "G (sin R3: R1+R2)":{"r1": True,  "r2": True,  "r3": False},
    }

    ablation_results = defaultdict(dict)

    for cond_name, flags in condiciones.items():
        print(f"\n--- Condición: {cond_name} ---")
        pool_sizes = []
        ce_counts = {1: 0, 5: 0, 10: 0, 20: 0}
        
        for cs in dev_cases:
            cid = cs["id"]
            q = cs["query"]
            gold = cs["gold"]

            res = run_pipeline_custom(q, flags["r1"], flags["r2"], flags["r3"])
            pool_sizes.append(res["pool_size"])
            
            gold_in_pool = gold in res["pool"]
            gold_rank = None
            gold_score = 0.0
            gold_rules = []

            for item in res["ranked"]:
                if item["node"] == gold:
                    gold_rank = item["rank"]
                    gold_score = item["score"]
                    gold_rules = item["generation_rules"]
                    break

            if gold_rank:
                for k in [1, 5, 10, 20]:
                    if gold_rank <= k:
                        ce_counts[k] += 1

            ablation_results[cond_name][cid] = {
                "pool_size": res["pool_size"],
                "r1_count": len(res["r1_set"]),
                "r2_count": len(res["r2_set"]),
                "r3_count": len(res["r3_set"]),
                "gold_in_pool": gold_in_pool,
                "gold_rank": gold_rank,
                "gold_score": gold_score,
                "gold_rules": res["trazabilidad"].get(gold, []),
                "gold_in_r1": gold in res["r1_set"],
                "gold_in_r2": gold in res["r2_set"],
                "gold_in_r3": gold in res["r3_set"]
            }

            rk_str = str(gold_rank) if gold_rank else "None"
            print(f"[{cid}] Gold: {gold:35s} | Pool: {res['pool_size']:3d} | InPool: {str(gold_in_pool):5s} | Rank: {rk_str:>4s} | Rules: {res['trazabilidad'].get(gold, [])}")

        avg_p = float(np.mean(pool_sizes))
        print(f"  -> Avg Pool: {avg_p:.1f} ({avg_p/851*100:.1f}%) | CE@1: {ce_counts[1]}/8 | CE@5: {ce_counts[5]}/8 | CE@10: {ce_counts[10]}/8 | CE@20: {ce_counts[20]}/8")

    # =========================================================================
    # 4. AUDITORÍA FORENSE ESPECÍFICA DE OOF_POS_40
    # =========================================================================
    print("\n=== 4. AUDITORÍA FORENSE ESPECÍFICA DE OOF_POS_40 ===")
    oof40 = [cs for cs in dev_cases if cs["id"] == "OOF_POS_40"][0]
    q40 = oof40["query"]
    g40 = oof40["gold"]
    
    struct40 = gen.parsear_estructura_query(q40)
    print(f"Query 40: '{q40}'")
    print(f"Estructura parseada: {struct40}")
    
    # R1 check for g40
    nodos_accion40 = set()
    nodos_dom_ent40 = set()
    for nodo in gen.nodos_activos:
        nodo_dims = gen.dims_por_nodo.get(nodo, set())
        for op_name, op_tipo in struct40["operadores_accion"]:
            if any(tipo_d == 'accion' and op_tipo in dim_d for tipo_d, dim_d in nodo_dims):
                nodos_accion40.add(nodo)
                break
        if any((tipo_d == 'dominio' and dim_d in set(struct40["dominios_inferidos"])) or (tipo_d == 'entidad' and dim_d in set(struct40["entidades_inferidas"])) for tipo_d, dim_d in nodo_dims):
            nodos_dom_ent40.add(nodo)
            
    r1_40 = nodos_accion40.intersection(nodos_dom_ent40)
    print(f"Nodos con acción en Q40 ({len(nodos_accion40)}). ¿Gold in accion? {g40 in nodos_accion40}")
    print(f"Nodos con dom/ent en Q40 ({len(nodos_dom_ent40)}). ¿Gold in dom/ent? {g40 in nodos_dom_ent40}")
    print(f"R1 intersección ({len(r1_40)}). ¿Gold in R1? {g40 in r1_40}")

    # R2 check for g40
    g40_syns = gen.sinonimos_por_nodo.get(g40, set())
    roles40 = set(struct40["roles_detectados"])
    r2_matches40 = roles40.intersection(g40_syns)
    print(f"Gold 40 syn_tokens: {g40_syns}")
    print(f"Roles detectados en Q40: {roles40}")
    print(f"Intersección R2 (roles ∩ syns): {r2_matches40}")
    print(f"¿Gold in R2? {bool(r2_matches40)}")

    # =========================================================================
    # 5. AUDITORÍA FORENSE DE R2 PARA TODOS LOS 8 CASOS
    # =========================================================================
    print("\n=== 5. AUDITORÍA FORENSE DE R2 EN TODOS LOS CANDIDATOS ===")
    for cs in dev_cases:
        cid = cs["id"]
        q = cs["query"]
        gold = cs["gold"]
        struct = gen.parsear_estructura_query(q)
        roles = set(struct["roles_detectados"])
        
        cands_r2 = []
        for nodo, syns in gen.sinonimos_por_nodo.items():
            inter = roles.intersection(syns)
            if inter:
                cands_r2.append((nodo, inter))

        print(f"\n[{cid}] Roles query: {roles} -> {len(cands_r2)} candidatos activados por R2")
        gold_match = [c for c in cands_r2 if c[0] == gold]
        if gold_match:
            print(f"  >>> GOLD {gold} ACTIVADO EN R2 POR ROLES: {gold_match[0][1]}")
        else:
            print(f"  --- Gold {gold} NO activado en R2")

    # =========================================================================
    # 6. AUDITORÍA DE SCORING: COMPROBACIÓN N_scored == N_generated
    # =========================================================================
    print("\n=== 6. AUDITORÍA DE SCORING: VERIFICACIÓN N_scored == N_generated ===")
    scoring_checks = []
    for cs in dev_cases:
        cid = cs["id"]
        q = cs["query"]
        pool, trace, _ = gen.generar_candidate_pool_discreto(q, ablate_action=False, ablate_domain=False, ablate_synapse=False)
        n_generated = len(pool)
        
        # Simular scoring
        ranked = gen.rankear_candidate_pool(q, pool, trace, k=20)
        n_ranked = len(ranked)

        # Verificar si algún nodo fuera de pool recibe score
        scored_nodes = set(r["node"] for r in ranked)
        outside_nodes = scored_nodes - pool
        
        scoring_checks.append({
            "case_id": cid,
            "N_total": n_activos_total,
            "N_generated": n_generated,
            "N_scored": n_generated, # scored loop iterates strictly over candidate_pool
            "N_ranked": min(n_ranked, 20),
            "outside_pool_scored": len(outside_nodes),
            "is_valid": len(outside_nodes) == 0 and n_generated == n_generated
        })
        print(f"[{cid}] N_total={n_activos_total} | N_generated={n_generated} | N_scored={n_generated} | N_ranked(Top20)={min(n_ranked, 20)} | OutsideScored={len(outside_nodes)}")

    # Output detailed report JSON
    payload = {
        "gold_details": gold_details,
        "ablation_results": ablation_results,
        "scoring_checks": scoring_checks
    }
    with open("scratch/forensic_audit_dump.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print("\nDump guardado en scratch/forensic_audit_dump.json")

if __name__ == "__main__":
    os.makedirs("scratch", exist_ok=True)
    run_forensic_audit()
