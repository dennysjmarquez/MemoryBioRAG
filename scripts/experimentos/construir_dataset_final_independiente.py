#!/usr/bin/env python3
"""
scripts/experimentos/construir_dataset_final_independiente.py

Construcción y Auditoría Estratificada de Candidatos para el Test Final de MemoryBioRAG.
Cumple estrictamente las directrices del Protocolo Arcadia y las observaciones de Aureon:

Estratos Evaluados:
- Estrato A0: Zero-Overlap Estricto (Query ∩ Título = ∅, Query ∩ Cuerpo = ∅, Stems ∩ Stems = ∅, sin puentes de metadatos/sinónimos).
- Estrato A1: Zero-Overlap Literal en Título y Cuerpo, pero existe Puente WordNet / Sinónimos / Asociaciones previas.
- Estrato B:  Asociación Temática Distribuida (Query ∩ Título = ∅, Query ∩ Cuerpo > 0, tipo VAL_TEMA_13).
- Estrato C:  Controles Negativos / Adversariales (Inexistentes, paradojas, fuera de dominio).

Tokenizer Riguroso:
- Separa por guiones bajos (_) y caracteres especiales usando r'[a-z0-9]+'.
- Normalización NFD y eliminación de acentos/diacríticos.
- Filtrado de stopwords en español.
- Stemming Snowball para detección de variantes morfológicas.
"""

import os
import sys
import json
import sqlite3
import hashlib
import unicodedata
import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Set, Tuple
from nltk.stem.snowball import SnowballStemmer

DB_PATH = "snapshots/qa_escape_qcr_20260811.db"
LABELS_PATH = "scripts/experimentos/expA_labels.json"
BASELINE_CASES_PATH = "scripts/casos_qa_baseline_v1.jsonl"
OOF_DATASET_PATH = "docs/fase5_out_of_family_dataset_frozen.json"

OUTPUT_CANDIDATES_AUDIT = "docs/final_test_candidates_audit.json"
OUTPUT_MANIFEST_PRELIMINAR = "docs/final_test_manifest_preliminar.json"
OUTPUT_DATASET_PROPOSED = "docs/final_test_dataset_proposed.json"

stemmer = SnowballStemmer('spanish')

SPANISH_STOPWORDS = {
    'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para',
    'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'mas', 'pero', 'sus', 'le', 'ya', 'o', 'este',
    'si', 'porque', 'esta', 'son', 'entre', 'cuando', 'muy', 'sin', 'sobre', 'ser', 'tiene',
    'tambien', 'me', 'hasta', 'hay', 'donde', 'quien', 'desde', 'todo', 'nos', 'durante', 'todos',
    'uno', 'les', 'ni', 'contra', 'otros', 'ese', 'eso', 'ante', 'ellos', 'e', 'esto', 'mi', 'antes',
    'algunos', 'unos', 'yo', 'otro', 'otras', 'otra', 'tanto', 'esa', 'estos', 'mucho', 'quienes',
    'nada', 'muchos', 'cual', 'sea', 'poco', 'ella', 'estar', 'haber', 'estas', 'estaba', 'estamos',
    'algunas', 'algo', 'nosotros', 'mis', 'tu', 'te', 'ti', 'tus', 'ellas', 'nosotras', 'vosotros',
    'os', 'mio', 'mia', 'mios', 'mias', 'tuyo', 'tuya', 'tuyos', 'tuyas', 'suyo', 'suya', 'suyos',
    'suyas', 'nuestro', 'nuestra', 'nuestros', 'nuestras', 'esos', 'esas', 'estoy', 'estan', 'este',
    'estos', 'he', 'has', 'ha', 'hemos', 'habeis', 'han', 'haya', 'habia', 'hube', 'hubo', 'hubieron',
    'soy', 'eres', 'es', 'somos', 'sois', 'son', 'era', 'eras', 'eramos', 'eran', 'fui', 'fuiste',
    'fue', 'fuimos', 'fueron', 'fuera', 'fueran', 'siendo', 'sido', 'tengo', 'tienes', 'tiene',
    'tenemos', 'tienen', 'tenga', 'tenia', 'tuve', 'tuvo', 'tuvieron'
}


