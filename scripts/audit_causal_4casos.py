#!/usr/bin/env python3
"""
scripts/audit_causal_4casos.py

Auditoría causal instrumentada de los 4 casos afectados de la ablación 2x2.
REGLA: No modifica core/ de forma permanente.
MÉTODO: Monkey-patching de expandir_query_con_hub a nivel de módulo para capturar
        argumentos y retorno exactos tal como los invoca buscar_por_frase.
        Instrumentación manual del estado FTS y expansión interna.
"""

import os
import sys
import re
import sqlite3
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_SNAPSHOT = "snapshots/qa_escape_qcr_20260811.db"

# ──────────────────────────────────────────────────────────────────────────────
# Utilidades de FTS
# ──────────────────────────────────────────────────────────────────────────────
def probe_fts_and(conn, frase):
    """Replica el probe FTS5 AND de buscar_por_frase (L4256-4266)."""
    tokens = [re.sub(r'["\x00]', '', t) for t in frase.split() if t.strip()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return -1, None
    fts_and = " AND ".join(f'"{t}"' for t in tokens)
    try:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM largo_plazo_fts WHERE largo_plazo_fts MATCH ?",
            (fts_and,)
        ).fetchone()[0]
        return cnt, fts_and
    except Exception as e:
        return -1, str(e)


def get_frase_limpia(frase_original):
    """Replica la normalización de frase_limpia (L4228-4237) de buscar_por_frase."""
    import unicodedata
    def strip_accents(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s)
                       if unicodedata.category(c) != 'Mn')
    try:
        from core.stopwords import STOPWORDS_ES
        stopwords_normalized = {strip_accents(w.lower()) for w in STOPWORDS_ES}
    except Exception:
        stopwords_normalized = set()

    clean_p = re.sub(r'[^\w\s_-]', ' ', frase_original.lower())
    clean_tokens = []
    for w in clean_p.split():
        w_clean = strip_accents(w)
        if w_clean not in stopwords_normalized and len(w) >= 2:
            clean_tokens.append(w)
    if clean_tokens:
        return " ".join(clean_tokens)
    return re.sub(r'[^\w\s_-]', ' ', frase_original.lower()).strip()


def probe_wordnet_expansion(frase_limpia_filtrada):
    """
    Replica la lógica WordNet de L4305-4343 de buscar_por_frase.
    Devuelve lista de tokens añadidos y explicación por cada token original.
    """
    try:
        from core.stopwords import STOPWORDS_ES
        from nltk.corpus import wordnet as _wn
    except Exception as e:
        return [], f"WordNet no disponible: {e}"

    tokens_frase_orig = [w for w in frase_limpia_filtrada.split() if len(w) >= 3]
    report = []
    wordnet_terms = []

    for token in tokens_frase_orig[:6]:
        token_l = token.lower()
        if token_l in STOPWORDS_ES:
            report.append(f"  '{token}' → SALTADO (stopword español)")
            continue
        try:
            spa_synsets = _wn.synsets(token_l, lang='spa')
            if spa_synsets:
                report.append(f"  '{token}' → SALTADO (tiene synsets en español: {[s.name() for s in spa_synsets[:2]]})")
                continue
        except Exception:
            pass
        if re.match(r'^[a-zA-Z]{3,}$', token):
            try:
                synsets = _wn.synsets(token)
                added = []
                for s in synsets[:2]:
                    for l in s.lemmas():
                        name = l.name().replace('_', ' ')
                        if name.lower() != token.lower() and name not in wordnet_terms:
                            wordnet_terms.append(name)
                            added.append(name)
                            if len(wordnet_terms) >= 8:
                                break
                    if len(wordnet_terms) >= 8:
                        break
                report.append(f"  '{token}' → EXPANDIDO ASCII. Synsets usados: {[s.name() for s in synsets[:2]]}. Términos añadidos: {added}")
            except Exception as e:
                report.append(f"  '{token}' → ERROR WordNet: {e}")
        else:
            report.append(f"  '{token}' → SALTADO (no es ASCII puro o len<3)")

    return wordnet_terms, report


# ──────────────────────────────────────────────────────────────────────────────
# Instrumentación de expandir_query_con_hub via monkey-patch
# ──────────────────────────────────────────────────────────────────────────────
_hub_trace = {}

