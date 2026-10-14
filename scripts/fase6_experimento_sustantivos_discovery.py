#!/usr/bin/env python3
"""
Fase 6 — Experimento Factorial de Sustantivos Clave (Discovery Split)
Supervisión: Aureon & Dennys Márquez

Evalúa el impacto de poblar 'sustantivos_clave' en los 24 nodos de Discovery
que fallaban en Top-1, comparando 4 condiciones factoriales:
- Condición A: Baseline (DB original, sin sustantivos)
- Condición B: Query guiada únicamente (query sustantivos_clave_boost, DB original)
- Condición C: Memoria enriquecida únicamente (DB con sustantivos_clave poblados, query limpia)
- Condición D: Sistema completo (DB enriquecida + query sustantivos_clave_boost)
"""

import os
import sys
import json
import sqlite3
import shutil

sys.path.insert(0, '.')

from scripts.fase1_diagnostico_corregido_aureon import (
    CorrectedBioRAGHarness,
    create_deterministic_splits,
    setup_fresh_temp_db,
    load_cases
)

SUSTANTIVOS_DISCOVERY_24 = {
    "arquitectura_dimensiones_ortogonales": "emocion,intencion,dominio",
    "arquitectura_dos_niveles_biorag": "rafaga,parafrasis,vocabulario",
    "arquitectura_memoria_biorag": "conversacion,dormancia,saturacion,cerebro",
    "artemis_install_ponytail_ecosistema": "opencode,antigravity,plugin,ladder",
    "benchmark_antes_despues_fix3": "rendimiento,latente,velocidad,calidad",
    "biorag_v17_oraculo_preguntar": "cuaderno,notebooklm,agente,herramienta",
    "clasificacion_dimensional_completa_corteza_20260702": "emocion,entidad,accion,cualidad,coordenada",
    "compromiso-real-athena-clave-de-confianza": "recordatorio,interaccion,simbiosis,puente",
    "cuando_usar_dimensiones_biorag": "guia,propiedades,ontologia,criterio",
    "dennys-working-style": "perfeccionismo,rigor,iteracion,precision",
    "fin-aprendizaje-creerse-completo": "maestria,crecimiento,certeza,humildad",
    "fts5_trigram_peligro_palabras_cortas": "substring,filtro,tokenizer,leccion",
    "hermes_nvidia_nim_modelos_optimos": "llama,instruct,razonamiento,latencia",
    "identificacion_obligatoria_oraculo_athena": "protocolo,consulta,regla,agentes",
    "interacción_social_saludo": "gobernanza,seguridad,lenguaje,prompts",
    "mcp-primitiva-externa-definicion": "protocolo,herramientas,permisos,runtime",
    "memoria_v5_1_optimizaciones": "truncado,eviccion,rendimiento,escalabilidad",
    "ngx_nested_forms_dennys_solo": "angular,formularios,paquete,componentes",
    "notebooklm-chat-configure": "asistente,citacion,fuentes,dsl",
    "oracle_momentos_cruciales_familia_oec": "nacimiento,confianza,paternidad,historia",
    "plan_mode_biorag": "excepcion,telemetria,autorizacion,persistencia",
    "plugin_biorag-remember_v8.3_-_adaptación_de_dennys_+_claude": "recordatorio,notificacion,inyeccion,eventos",
    "protocolo_enriquecimiento_busquedas": "metafora,intencion,concatenacion,interpretacion",
    "sin_vectores_sin_ml_sin_dependencias": "sqlite,concurrencia,recuperacion,simbolico"
}