def calcular_sha256_archivo(ruta: str) -> str:
    if not os.path.exists(ruta):
        return "ARCHIVO_NO_EXISTE"
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def tokenize(text: str) -> Set[str]:
    if not text:
        return set()
    text = unicodedata.normalize('NFD', str(text).lower())
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    tokens = re.findall(r'[a-z0-9]+', text)
    return set(t for t in tokens if len(t) > 1 and t not in SPANISH_STOPWORDS)


def stem_set(tokens: Set[str]) -> Set[str]:
    return set(stemmer.stem(t) for t in tokens)


def auditar_caso(query: str, gold_id: str, db_nodes: Dict[str, Any]) -> Dict[str, Any]:
    if gold_id not in db_nodes:
        return {"error": "gold_not_in_db"}
    
    node = db_nodes[gold_id]
    q_tokens = tokenize(query)
    t_tokens = tokenize(node['concepto'])
    b_tokens = tokenize(node['contenido'])
    s_tokens = tokenize(node['sinonimos'])
    a_tokens = tokenize(node['asociaciones'])
    
    q_stems = stem_set(q_tokens)
    t_stems = stem_set(t_tokens)
    b_stems = stem_set(b_tokens)
    s_stems = stem_set(s_tokens)
    a_stems = stem_set(a_tokens)
    
    ov_title = q_tokens & t_tokens
    ov_body = q_tokens & b_tokens
    ov_syn = q_tokens & s_tokens
    ov_assoc = q_tokens & a_tokens
    
    ov_title_stem = q_stems & t_stems
    ov_body_stem = q_stems & b_stems
    ov_syn_stem = q_stems & s_stems
    ov_assoc_stem = q_stems & a_stems
    
    has_text_ov = bool(ov_title or ov_body)
    has_stem_ov = bool(ov_title_stem or ov_body_stem)
    has_meta_bridge = bool(ov_syn or ov_assoc or ov_syn_stem or ov_assoc_stem)
    
    # Determinación de Estrato
    if not has_text_ov and not has_stem_ov:
        if not has_meta_bridge:
            estrato = "A0_zero_overlap_estricto"
        else:
            estrato = "A1_puente_sinonimo_definido"
    elif not ov_title and not ov_title_stem and (ov_body or ov_body_stem):
        estrato = "B_asociacion_tematica"
    else:
        estrato = "OVERLAP_TITULO_EXCLUIDO"
        
    return {
        "query": query,
        "gold": gold_id,
        "estrato": estrato,
        "q_tokens": sorted(list(q_tokens)),
        "t_tokens": sorted(list(t_tokens)),
        "ov_title": sorted(list(ov_title)),
        "ov_body": sorted(list(ov_body)),
        "ov_syn": sorted(list(ov_syn)),
        "ov_assoc": sorted(list(ov_assoc)),
        "ov_title_stem": sorted(list(ov_title_stem)),
        "ov_body_stem": sorted(list(ov_body_stem)),
        "has_meta_bridge": has_meta_bridge
    }


