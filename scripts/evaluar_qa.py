import sys
import os
import json
import re
import shutil
import sqlite3
import time
import unicodedata
import difflib
from collections import defaultdict

# Add workspace root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG


def _normalizar_token(texto):
    """Normaliza texto para matching de tokens: sin acentos, minúsculas."""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(c)
    ).lower()


def _clave_etiqueta(texto):
    """Clave comparativa de etiqueta oro: sin acentos, minúsculas, solo alfanuméricos.

    Permite resolver etiquetas obsoletas del JSONL cuando un nodo fue renombrado con
    cambios de puntuación (coma -> "_y_", dos puntos, guiones). Los 3 fallos de la
    categoría `literal` del 2026-09-02 eran exactamente esto: el motor devolvía el nodo
    correcto en TOP1 con score 0.935 y el caso se contaba como fallo porque la etiqueta
    apuntaba al nombre viejo, ya inexistente en la DB.
    """
    return re.sub(r'[^a-z0-9]+', '', _normalizar_token(texto))


def _restaurar_estado_nodos(db, estado_inicial):
    """Restaura `estado` y `peso_sinaptico` de los nodos que el caso anterior modificó.

    Por qué hace falta (hallazgo del 2026-09-02, diagnóstico §4.3):
    el arnés muta la DB caso a caso y esas mutaciones se ACUMULAN:

      - el setup hace `UPDATE largo_plazo SET estado='activo'/'dormido'` sobre el nodo
        esperado de cada caso;
      - `buscar_por_frase(profundidad='profundo')` DESPIERTA nodos dormidos
        (`estado='activo'`, `peso_sinaptico += 0.15`) dentro del motor
        (core/memory_store.py, bloque de paginación profunda).

    Consecuencia: el resultado del caso N depende de los N-1 casos anteriores. En la
    DB viva hay 66 nodos `dormido` y 46 de los 921 casos tienen su nodo esperado en
    ese estado, así que buena parte del corpus se va reactivando de forma irreversible
    a medida que avanza la corrida y el pool de candidatos crece.

    Efecto medido: el caso `typo` 0513 ('denys-identidad-profunda') pasó de PASS a
    FAIL entre dos corridas del MISMO código porque su nodo esperado puntúa 0.1743,
    empatado con otro candidato y justo en el corte del top-5; cualquier cambio de
    estado aguas arriba lo deja dentro o fuera. Eso es ruido del arnés, no señal del
    motor, y con ruido de ±1-2 casos no se puede validar ningún fix.

    El restaurador hace la evaluación independiente del orden: cada caso arranca desde
    el mismo estado de corpus. Coste: un SELECT de ~1k filas + updates puntuales por
    caso, despreciable frente a ~1 s de búsqueda.
    """
    actual = db.cursor.execute(
        "SELECT concepto, estado, peso_sinaptico FROM largo_plazo"
    ).fetchall()
    cambias = []
    for concepto, estado, peso in actual:
        original = estado_inicial.get(concepto)
        if original and (original[0] != estado or original[1] != peso):
            cambias.append((original[0], original[1], concepto))
    if not cambias:
        return 0
    db.cursor.executemany(
        "UPDATE largo_plazo SET estado = ?, peso_sinaptico = ? WHERE concepto = ?",
        cambias,
    )
    db.conn.commit()
    return len(cambias)


def _tokens_corpus(db):
    """Tokens (>=3 chars, normalizados) presentes en el corpus completo.

    Se usa para detectar controles negativos contaminados: si un token de la
    query aparece como palabra en el corpus (concepto + contenido + sinónimos),
    la query dejó de ser "ruido" y pasó a ser una coincidencia léxica legítima.
    Esos controles no miden el gate de ruido y se reportan aparte.
    """
    tokens = set()
    db.cursor.execute(
        "SELECT concepto, COALESCE(contenido, ''), COALESCE(sinonimos, '') FROM largo_plazo"
    )
    for concepto, contenido, sinonimos in db.cursor.fetchall():
        texto = f"{concepto} {contenido} {sinonimos}".replace('_', ' ').replace('-', ' ')
        for w in re.findall(r'\w{3,}', _normalizar_token(texto)):
            tokens.add(w)
    return tokens