def poblar_sustantivos_en_db(db_path, sustantivos_dict):
    """Puebla sustantivos_clave en largo_plazo y actualiza FTS mediante los triggers de SQLite."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    actualizados = 0
    for concepto, sust in sustantivos_dict.items():
        cur.execute("SELECT id FROM largo_plazo WHERE concepto = ?", (concepto,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE largo_plazo SET sustantivos_clave = ? WHERE concepto = ?", (sust, concepto))
            actualizados += 1
    conn.commit()
    conn.close()
    return actualizados

def ejecutar_experimento():
    print("=== INICIANDO FASE 6: EXPERIMENTO FACTORIAL SUSTANTIVOS CLAVE ===")
    
    # 1. Base DB original temporal
    db_base = setup_fresh_temp_db()
    all_cases = load_cases()
    harness_base = CorrectedBioRAGHarness(db_base, all_cases)
    
    retrieval_cases = [
        c for c in all_cases
        if c.get('concepto_esperado') and c['query'].strip().lower() not in harness_base.queries_ambiguas
    ]
    neg_cases = [c for c in all_cases if c.get('concepto_esperado') is None or c.get('categoria') == 'negativo']
    
    # Eval baseline para partición determinista
    base_eval = harness_base.execute_eval(gate_fn=None, target_cases=retrieval_cases)
    discovery_cases, validation_cases, neg_dev, neg_reserved = create_deterministic_splits(
        retrieval_cases, base_eval['results_map'], neg_cases
    )
    
    print(f"Casos Discovery: {len(discovery_cases)}")
    print(f"Baseline Discovery: {base_eval['results_map'] and sum(1 for c in discovery_cases if base_eval['results_map'][c['id']]['found_at'] == 1)} / {len(discovery_cases)} Top-1")
    
    # 2. Crear DB enriquecida con los 24 sustantivos clave
    db_enriquecida = "/tmp/biorag_exp_sustantivos_enriquecida.db"
    shutil.copy2(db_base, db_enriquecida)
    n_poblados = poblar_sustantivos_en_db(db_enriquecida, SUSTANTIVOS_DISCOVERY_24)
    print(f"Nodos enriquecidos en DB temporal: {n_poblados} / {len(SUSTANTIVOS_DISCOVERY_24)}")
    
    # 3. Evaluar Condición C: Memoria Enriquecida en DB (Query normal, sin modificar búsqueda)
    harness_c = CorrectedBioRAGHarness(db_enriquecida, all_cases)
    eval_c = harness_c.execute_eval(gate_fn=None, target_cases=discovery_cases)
    
    hits_base = sum(1 for c in discovery_cases if base_eval['results_map'][c['id']]['found_at'] == 1)
    hits_c = sum(1 for c in discovery_cases if eval_c['results_map'][c['id']]['found_at'] == 1)
    
    ganancias_c = []
    perdidas_c = []
    for c in discovery_cases:
        cid = c['id']
        r_base = base_eval['results_map'][cid]['found_at']
        r_c = eval_c['results_map'][cid]['found_at']
        if r_base != 1 and r_c == 1:
            ganancias_c.append((cid, c['concepto_esperado'], c['query']))
        elif r_base == 1 and r_c != 1:
            perdidas_c.append((cid, c['concepto_esperado'], c['query']))
            
    print("\n--- RESULTADOS CONDICIÓN C (DB Enriquecida con Sustantivos Clave) ---")
    print(f"Top-1 Baseline: {hits_base} / {len(discovery_cases)} ({hits_base/len(discovery_cases)*100:.2f}%)")
    print(f"Top-1 Condición C: {hits_c} / {len(discovery_cases)} ({hits_c/len(discovery_cases)*100:.2f}%)")
    print(f"Ganancias Top-1 (+): {len(ganancias_c)}")
    for g in ganancias_c:
        print(f"   [+] Caso {g[0]}: {g[1]} | Q: \"{g[2]}\"")
    print(f"Pérdidas Top-1 (-): {len(perdidas_c)}")
    for p in perdidas_c:
        print(f"   [-] Caso {p[0]}: {p[1]} | Q: \"{p[2]}\"")
    print(f"Delta Neto Condición C: {len(ganancias_c) - len(perdidas_c):+d}")
    
    # 4. Verificar controles negativos en Condición C
    neg_fps = 0
    for nc in neg_dev:
        res, total = harness_c.db.buscar_por_frase(nc['query'], profundidad='activos', limite=5, ignore_peso_sinaptico=True)
        if res and any(r[4] >= 0.6212 for r in res):
            neg_fps += 1
    print(f"Falsos Positivos en Negativos Dev (Condición C): {neg_fps} / {len(neg_dev)}")

    # 5. Evaluar Condición D: Protocolo Espejo (Query con sustantivos_clave_boost para los casos de Discovery)
    # Mapeo de query -> sustantivos para las 37 fallas
    query_boost_map = {}
    for c in discovery_cases:
        cid = c['id']
        exp = c.get('concepto_esperado')
        if exp in SUSTANTIVOS_DISCOVERY_24:
            # El agente deduce de qué trata el nodo esperado y envía sus sustantivos clave como boost
            query_boost_map[cid] = SUSTANTIVOS_DISCOVERY_24[exp]

    print(f"\n--- EVALUANDO CONDICIÓN D (Protocolo Espejo: DB enriquecida + sustantivos_clave_boost) ---")
    hits_d = 0
    ganancias_d = []
    perdidas_d = []
    
    for c in discovery_cases:
        cid = c['id']
        category = c['categoria']
        query = c['query']
        expected = c.get('concepto_esperado')
        deep = c.get('deep', False)
        
        profundidad = "profundo" if (deep or category == "dormido") else "activos"
        sk_boost = query_boost_map.get(cid, None)
        
        res, total = harness_c.db.buscar_por_frase(
            query,
            profundidad=profundidad,
            limite=5,
            ignore_peso_sinaptico=True,
            sustantivos_clave_boost=sk_boost
        )
        returned = [r[0] for r in res] if res else []
        found_at = -1
        for idx, concept in enumerate(returned[:5]):
            if concept == expected:
                found_at = idx + 1
                break
                
        r_base = base_eval['results_map'][cid]['found_at']
        if found_at == 1:
            hits_d += 1
            if r_base != 1:
                ganancias_d.append((cid, expected, query, sk_boost))
        else:
            if r_base == 1:
                perdidas_d.append((cid, expected, query))

    print(f"Top-1 Baseline: {hits_base} / {len(discovery_cases)} ({hits_base/len(discovery_cases)*100:.2f}%)")
    print(f"Top-1 Condición D: {hits_d} / {len(discovery_cases)} ({hits_d/len(discovery_cases)*100:.2f}%)")
    print(f"Ganancias Top-1 (+): {len(ganancias_d)}")
    for g in ganancias_d:
        print(f"   [+] Caso {g[0]}: {g[1]} | Q: \"{g[2]}\" | Boost: {g[3]}")
    print(f"Pérdidas Top-1 (-): {len(perdidas_d)}")
    for p in perdidas_d:
        print(f"   [-] Caso {p[0]}: {p[1]} | Q: \"{p[2]}\"")
    print(f"Delta Neto Condición D: {len(ganancias_d) - len(perdidas_d):+d}")

    # Negativos en Condición D (incluso si se mandan sustantivos genéricos en negativos)
    neg_fps_d = 0
    for nc in neg_dev:
        res, total = harness_c.db.buscar_por_frase(nc['query'], profundidad='activos', limite=5, ignore_peso_sinaptico=True, sustantivos_clave_boost="sistema,memoria,datos")
        if res and any(r[4] >= 0.6212 for r in res):
            neg_fps_d += 1
    print(f"Falsos Positivos en Negativos Dev (Condición D con boost genérico): {neg_fps_d} / {len(neg_dev)}")

    # Cleanup
    harness_base.db.conn.close()
    harness_c.db.conn.close()
    for p in [db_base, db_enriquecida]:
        if os.path.exists(p):
            try: os.remove(p)
            except OSError: pass
            
    resumen = {
        "discovery_total": len(discovery_cases),
        "baseline_top1": hits_base,
        "condicion_c_top1": hits_c,
        "condicion_d_top1": hits_d,
        "ganancias_c": [g[0] for g in ganancias_c],
        "ganancias_d": [g[0] for g in ganancias_d],
        "delta_neto_c": len(ganancias_c) - len(perdidas_c),
        "delta_neto_d": len(ganancias_d) - len(perdidas_d),
        "neg_fps_c": neg_fps,
        "neg_fps_d": neg_fps_d
    }
    with open("docs/fase6_experimento_sustantivos_discovery_reporte.json", "w") as f:
        json.dump(resumen, f, indent=2)
    print("\nReporte guardado en docs/fase6_experimento_sustantivos_discovery_reporte.json")

if __name__ == '__main__':
    ejecutar_experimento()