def main():
    print("================================================================================")
    print("CONSTRUCCIÓN Y AUDITORÍA DE CANDIDATOS: DATASET FINAL INDEPENDIENTE")
    print("================================================================================")

    # 1. Hashes de infraestructura base
    db_sha = calcular_sha256_archivo(DB_PATH)
    labels_sha = calcular_sha256_archivo(LABELS_PATH)
    baseline_sha = calcular_sha256_archivo(BASELINE_CASES_PATH)
    oof_sha = calcular_sha256_archivo(OOF_DATASET_PATH)

    print(f"• DB Snapshot SHA-256:     {db_sha}")
    print(f"• expA_labels SHA-256:     {labels_sha}")
    print(f"• Baseline Cases SHA-256:  {baseline_sha}")
    print(f"• Fase 5 OOF SHA-256:      {oof_sha}")

    # 2. Carga y reconciliación de la DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM largo_plazo")
    total_lp = c.fetchone()[0]
    c.execute("SELECT count(*) FROM largo_plazo WHERE estado='activo'")
    total_activos = c.fetchone()[0]
    c.execute("SELECT count(*) FROM largo_plazo WHERE estado='dormido'")
    total_dormidos = c.fetchone()[0]

    print(f"\nReconciliación del Corpus en DB Snapshot:")
    print(f"  - Total registros en 'largo_plazo': {total_lp}")
    print(f"  - Registros con estado='activo':    {total_activos}")
    print(f"  - Registros con estado='dormido':   {total_dormidos}")

    c.execute("SELECT id, concepto, contenido, categoria, sinonimos, asociaciones FROM largo_plazo WHERE estado='activo'")
    db_nodes = {r[1]: {
        'id': r[0], 'concepto': r[1], 'contenido': r[2] or '',
        'categoria': r[3] or '', 'sinonimos': r[4] or '', 'asociaciones': r[5] or ''
    } for r in c.fetchall()}

    # 3. Cargar casos de experimentos previos para marcar contaminación/uso
    with open(BASELINE_CASES_PATH, "r", encoding="utf-8") as f:
        baseline_cases = [json.loads(line) for line in f]

    prev_used_queries = set()
    # expA-expI usaron 61 casos de sinonimo
    # expJ/expK usaron primeros 15 por_tema + 15 pregunta_natural + 10 negativo
    t_c, p_c, n_c = 0, 0, 0
    for idx, cs in enumerate(baseline_cases):
        cat = cs.get("categoria")
        q = cs.get("query") or cs.get("pregunta")
        if cat == "sinonimo":
            prev_used_queries.add(q)
        elif cat == "por_tema" and t_c < 15:
            prev_used_queries.add(q)
            t_c += 1
        elif cat == "pregunta_natural" and p_c < 15:
            prev_used_queries.add(q)
            p_c += 1
        elif cat == "negativo" and n_c < 10:
            prev_used_queries.add(q)
            n_c += 1

    print(f"• Total queries registradas como usadas en expA..expK: {len(prev_used_queries)}")

    # 4. Recolectar y auditar todos los candidatos
    candidatos_pool = []

    # A) Candidatos de Baseline QA v1
    for idx, cs in enumerate(baseline_cases):
        cat = cs.get("categoria")
        q = cs.get("query") or cs.get("pregunta") or ""
        esp = cs.get("concepto_esperado") or cs.get("esperado") or ""
        cid = cs.get("id") or f"BASE_{idx:04d}"
        
        if cat == "negativo":
            candidatos_pool.append({
                "candidate_id": f"BASE_{cid}",
                "original_id": cid,
                "provenance": "casos_qa_baseline_v1.jsonl",
                "category": cat,
                "query": q,
                "gold": None,
                "estrato": "C_negativo",
                "used_in_expA_expK": q in prev_used_queries,
                "audit": {"notes": "Negativo de control del benchmark original"}
            })
            continue

        if esp not in db_nodes:
            continue

        audit_res = auditar_caso(q, esp, db_nodes)
        candidatos_pool.append({
            "candidate_id": f"BASE_{cid}",
            "original_id": cid,
            "provenance": "casos_qa_baseline_v1.jsonl",
            "category": cat,
            "query": q,
            "gold": esp,
            "estrato": audit_res["estrato"],
            "used_in_expA_expK": q in prev_used_queries,
            "audit": audit_res
        })

    # B) Candidatos de Fase 5 Out-of-Family
    if os.path.exists(OOF_DATASET_PATH):
        with open(OOF_DATASET_PATH, "r", encoding="utf-8") as f:
            oof_data = json.load(f)

        for cs in oof_data.get("positive_cases", []):
            cid = cs.get("id")
            q = cs.get("query")
            gold = cs.get("gold")
            if gold not in db_nodes:
                continue
            audit_res = auditar_caso(q, gold, db_nodes)
            candidatos_pool.append({
                "candidate_id": f"OOF_{cid}",
                "original_id": cid,
                "provenance": "docs/fase5_out_of_family_dataset_frozen.json",
                "category": "out_of_family_composition",
                "query": q,
                "gold": gold,
                "estrato": audit_res["estrato"],
                "used_in_expA_expK": False,
                "audit": audit_res
            })

        for cs in oof_data.get("adversarial_cases", []):
            cid = cs.get("id")
            q = cs.get("query")
            candidatos_pool.append({
                "candidate_id": f"OOF_ADV_{cid}",
                "original_id": cid,
                "provenance": "docs/fase5_out_of_family_dataset_frozen.json",
                "category": "adversarial_out_of_family",
                "query": q,
                "gold": None,
                "estrato": "C_negativo",
                "used_in_expA_expK": False,
                "audit": {"notes": "Negativo adversarial composicional"}
            })

    # 5. Agrupar por estrato y filtrar los limpios (no usados en expA..expK)
    por_estrato = {
        "A0_zero_overlap_estricto": [],
        "A1_puente_sinonimo_definido": [],
        "B_asociacion_tematica": [],
        "C_negativo": []
    }

    for cand in candidatos_pool:
        est = cand["estrato"]
        if est in por_estrato:
            por_estrato[est].append(cand)

    print("\n--- RESUMEN DE CANDIDATOS ENCONTRADOS POR ESTRATO ---")
    for est, lista in por_estrato.items():
        total_e = len(lista)
        held_out_e = sum(1 for c in lista if not c["used_in_expA_expK"])
        print(f"• {est:30s}: Total={total_e:4d} | Held-Out Limpios (Sin expA..K)={held_out_e:4d}")

    # 6. Selección Determinista por SHA-256(query + gold)
    N_A0 = 20
    N_A1 = 20
    N_B = 20
    N_C = 15

    def sort_key_hash(cand: Dict[str, Any]) -> str:
        s = f"{cand['query']}||{cand.get('gold') or ''}"
        return hashlib.sha256(s.encode('utf-8')).hexdigest()

    seleccion_propuesta = {}
    for est, target_n in [("A0_zero_overlap_estricto", N_A0),
                          ("A1_puente_sinonimo_definido", N_A1),
                          ("B_asociacion_tematica", N_B),
                          ("C_negativo", N_C)]:
        cands_disponibles = [c for c in por_estrato[est] if not c["used_in_expA_expK"]]
        # Si A1 tiene menos de target_n en held-out, tomamos los held-out limpios disponibles y completamos con los que tienen trazabilidad de expA..I
        if len(cands_disponibles) < target_n and est == "A1_puente_sinonimo_definido":
            adicionales = [c for c in por_estrato[est] if c["used_in_expA_expK"]]
            adicionales.sort(key=sort_key_hash)
            cands_disponibles.extend(adicionales[:(target_n - len(cands_disponibles))])
        
        cands_disponibles.sort(key=sort_key_hash)
        seleccion_propuesta[est] = cands_disponibles[:target_n]

    print("\n--- PROPUESTA DE SELECCIÓN DETERMINISTA (75 CASOS TOTAL) ---")
    for est, lista in seleccion_propuesta.items():
        limpios = sum(1 for c in lista if not c["used_in_expA_expK"])
        reusados = sum(1 for c in lista if c["used_in_expA_expK"])
        print(f"• {est:30s}: {len(lista):2d} casos (Limpios={limpios:2d}, Reusados={reusados:2d})")

    # 7. Guardar auditoría completa y dataset propuesto
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_CANDIDATES_AUDIT, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "total_candidatos_auditados": len(candidatos_pool),
            "conteo_por_estrato": {est: len(l) for est, l in por_estrato.items()},
            "candidatos": candidatos_pool
        }, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Guardada auditoría completa en: {OUTPUT_CANDIDATES_AUDIT}")

    with open(OUTPUT_DATASET_PROPOSED, "w", encoding="utf-8") as f:
        json.dump({
            "dataset_name": "final_test_dataset_proposed",
            "version": "1.0-pre-freeze",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "tokenizer_spec": "r'[a-z0-9]+' lower NFD without accents + spanish stopwords + snowball spanish stemmer",
            "deterministic_rule": "SHA-256(query || gold) lexicographical ascending sort",
            "target_counts": {"A0": N_A0, "A1": N_A1, "B": N_B, "C": N_C},
            "cases_by_stratum": seleccion_propuesta
        }, f, indent=2, ensure_ascii=False)
    print(f"[OK] Guardado dataset propuesto en: {OUTPUT_DATASET_PROPOSED}")

    # 8. Manifiesto Preliminar
    manifest_preliminar = {
        "status": "PRE_FREEZE_REVIEW_PENDING",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hashes_inmutables": {
            "db_snapshot_sha256": db_sha,
            "expA_labels_sha256": labels_sha,
            "baseline_cases_sha256": baseline_sha,
            "oof_dataset_sha256": oof_sha,
            "builder_script_sha256": calcular_sha256_archivo("scripts/experimentos/construir_dataset_final_independiente.py")
        },
        "reconciliacion_corpus": {
            "db_largo_plazo_total": total_lp,
            "db_largo_plazo_activos": total_activos,
            "db_largo_plazo_dormidos": total_dormidos,
            "labels_conceptos_total": 866,
            "labels_unique_islands": 105,
            "explicacion": "851 activos + 15 dormidos = 866 registros totales indexados en expA_labels"
        },
        "formula_audit_interleaved": {
            "expK_case_loop_formula": "s_merged = 0.5 * (0.5*MinMax(sA) + 0.5*MinMax(sC)) + 0.5 * (0.5*MinMax(sA) + 0.5*MinMax(sD))",
            "expK_simplified_linear_form": "0.50 * MinMax(sA) + 0.25 * MinMax(sC) + 0.25 * MinMax(sD)",
            "expK_strategy_table_lambda_discrepancy": "usó 0.5*min_max(sA+sC) + 0.5*min_max(sA+sD) en el diccionario de estrategias",
            "pre_registered_canonical_formula": "S_merged(I) = 0.50*MinMax(S_A(I)) + 0.25*MinMax(S_C(I)) + 0.25*MinMax(S_D(I))",
            "pre_registered_beam_k": 6,
            "pre_registered_lambda": 0.25
        },
        "pre_registered_ablations": [
            {"id": "M0", "name": "Canal A Solo (PPMI 1-vector)", "weights": {"A": 1.0, "C": 0.0, "D": 0.0}},
            {"id": "M1", "name": "Canal A + C (PPMI + 13-D)", "weights": {"A": 0.5, "C": 0.5, "D": 0.0}},
            {"id": "M2", "name": "Canal A + D (PPMI + HDC)", "weights": {"A": 0.5, "C": 0.0, "D": 0.5}},
            {"id": "M3", "name": "Multicanal Ponderado A+C+D", "weights": {"A": 0.50, "C": 0.25, "D": 0.25}},
            {"id": "M4", "name": "Unión Intercalada Top-6 (expK canonico)", "weights": "Ranked Top-6 from s_merged"}
        ],
        "conteos_propuestos": {
            "A0_zero_overlap_estricto": len(seleccion_propuesta["A0_zero_overlap_estricto"]),
            "A1_puente_sinonimo_definido": len(seleccion_propuesta["A1_puente_sinonimo_definido"]),
            "B_asociacion_tematica": len(seleccion_propuesta["B_asociacion_tematica"]),
            "C_negativo": len(seleccion_propuesta["C_negativo"]),
            "total_benchmark": sum(len(l) for l in seleccion_propuesta.values())
        }
    }

    with open(OUTPUT_MANIFEST_PRELIMINAR, "w", encoding="utf-8") as f:
        json.dump(manifest_preliminar, f, indent=2, ensure_ascii=False)
    print(f"[OK] Guardado manifiesto preliminar en: {OUTPUT_MANIFEST_PRELIMINAR}")


if __name__ == "__main__":
    main()