def run_evaluation():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Cargar .env.local automáticamente si existe
    env_local = os.path.join(base_dir, ".env.local")
    if os.path.exists(env_local):
        with open(env_local, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    # No contaminar log_busquedas con consultas del benchmark
    os.environ["BIORAG_NO_LOG"] = "1"

    src_db = os.environ.get('BIORAG_PATH') or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")

    temp_db = os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag_qa_temp.db")
    cases_filename = sys.argv[1] if len(sys.argv) > 1 else "casos_qa_baseline_v1.jsonl"
    cases_file = os.path.join(base_dir, "scripts", cases_filename)
    failed_file = os.path.join(base_dir, "scripts", "casos_fallidos.jsonl")
    
    if not os.path.exists(cases_file):
        print(f"Error: Test cases file not found at {cases_file}.")
        sys.exit(1)
        
    print(f"Creating isolated database copy at: {temp_db}")
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
    conn_src = sqlite3.connect(src_db)
    conn_src.execute("PRAGMA wal_checkpoint(FULL);")
    conn_dst = sqlite3.connect(temp_db)
    conn_src.backup(conn_dst)
    conn_dst.close()
    conn_src.close()


    
    # Load cases
    cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
                
    print(f"Loaded {len(cases)} test cases.")
    
    # Initialize BioRAG against the temp DB copy
    db = SQLiteMemoryBioRAG(db_path=temp_db)

    # Tokens del corpus para detectar controles negativos contaminados
    # (autorreferencia: el corpus documenta las mismas queries negativas).
    corpus_tokens = _tokens_corpus(db)

    # ── Resolución de etiquetas oro contra la DB evaluada ──────────────────
    # El JSONL se genera contra una DB concreta; si después un nodo se renombra, la
    # etiqueta queda obsoleta y el caso se vuelve IMPOSIBLE (falla aunque el motor
    # acierte). Se resuelve aquí, en tiempo de evaluación y contra la copia que se está
    # midiendo, para que el dataset no se rompa con cada rename.
    # Desactivable: export BIORAG_QA_RESOLVER_ETIQUETAS=0
    RESOLVER_ETIQUETAS = os.environ.get("BIORAG_QA_RESOLVER_ETIQUETAS", "1") == "1"
    clave_a_conceptos = defaultdict(list)
    for (_conc,) in db.cursor.execute("SELECT concepto FROM largo_plazo").fetchall():
        if _conc:
            clave_a_conceptos[_clave_etiqueta(_conc)].append(_conc)

    # Nivel difuso: los renames reales del corpus no son solo de puntuación. Los 3
    # casos del 2026-09-02 fueron coma -> "_y_" (se AÑADIÓ el token "y"), así que la
    # clave normalizada no coincide:
    #   viejo  lección:_guardar_todo_lo_importante_inmediatamente,_no_esperar
    #   actual lección:_guardar_todo_lo_importante_inmediatamente_y_no_esperar
    # Por eso existe este segundo nivel, acotado por dos guardas: ratio >= umbral y
    # separación clara sobre el segundo mejor candidato. Si no se cumplen ambas, la
    # etiqueta se reporta como irreparable en vez de adivinar (un gold erróneo es peor
    # que un fallo visible).
    UMBRAL_DIFUSO = float(os.environ.get("BIORAG_QA_ETIQUETA_DIFUSA", "0.94"))
    MARGEN_DIFUSO = float(os.environ.get("BIORAG_QA_ETIQUETA_MARGEN", "0.02"))

    def _resolver_etiqueta(esperado):
        """Devuelve (concepto_resuelto, motivo) para una etiqueta oro."""
        if not esperado:
            return esperado, ""
        row = db.cursor.execute(
            "SELECT concepto FROM largo_plazo WHERE concepto = ?", (esperado,)
        ).fetchone()
        if row:
            return esperado, ""

        clave = _clave_etiqueta(esperado)

        # Nivel 1: coincidencia exacta ignorando puntuación y acentos
        candidatos = clave_a_conceptos.get(clave, [])
        if len(candidatos) == 1:
            return candidatos[0], "obsoleta_resuelta"
        if len(candidatos) > 1:
            return esperado, "obsoleta_ambigua"

        # Nivel 2: coincidencia difusa sobre la clave normalizada
        cercanos = difflib.get_close_matches(clave, list(clave_a_conceptos.keys()), n=3, cutoff=0.80)
        if not cercanos:
            return esperado, "inexistente"
        mejor_clave = cercanos[0]
        ratio = difflib.SequenceMatcher(None, clave, mejor_clave).ratio()
        segundo = (
            difflib.SequenceMatcher(None, clave, cercanos[1]).ratio()
            if len(cercanos) > 1 else 0.0
        )
        opciones = clave_a_conceptos[mejor_clave]
        if ratio < UMBRAL_DIFUSO:
            return esperado, f"inexistente (mejor candidato difuso {ratio:.3f} < {UMBRAL_DIFUSO})"
        if (ratio - segundo) < MARGEN_DIFUSO:
            return esperado, f"obsoleta_ambigua_difusa ({ratio:.3f} vs {segundo:.3f})"
        if len(opciones) > 1:
            return esperado, "obsoleta_ambigua"
        return opciones[0], "obsoleta_resuelta_difusa"

    etiquetas_obsoletas = []   # (id, etiqueta_jsonl, concepto_real)
    etiquetas_irreparables = []  # (id, etiqueta_jsonl, motivo)

    # ── Queries con etiqueta oro contradictoria ────────────────────────────
    # Misma query con >= 2 esperados distintos: un motor determinista no puede acertar
    # ambas, así que esos casos no miden el motor, miden el ruido del dataset. Se sacan
    # del Recall global y se reportan aparte como categoría `ambiguo` (igual que
    # `negativo`). En el dataset 2026-09-02: 'dimensiones', 'compromiso', 'biorag'.
    golds_por_query = defaultdict(set)
    for _c in cases:
        if _c.get("concepto_esperado"):
            golds_por_query[_c["query"].strip().lower()].add(_c["concepto_esperado"])
    queries_ambiguas = {q for q, g in golds_por_query.items() if len(g) > 1}

    # Stats tracking
    stats = defaultdict(lambda: {"total": 0, "hits_at_5": 0, "hits_at_1": 0, "reciprocal_rank_sum": 0, "false_positives": 0, "contaminados": 0, "cubiertos": 0})
    failures_by_category = defaultdict(list)
    spreading_activation_count = 0  # Contador de queries que activan spreading activation
    
    start_time = time.time()

    # Snapshot del estado del corpus para poder restaurarlo entre casos (ver
    # _restaurar_estado_nodos). Sin esto la evaluación no es reproducible: cada caso
    # hereda las reactivaciones y subidas de peso_sinaptico de los casos anteriores.
    estado_inicial_nodos = {
        r[0]: (r[1], r[2])
        for r in db.cursor.execute(
            "SELECT concepto, estado, peso_sinaptico FROM largo_plazo"
        ).fetchall()
    }
    nodos_restaurados_total = 0
    nodos_dormidos_iniciales = sum(
        1 for _e, _p in estado_inicial_nodos.values() if _e == "dormido"
    )

    for case in cases:
        case_id = case["id"]
        category = case["categoria"]
        query = case["query"]
        expected = case["concepto_esperado"]
        deep = case.get("deep", False)

        # Etiqueta obsoleta -> resolver contra la DB evaluada
        if RESOLVER_ETIQUETAS and expected:
            esperado_resuelto, motivo_etiqueta = _resolver_etiqueta(expected)
            if motivo_etiqueta.startswith("obsoleta_resuelta"):
                etiquetas_obsoletas.append((case_id, expected, esperado_resuelto))
                expected = esperado_resuelto
            elif motivo_etiqueta:
                etiquetas_irreparables.append((case_id, expected, motivo_etiqueta))

        # Query contradictoria -> fuera del recall global
        if expected and query.strip().lower() in queries_ambiguas:
            golds = sorted(golds_por_query[query.strip().lower()])
            stats["ambiguo"]["total"] += 1
            _res, _tot = db.buscar_por_frase(
                query, profundidad="activos", limite=5, ignore_peso_sinaptico=True
            )
            _devueltos = [r[0] for r in _res]
            _cubierto = [g for g in golds if g in _devueltos]
            if _cubierto:
                stats["ambiguo"]["cubiertos"] += 1
            else:
                failures_by_category["ambiguo"].append({
                    "id": case_id,
                    "query": query,
                    "expected": golds,
                    "returned": _devueltos[:3],
                    "scores": [r[4] for r in _res][:3],
                    "error": "Query ambigua: ninguno de los esperados contradictorios apareció en top 5",
                })
            nodos_restaurados_total += _restaurar_estado_nodos(db, estado_inicial_nodos)
            continue

        stats[category]["total"] += 1
        
        # 1. Setup phase: only set active/dormant state for target concept (weights are 1.00 for ALL nodes globally)
        if category == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()
            
        # 2. Execute query
        profundidad = "profundo" if (deep or category == "dormido" or category == "negativo") else "activos"
        results, total = db.buscar_por_frase(query, profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        
        # Track spreading activation usage
        if hasattr(db, 'last_parent_map') and db.last_parent_map:
            spreading_activation_count += 1
        
        # Extract returned concepts
        returned = [r[0] for r in results]
        scores = [r[4] for r in results]
        
        # 3. Evaluation phase
        if expected is None:
            # Negative control case: check if we retrieved any matches with high score
            # DEUDA TÉCNICA CONOCIDA: evaluar_qa.py evalúa FP con el corte estático BIORAG_FP_THRESHOLD=0.25
            # y no consulta la tabla calibracion_estado ni pasa por _debe_responder() / nivel_certeza() de
            # biorag_recordar(). Para validar el umbral conforme empírico (ej. 0.5233) en producción,
            # se requiere una suite dedicada que evalúe el pipeline de producción MCP.
            # Noise threshold: configurable via BIORAG_FP_THRESHOLD (default 0.25)
            fp_threshold = float(os.environ.get('BIORAG_FP_THRESHOLD', '0.25'))

            # Detección de control contaminado: si algún token de la query ya
            # existe como palabra en el corpus, el control dejó de ser "negativo"
            # (el motor lo recupera correctamente y no es un fallo del gate).
            q_tokens = [t for t in re.findall(r'\w{3,}', _normalizar_token(query))]
            contaminados = [t for t in q_tokens if t in corpus_tokens]
            if contaminados:
                stats[category]["contaminados"] += 1
                failures_by_category[category].append({
                    "id": case_id,
                    "query": query,
                    "expected": None,
                    "returned": returned[:3],
                    "scores": scores[:3],
                    "contaminado": True,
                    "error": f"Control negativo contaminado (tokens en corpus: {', '.join(sorted(set(contaminados)))}) — no es un FP del gate"
                })
            else:
                fps = [r for r in results if r[4] >= fp_threshold]
                if len(fps) > 0:
                    stats[category]["false_positives"] += 1
                    failures_by_category[category].append({
                        "id": case_id,
                        "query": query,
                        "expected": None,
                        "returned": returned[:3],
                        "scores": scores[:3],
                        "error": f"False positive returned with score {scores[0]}"
                    })
        else:
            # Normal or awakening case
            found_at = -1
            for idx, concept in enumerate(returned):
                if concept == expected:
                    found_at = idx + 1
                    break
                    
            if found_at != -1:
                stats[category]["hits_at_5"] += 1
                stats[category]["reciprocal_rank_sum"] += 1.0 / found_at
                if found_at == 1:
                    stats[category]["hits_at_1"] += 1
                    
                # Extra validation for dormant nodes: check if the state was updated to 'activo'
                if category == "dormido":
                    db.cursor.execute("SELECT estado FROM largo_plazo WHERE concepto = ?", (expected,))
                    row = db.cursor.fetchone()
                    if not row or row[0] != "activo":
                        failures_by_category[category].append({
                            "id": case_id,
                            "query": query,
                            "expected": expected,
                            "returned": returned[:3],
                            "scores": scores[:3],
                            "error": f"Node found but remained dormant (state is {row[0] if row else 'None'})"
                        })
                        # Revert stats change since awakening failed
                        stats[category]["hits_at_5"] -= 1
                        if found_at == 1:
                            stats[category]["hits_at_1"] -= 1
                        stats[category]["reciprocal_rank_sum"] -= 1.0 / found_at
            else:
                failures_by_category[category].append({
                    "id": case_id,
                    "query": query,
                    "expected": expected,
                    "returned": returned[:3],
                    "scores": scores[:3],
                    "error": "Expected concept not found in top 5 results"
                })

        # Aislar el caso siguiente del estado que este caso dejó en la DB
        nodos_restaurados_total += _restaurar_estado_nodos(db, estado_inicial_nodos)

    elapsed_time = time.time() - start_time
    db.conn.close()
    
    # Export failed cases to JSONL
    print(f"\nExporting failed cases to: {failed_file}")
    with open(failed_file, "w", encoding="utf-8") as f:
        for cat, fails in failures_by_category.items():
            for fail in fails:
                fail_record = {"categoria": cat, **fail}
                f.write(json.dumps(fail_record, ensure_ascii=False) + "\n")
                
    # Cleanup temp database
    print(f"Cleaning up temporary database copy at {temp_db}...")
    if os.path.exists(temp_db):
        os.remove(temp_db)
        
    # Generate report
    print("\n" + "="*80)
    print("                      BIORAG QA EVALUATION REPORT")
    print("="*80)
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
    print("-"*80)
    print(f"{'Category':<22} | {'Total':<6} | {'Recall@5':<9} | {'Recall@1':<9} | {'MRR':<8} | {'Errors/FPs':<10}")
    print("-"*80)
    
    total_queries = 0
    total_hits_at_5 = 0
    total_hits_at_1 = 0
    total_mrr_sum = 0
    total_negatives = 0
    total_false_positives = 0
    total_contaminados = 0
    
    for cat in sorted(stats.keys()):
        stat = stats[cat]
        cnt = stat["total"]
        if cat == "ambiguo":
            cobertura = (stat.get("cubiertos", 0) / cnt * 100) if cnt else 0.0
            print(f"{cat:<22} | {cnt:<6} | {'N/A':<9} | {'N/A':<9} | {'N/A':<8} | {len(failures_by_category[cat]):<10} ({cobertura:.1f}% de cobertura sobre queries con etiqueta contradictoria; fuera del Recall global)")
            continue
        if cat == "negativo":
            total_negatives += cnt
            total_false_positives += stat["false_positives"]
            total_contaminados += stat.get("contaminados", 0)
            validos = cnt - stat.get("contaminados", 0)
            fp_rate = (stat["false_positives"] / validos) * 100 if validos > 0 else 0.0
            print(f"{cat:<22} | {cnt:<6} | {'N/A':<9} | {'N/A':<9} | {'N/A':<8} | {stat['false_positives']:<10} ({fp_rate:.1f}% FP sobre {validos} válidos; {stat.get('contaminados', 0)} contaminados)")
        else:
            total_queries += cnt
            total_hits_at_5 += stat["hits_at_5"]
            total_hits_at_1 += stat["hits_at_1"]
            total_mrr_sum += stat["reciprocal_rank_sum"]
            
            recall_5 = (stat["hits_at_5"] / cnt) * 100 if cnt > 0 else 0
            recall_1 = (stat["hits_at_1"] / cnt) * 100 if cnt > 0 else 0
            mrr = stat["reciprocal_rank_sum"] / cnt if cnt > 0 else 0
            num_failures = cnt - stat["hits_at_5"] if cat != "dormido" else len(failures_by_category[cat])
            print(f"{cat:<22} | {cnt:<6} | {recall_5:>7.2f}% | {recall_1:>7.2f}% | {mrr:>6.3f} | {num_failures:<10}")
            
    print("-"*80)
    global_recall_5 = (total_hits_at_5 / total_queries) * 100 if total_queries > 0 else 0
    global_recall_1 = (total_hits_at_1 / total_queries) * 100 if total_queries > 0 else 0
    global_mrr = total_mrr_sum / total_queries if total_queries > 0 else 0
    global_validos = total_negatives - total_contaminados
    global_fp_rate = (total_false_positives / global_validos) * 100 if global_validos > 0 else 0.0
    
    print(f"{'GLOBAL SUMMARY (Retrieval)':<22} | {total_queries:<6} | {global_recall_5:>7.2f}% | {global_recall_1:>7.2f}% | {global_mrr:>6.3f} | {total_queries - total_hits_at_5:<10}")
    print(f"{'GLOBAL SUMMARY (Noise/FP)':<22} | {total_negatives:<6} | {'N/A':<9} | {'N/A':<9} | {'N/A':<8} | {total_false_positives:<10} ({global_fp_rate:.2f}% FP sobre {global_validos} válidos; {total_contaminados} contaminados)")
    print(f"{'SPREADING ACTIVATION':<22} | {spreading_activation_count}/{len(cases)} queries ({spreading_activation_count/len(cases)*100:.1f}%)")
    print(f"{'AISLAMIENTO POR CASO':<22} | {nodos_restaurados_total} mutaciones de estado revertidas "
          f"({nodos_dormidos_iniciales} nodos arrancaron dormidos)")
    print("="*80)

    # ── Salud del dataset: etiquetas que el evaluador tuvo que reparar ──────
    if etiquetas_obsoletas or etiquetas_irreparables or queries_ambiguas:
        print("\nDATASET (salud de las etiquetas oro):")
        print("-"*80)
        if etiquetas_obsoletas:
            print(f"  {len(etiquetas_obsoletas)} etiqueta(s) obsoleta(s) resuelta(s) contra la DB:")
            for _id, _vieja, _nueva in etiquetas_obsoletas:
                print(f"    [{_id}] {_vieja}\n         -> {_nueva}")
        if etiquetas_irreparables:
            print(f"  {len(etiquetas_irreparables)} etiqueta(s) NO resoluble(s) (el nodo no existe en la DB evaluada):")
            for _id, _etq, _mot in etiquetas_irreparables:
                print(f"    [{_id}] {_etq}  ({_mot})")
        if queries_ambiguas:
            print(f"  {len(queries_ambiguas)} query(s) con etiqueta contradictoria -> reclasificadas como 'ambiguo':")
            for _q in sorted(queries_ambiguas):
                print(f"    {_q!r} -> {sorted(golds_por_query[_q])}")
        print("-"*80)
    
    # Output detailed failures per category (up to 3 cases per category)
    if len(failures_by_category) > 0:
        print("\nSAMPLE FAILURES BY CATEGORY FOR ACTIONABLE DIAGNOSIS:")
        print("="*80)
        for cat in sorted(failures_by_category.keys()):
            fails = failures_by_category[cat]
            print(f"\n[Category: {cat}] ({len(fails)} total failures)")
            print("-" * 40)
            for idx, fail in enumerate(fails[:3]):
                print(f"  #{idx+1} [ID {fail['id']}] Query: \"{fail['query']}\"")
                print(f"      Expected:  {fail['expected']}")
                print(f"      Returned:  {fail['returned']} (scores: {[round(s, 3) for s in fail['scores']]})")
                print(f"      Reason:    {fail['error']}")
        print("="*80)
        print(f"Note: All failed cases have been saved to {failed_file} for full debug analysis.")
    else:
        print("\nAmazing! Zero failures detected across all test categories.")
        print("="*80)

    # ── Métricas machine-readable + gate de regresión ──────────────────────
    # Hasta v30.0 la suite solo emitía texto: comparar dos corridas obligaba a hacer
    # grep del informe, y evaluar_qa.py terminaba SIEMPRE en 0. Con `set -e` en
    # run_qa_suite.sh eso significa que la suite no podía fallar: el 2026-09-02 el
    # Recall@5 global cayó 97.39% -> 95.23% (+19 fallos) y el wrapper imprimió
    # "SUITE DE EVALUACIÓN BIORAG FINALIZADA CON ÉXITO".
    #
    # qa_metrics.json deja las cifras listas para diff/CI, y el gate convierte una
    # regresión en exit code distinto de cero.
    metrics_file = os.environ.get(
        "BIORAG_QA_METRICS", os.path.join(base_dir, "scripts", "qa_metrics.json")
    )
    global_fallos = total_queries - total_hits_at_5
    metrics = {
        "version": "v30.1",
        "generado_en": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(elapsed_time, 2),
        "casos_file": cases_filename,
        "casos_total": len(cases),
        "db_src": src_db,
        "global": {
            "queries": total_queries,
            "recall_at_5": round(global_recall_5, 2),
            "recall_at_1": round(global_recall_1, 2),
            "mrr": round(global_mrr, 4),
            "fallos": global_fallos,
            "negativos_total": total_negatives,
            "negativos_fp": total_false_positives,
            "negativos_fp_rate": round(global_fp_rate, 2),
            "negativos_contaminados": total_contaminados,
            "spreading_activation": spreading_activation_count,
            "etiquetas_obsoletas_resueltas": len(etiquetas_obsoletas),
            "etiquetas_irreparables": len(etiquetas_irreparables),
            "queries_ambiguas": len(queries_ambiguas),
            "nodos_dormidos_iniciales": nodos_dormidos_iniciales,
            "nodos_restaurados_entre_casos": nodos_restaurados_total,
        },
        "categorias": {
            cat: {
                "total": st["total"],
                "recall_at_5": round((st["hits_at_5"] / st["total"] * 100) if st["total"] else 0.0, 2),
                "recall_at_1": round((st["hits_at_1"] / st["total"] * 100) if st["total"] else 0.0, 2),
                "mrr": round((st["reciprocal_rank_sum"] / st["total"]) if st["total"] else 0.0, 4),
                "fallos": (st["total"] - st["hits_at_5"]) if cat != "dormido" else len(failures_by_category[cat]),
            }
            for cat, st in sorted(stats.items())
            if cat not in ("negativo", "ambiguo") and st["total"]
        },
    }
    metrics["global"]["orden_no_monotonico"] = sum(
        1
        for _f in (f for _fs in failures_by_category.values() for f in _fs)
        if _f.get("scores")
        and any(_f["scores"][i] < _f["scores"][i + 1] for i in range(len(_f["scores"]) - 1))
    )
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"\nMétricas exportadas a: {metrics_file}")

    gate_ok, gate_reasons = _evaluar_gate(metrics, base_dir)
    return metrics, gate_ok, gate_reasons


def _evaluar_gate(metrics, base_dir):
    """Compara las métricas de la corrida contra los umbrales del gate de regresión.

    Defaults = la BASELINE OFICIAL 2026-09-05 (Recall@5 97.26%, 24 fallos) — v30.2
    implementación B2+B3 Quality Gate. Mejor que todos los estados anteriores en R@5,
    R@1 y MRR con 0 FP. Para una corrida exploratoria
    (ablaciones, experimentos) se desactiva con BIORAG_QA_GATE=0.

    Variables:
      BIORAG_QA_GATE=1|0            activa/apaga el gate (default 1)
      BIORAG_QA_MIN_RECALL5=97.0    Recall@5 global mínimo, en %
      BIORAG_QA_MAX_FALLOS=24       máximo de fallos de recuperación
      BIORAG_QA_MAX_FP_RATE=0.0     máximo % de falsos positivos sobre negativos válidos
      BIORAG_QA_MAX_REGRESION_PP=2.0  caída máxima por categoría vs. baseline, en pp
      BIORAG_QA_BASELINE=qa_metrics_baseline.json  baseline en scripts/ (si no existe,
                                      solo se avisa; no se compara por categoría)
    """
    if os.environ.get("BIORAG_QA_GATE", "1") != "1":
        return True, ["gate desactivado (BIORAG_QA_GATE=0)"]

    g = metrics["global"]
    min_recall5 = float(os.environ.get("BIORAG_QA_MIN_RECALL5", "97.0"))
    max_fallos = int(os.environ.get("BIORAG_QA_MAX_FALLOS", "24"))
    max_fp = float(os.environ.get("BIORAG_QA_MAX_FP_RATE", "0.0"))
    max_regresion = float(os.environ.get("BIORAG_QA_MAX_REGRESION_PP", "2.0"))

    reasons = []
    if g["recall_at_5"] < min_recall5:
        reasons.append(
            f"Recall@5 global {g['recall_at_5']:.2f}% < mínimo {min_recall5:.2f}%"
        )
    if g["fallos"] > max_fallos:
        reasons.append(f"{g['fallos']} fallos > máximo {max_fallos}")
    if g["negativos_fp_rate"] > max_fp:
        reasons.append(
            f"FP {g['negativos_fp_rate']:.2f}% > máximo {max_fp:.2f}% "
            f"({g['negativos_fp']}/{g['negativos_total'] - g['negativos_contaminados']} negativos válidos)"
        )

    baseline_name = os.environ.get("BIORAG_QA_BASELINE", "qa_metrics_baseline.json")
    baseline_path = os.path.join(base_dir, "scripts", baseline_name)
    if os.path.exists(baseline_path):
        try:
            with open(baseline_path, encoding="utf-8") as f:
                base = json.load(f)
            for cat, actual in metrics["categorias"].items():
                ref = base.get("categorias", {}).get(cat)
                if not ref:
                    continue
                delta = actual["recall_at_5"] - ref["recall_at_5"]
                if delta < -max_regresion:
                    reasons.append(
                        f"{cat}: Recall@5 {actual['recall_at_5']:.2f}% vs baseline "
                        f"{ref['recall_at_5']:.2f}% ({delta:+.2f} pp)"
                    )
        except Exception as exc:  # baseline corrupta no debe tumbar la corrida
            print(f"[WARN] No se pudo leer la baseline {baseline_path}: {exc}")
    else:
        print(
            f"[INFO] Sin baseline en {baseline_path} — se omitió la comparación por "
            f"categoría. Generala con: cp scripts/qa_metrics.json scripts/{baseline_name}"
        )

    return (len(reasons) == 0), reasons


if __name__ == "__main__":
    metrics, gate_ok, reasons = run_evaluation()
    if not gate_ok:
        print("\n" + "!" * 80)
        print("GATE DE REGRESIÓN: FALLADO")
        print("!" * 80)
        for r in reasons:
            print(f"  ✗ {r}")
        print("\nLa suite termina en rojo a propósito: estos números están por debajo")
        print("de la baseline oficial. Si estás en una corrida exploratoria (ablación,")
        print("experimento) y esperabas este resultado, relaja o apaga el gate con:")
        print("  BIORAG_QA_GATE=0 ./scripts/run_qa_suite.sh")
        print("  BIORAG_QA_MIN_RECALL5=95.0 BIORAG_QA_MAX_FALLOS=42 ./scripts/run_qa_suite.sh")
        print("!" * 80)
        sys.exit(1)
    if reasons:
        print(f"\n[GATE] OK — {'; '.join(reasons)}")
    else:
        print("\n[GATE] OK — métricas dentro de los umbrales de la baseline oficial")