def patch_concept_hub():
    """Reemplaza expandir_query_con_hub en el módulo core.concept_hub con wrapper."""
    import core.concept_hub as _chub
    original_fn = _chub.expandir_query_con_hub

    def instrumented_hub(frase_limpia, conn, threshold=0.40, *args, **kwargs):
        result = original_fn(frase_limpia, conn, threshold=threshold, *args, **kwargs)
        _hub_trace['frase_limpia'] = frase_limpia
        _hub_trace['threshold'] = threshold
        _hub_trace['result'] = result
        return result

    _chub.expandir_query_con_hub = instrumented_hub
    return original_fn


def restore_concept_hub(original_fn):
    """Restaura la función original después del trace."""
    import core.concept_hub as _chub
    _chub.expandir_query_con_hub = original_fn


# ──────────────────────────────────────────────────────────────────────────────
# Auditoría de un caso
# ──────────────────────────────────────────────────────────────────────────────
CONFIGS = {
    "C": {"hub": "1", "wn": "0", "nombre": "Hub ON / WN OFF"},
    "D": {"hub": "0", "wn": "0", "nombre": "Hub OFF / WN OFF"},
    "B": {"hub": "0", "wn": "1", "nombre": "Hub OFF / WN ON"},
    "A": {"hub": "1", "wn": "1", "nombre": "Hub ON / WN ON"},
}


def audit_caso(tid, query, gold, cat, configs_to_run=None):
    from core.memory_store import SQLiteMemoryBioRAG

    if configs_to_run is None:
        configs_to_run = list(CONFIGS.keys())

    print(f"\n{'='*80}")
    print(f"CASO {tid} | {cat} | Query: '{query}' | Gold: {gold}")
    print('='*80)

    # 1. Normalización
    frase_limpia = get_frase_limpia(query)
    print(f"\n[PASO 1] Normalización:")
    print(f"  query original     : '{query}'")
    print(f"  frase_limpia       : '{frase_limpia}'")

    # 2. Probe FTS AND (independiente de Hub/WN)
    conn_probe = sqlite3.connect(DB_SNAPSHOT)
    cnt_and, fts_expr = probe_fts_and(conn_probe, frase_limpia)
    conn_probe.close()
    necesita_expansion = (cnt_and == 0)
    print(f"\n[PASO 2] FTS AND Probe:")
    print(f"  expresión FTS5     : {fts_expr}")
    print(f"  hits FTS AND       : {cnt_and}")
    print(f"  _necesita_expansion: {necesita_expansion}")

    # 3. Expansión WordNet (aplicable solo si necesita_expansion=True)
    wn_terms, wn_report = probe_wordnet_expansion(frase_limpia)
    print(f"\n[PASO 3] Análisis WordNet (se invocaría si _necesita_expansion=True):")
    for line in wn_report:
        print(line)
    if wn_terms:
        print(f"  → Términos que se añadirían a frase: {wn_terms}")
    else:
        print(f"  → Sin términos WordNet añadidos.")

    # 4. Por cada configuración: Hub trace + búsqueda real
    for cfg_id in configs_to_run:
        cfg = CONFIGS[cfg_id]
        os.environ["BIORAG_HUB_ENABLED"] = cfg["hub"]
        os.environ["BIORAG_WORDNET_ENABLED"] = cfg["wn"]
        os.environ["BIORAG_NO_LOG"] = "1"
        os.environ["BIORAG_ORDEN_MONOTONICO"] = "1"

        _hub_trace.clear()
        original_fn = patch_concept_hub()
        try:
            cerebro = SQLiteMemoryBioRAG(db_path=DB_SNAPSHOT)
            if cat == "dormido" and gold:
                cerebro.cursor.execute(
                    "UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (gold,))
            elif gold:
                cerebro.cursor.execute(
                    "UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (gold,))

            profundidad = "profundo" if cat in ("dormido", "negativo") else "activos"
            results, total = cerebro.buscar_por_frase(
                query, profundidad=profundidad, limite=10, ignore_peso_sinaptico=True
            )
            cerebro.conn.close()
        except Exception as e:
            restore_concept_hub(original_fn)
            print(f"\n[{cfg_id}] ERROR: {e}")
            continue
        finally:
            restore_concept_hub(original_fn)

        print(f"\n[{cfg_id}] {cfg['nombre']}")
        print(f"  --- Hub trace ---")
        if _hub_trace.get('result') is not None:
            hub_res = _hub_trace['result']
            print(f"  expandir_query_con_hub recibió frase_limpia: '{_hub_trace.get('frase_limpia')}'")
            print(f"  hub_confidence  : {hub_res.get('hub_confidence', 'N/A')}")
            print(f"  canonical_nodes : {hub_res.get('canonical_nodes', [])}")
            print(f"  expanded_terms  : {hub_res.get('expanded_terms', [])}")
            # Determinar ruta activa
            hub_conf = hub_res.get('hub_confidence', 0)
            canonical_nodes = hub_res.get('canonical_nodes', [])
            exp_terms = hub_res.get('expanded_terms', [])
            if exp_terms and necesita_expansion:
                print(f"  → RUTA A ACTIVA: expansión léxica pre-FTS inyectada")
            elif not exp_terms and not necesita_expansion:
                print(f"  → RUTA A INACTIVA: _necesita_expansion=False")
            if hub_conf >= 0.4 and canonical_nodes:
                gold_list = [gold] if isinstance(gold, str) else gold
                for gn in gold_list:
                    if gn in canonical_nodes:
                        print(f"  → RUTA B ACTIVA: gold '{gn}' es canonical_node (confianza={hub_conf:.3f})")
                    else:
                        print(f"  → RUTA B: gold '{gn}' NO es canonical_node")
            elif hub_conf < 0.4:
                print(f"  → RUTA B INACTIVA: hub_confidence {hub_conf:.3f} < 0.4")
            if canonical_nodes and hub_conf >= 0.4:
                print(f"  → RUTA C: canonical bypass QCR para {canonical_nodes}")
        else:
            if cfg["hub"] == "0":
                print(f"  Hub desactivado (BIORAG_HUB_ENABLED=0)")
            else:
                print(f"  expandir_query_con_hub devolvió None (sin match en DB)")

        print(f"  --- Resultados (Top-10) ---")
        cands = [r[0] for r in results]
        scores = [round(r[4], 4) for r in results]
        gold_pos = -1
        gold_score = -1
        for idx, (cand, sc) in enumerate(zip(cands, scores)):
            gold_list = [gold] if isinstance(gold, str) else gold
            marker = " ← GOLD" if cand in gold_list else ""
            print(f"  [{idx+1}] {cand} ({sc}){marker}")
            if cand in gold_list and gold_pos == -1:
                gold_pos = idx + 1
                gold_score = sc
        if gold_pos == -1:
            # Check if gold even appears beyond top-10
            for idx, (cand, sc) in enumerate(zip(cands, scores)):
                pass
            print(f"  Gold '{gold}': NO EN TOP-10 (fallo)")
        else:
            print(f"  → Gold '{gold}' en posición {gold_pos} con score {gold_score}")


# ──────────────────────────────────────────────────────────────────────────────
# Taxonomía detallada de los 24 fallos de Run A
# ──────────────────────────────────────────────────────────────────────────────
def taxonomia_fallos():
    """
    Clasifica los 24 fallos de Run A por tipo de limitación real del pipeline,
    no solo por apariencia lingüística.
    """
    import json
    fallos_path = "docs/casos_fallidos_ablation_A.jsonl"
    if not os.path.exists(fallos_path):
        print("No existe docs/casos_fallidos_ablation_A.jsonl")
        return

    with open(fallos_path) as f:
        fallos = [json.loads(line) for line in f if line.strip()]

    # Cargar casos completos para obtener deep/notas
    with open("scripts/casos_qa_baseline_v1.jsonl") as f:
        casos_full = {json.loads(line)["id"]: json.loads(line)
                      for line in f if line.strip()}

    print(f"\n{'='*80}")
    print("TAXONOMÍA CAUSAL DE LOS 24 FALLOS RESIDUALES — Run A (v30.2 baseline)")
    print('='*80)
    print(f"{'ID':<6} {'Cat':<22} {'Tipo Limitación':<32} {'Diagnóstico'}")
    print('-'*120)

    for fa in fallos:
        fid = fa["id"]
        q = fa["query"]
        gold = fa.get("expected") or fa.get("concepto_esperado", "")
        cat = fa.get("categoria", "")
        ret = fa.get("returned", [])
        sc = fa.get("scores", [])

        # Determinar tipo de limitación causal
        q_lower = q.lower()
        q_tokens = q_lower.split()
        n_tokens = len(q_tokens)
        gold_str = gold if isinstance(gold, str) else str(gold)

        if cat == "ambiguo":
            tipo = "ambiguedad_gold"
            diag = "Gold contradictorio en el dataset (2 conceptos mutuamente excluyentes)"
        elif cat == "cruce_idioma":
            tipo = "multilingue_sin_traduccion"
            diag = f"Token inglés ('{q}') sin bridge de traducción ni WordNet coverage suficiente"
        elif n_tokens == 1:
            # Determinar si el top devuelto tiene el gold con score cercano
            if sc and sc[0] > 0.70:
                tipo = "desambiguacion_polisemica"
                diag = f"1 token ultra-polisémico: corpus devuelve {sc[0]:.3f} para '{ret[0] if ret else '?'}'. Sin contexto adicional es irresoluble por expansión léxica"
            else:
                tipo = "representacion_ausente"
                diag = f"1 token con score bajo: la relación semántica entre '{q}' y '{gold_str}' no está representada léxicamente"
        elif cat == "sinonimo":
            if sc and sc[0] > 0.65:
                tipo = "desambiguacion_sinonim_compet"
                diag = f"Hay un candidato competidor '{ret[0] if ret else '?'}' ({sc[0]:.3f}) que domina el score. Gold requiere contexto de intención"
            else:
                tipo = "gap_semantico_sinonimo"
                diag = f"El sinónimo implícito entre '{q}' y '{gold_str}' no está cubierto por FTS/PPMI/WordNet"
        elif cat in ("variante_gramatical", "typo"):
            tipo = "corrupcion_morfologica_extrema"
            diag = f"Corrupción de tokens estructurales (sufijos/plurales compuestos) que impiden match FTS AND. FP de cobertura léxica"
        elif cat == "por_tema":
            if len(q_tokens) <= 3:
                tipo = "brecha_asociativa_abstracta"
                diag = f"Query de {n_tokens} tokens con relación puramente conceptual al gold. Sin covarianza léxica directa"
            else:
                tipo = "gap_semantico_por_tema"
                diag = f"Múltiples tokens pero relación semántica indirecta con '{gold_str}'. El pooling léxico no captura la intención temática"
        else:
            tipo = "sin_clasificar"
            diag = f"Categoría '{cat}' con análisis pendiente"

        print(f"{fid:<6} {cat:<22} {tipo:<32} {diag[:70]}")
        print(f"       Query: '{q[:60]}' → Gold: '{gold_str[:50]}'")
        sc0 = sc[0] if sc else 0.0
        print(f"       Top devuelto: {ret[0] if ret else 'vacío'} ({sc0:.3f})")
        print()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("AUDITORÍA CAUSAL INSTRUMENTADA — 4 CASOS ABLACIÓN (Aureon Protocol)")
    print(f"DB: {DB_SNAPSHOT}\n")

    CASOS = {
        "0513": {
            "query": "denys-identidad-profunda",
            "gold": "dennys-identidad-profunda",
            "cat": "typo",
            "configs": ["D", "C"],  # Solo los que cambian entre sí
        },
        "0848": {
            "query": "semánticas 849 embedding",
            "gold": "v13_2_limpieza_tabla_semantica",
            "cat": "por_tema",
            "configs": ["D", "B"],  # WN es el único factor
        },
        "0763": {
            "query": "aprendizaje",
            "gold": "fin-aprendizaje-creerse-completo",
            "cat": "sinonimo",
            "configs": ["D", "C", "B", "A"],  # Todos para ver desplazamiento
        },
        "0744": {
            "query": "biorags v16s 0s estadando",
            "gold": "biorag_v16_0_estado",
            "cat": "variante_gramatical",
            "configs": ["D", "C", "B", "A"],
        },
    }

    for tid, info in CASOS.items():
        audit_caso(
            tid=tid,
            query=info["query"],
            gold=info["gold"],
            cat=info["cat"],
            configs_to_run=info["configs"],
        )

    taxonomia_fallos()
