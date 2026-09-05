"""
Evaluación del Concept Hub — FASE 2: Búsquedas semánticas puras.

Mide si el Concept Hub resuelve el problema de vocabulario sin overlap.
Compara resultados CON y SIN hub para las 5 queries de la FASE 2.

Uso:
    python3 scripts/test_concept_hub.py
    (desde el directorio raíz del proyecto: cd <raiz_biorag>)
"""

import sys
import os
import json
import time

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG
from core.concept_hub import expandir_query_con_hub, crear_tablas, cargar_hubs_iniciales


# ─── CASOS DE PRUEBA FASE 2 (Paráfrasis Naturales de Generalización) ───

CASOS_FASE2 = [
    {
        "query": "qué hacía antes de ser programador",
        "nodo_esperado": "historia_tasajera_fumigador_rufino",
        "descripcion": "Empleos previos a IT (paráfrasis)"
    },
    {
        "query": "metí un cambio y todo se rompió",
        "nodo_esperado": "leccion_control_flujo_codigo_preexistente",
        "descripcion": "Regresiones por cambios (paráfrasis 2a)"
    },
    {
        "query": "toqué algo que andaba bien y dejó de andar",
        "nodo_esperado": "leccion_control_flujo_codigo_preexistente",
        "descripcion": "Ruptura de código preexistente (paráfrasis 2b)"
    },
    {
        "query": "cómo sobrevivía económicamente antes de la tecnología",
        "nodo_esperado": "historia_tasajera_fumigador_rufino",
        "descripcion": "Supervivencia pre-tecnología (paráfrasis)"
    },
    {
        "query": "dos modelos de IA que no están de acuerdo, ¿cómo resuelvo?",
        "nodo_esperado": "resolucion_de_contradicciones_entre_insights_sumatoria_mentalidad",
        "descripcion": "Consenso multi-modelo (paráfrasis)"
    }
]


def evaluar_concept_hub():
    """Ejecuta la evaluación completa."""
    print("=" * 70)
    print("EVALUACIÓN CONCEPT HUB — FASE 2: Vocabulario sin overlap")
    print("=" * 70)

    # Inicializar con la DB que la suite aísla (BIORAG_PATH), igual que el resto de
    # tests/ y scripts. Antes se hardcodeaba memory_biorag_test.db, así que el paso
    # [3/4] de run_qa_suite.sh medía un corpus DISTINTO al de producción (880 nodos /
    # 12 hubs / 78 bridges contra 993 / 17 / 119 de la DB viva) y además escribía
    # (crear_tablas + cargar_hubs_iniciales) fuera de la copia aislada que el wrapper
    # promete proteger. Sin BIORAG_PATH se conserva el default histórico.
    db_path = os.environ.get("BIORAG_PATH") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "MemoryBioRAG_Data", "memory_biorag_test.db"
    )

    cerebro = SQLiteMemoryBioRAG(db_path)

    # Asegurar que las tablas del hub existen y los hubs iniciales están sincronizados
    crear_tablas(cerebro.conn)
    cargar_hubs_iniciales(cerebro.conn)

    print(f"\n[INFO] DB: {db_path}")
    cursor = cerebro.conn.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado='activo'")
    print(f"[INFO] Nodos activos: {cursor.fetchone()[0]}")
    cursor = cerebro.conn.execute("SELECT COUNT(*) FROM concept_hubs")
    print(f"[INFO] Concept Hubs: {cursor.fetchone()[0]}")
    cursor = cerebro.conn.execute("SELECT COUNT(*) FROM concept_hub_bridges")
    print(f"[INFO] Bridges: {cursor.fetchone()[0]}")

    resultados = []

    for i, caso in enumerate(CASOS_FASE2, 1):
        print(f"\n{'─' * 70}")
        print(f"CASO {i}: {caso['descripcion']}")
        print(f"  Query: \"{caso['query']}\"")
        print(f"  Esperado: {caso['nodo_esperado']}")

        # 1. Test SIN hub (deshabilitar expansión temporalmente)
        print(f"\n  [SIN HUB]")
        start = time.time()
        try:
            # Temporarily disable hub expansion
            import core.memory_store as ms
            original_expand = ms.expandir_query_con_hub if hasattr(ms, 'expandir_query_con_hub') else None
            # Patch the import in buscar_por_frase to return None
            import sys
            original_getattr = sys.modules.get('core.concept_hub')
            
            # Create a mock module that returns None for expandir_query_con_hub
            class MockHub:
                @staticmethod
                def expandir_query_con_hub(*args, **kwargs):
                    return None
                crear_tablas = lambda *a, **k: None
                cargar_hubs_iniciales = lambda *a, **k: None
            
            sys.modules['core.concept_hub'] = MockHub()
            
            resultados_sin, total_sin = cerebro.buscar_por_frase(
                caso["query"], limite=5
            )
            
            # Restore original module
            if original_getattr:
                sys.modules['core.concept_hub'] = original_getattr
            elif 'core.concept_hub' in sys.modules:
                del sys.modules['core.concept_hub']
            tiempo_sin = time.time() - start

            encontrado_sin = any(
                r[0] == caso["nodo_esperado"] for r in resultados_sin
            )
            posicion_sin = -1
            for j, r in enumerate(resultados_sin):
                if r[0] == caso["nodo_esperado"]:
                    posicion_sin = j + 1
                    break

            print(f"    Resultados: {total_sin} | Tiempo: {tiempo_sin:.3f}s")
            print(f"    Nodo esperado: {'✅ TOP' + str(posicion_sin) if encontrado_sin else '❌ No encontrado'}")
            if resultados_sin:
                print(f"    TOP-3: {[r[0] for r in resultados_sin[:3]]}")
        except Exception as e:
            print(f"    ERROR: {e}")
            encontrado_sin = False
            posicion_sin = -1
            tiempo_sin = 0

        # 2. Test CON hub (expandir query)
        print(f"\n  [CON HUB]")
        hub_result = expandir_query_con_hub(caso["query"], cerebro.conn)
        if hub_result:
            print(f"    Hub matcheado: {hub_result['hub_id']} (confianza: {hub_result['hub_confidence']:.3f})")
            print(f"    Bridges: {hub_result['bridges_matched']}")
            print(f"    Términos expandidos: {hub_result['expanded_terms'][:10]}...")
        else:
            print(f"    Hub: Ninguno matcheó")

        start = time.time()
        try:
            # Buscar con la query original — la expansión interna del hub se encarga
            resultados_con, total_con = cerebro.buscar_por_frase(
                caso["query"], limite=5
            )
            tiempo_con = time.time() - start

            encontrado_con = any(
                r[0] == caso["nodo_esperado"] for r in resultados_con
            )
            posicion_con = -1
            for j, r in enumerate(resultados_con):
                if r[0] == caso["nodo_esperado"]:
                    posicion_con = j + 1
                    break

            print(f"    Resultados: {total_con} | Tiempo: {tiempo_con:.3f}s")
            print(f"    Nodo esperado: {'✅ TOP' + str(posicion_con) if encontrado_con else '❌ No encontrado'}")
            if resultados_con:
                print(f"    TOP-3: {[r[0] for r in resultados_con[:3]]}")
        except Exception as e:
            print(f"    ERROR: {e}")
            encontrado_con = False
            posicion_con = -1
            tiempo_con = 0

        resultados.append({
            "caso": i,
            "query": caso["query"],
            "esperado": caso["nodo_esperado"],
            "sin_hub_encontrado": encontrado_sin,
            "sin_hub_posicion": posicion_sin,
            "con_hub_encontrado": encontrado_con,
            "con_hub_posicion": posicion_con,
            "hub_match": hub_result is not None
        })

    # Resumen
    print(f"\n{'=' * 70}")
    print("RESUMEN")
    print(f"{'=' * 70}")

    exitos_sin = sum(1 for r in resultados if r["sin_hub_encontrado"])
    exitos_con = sum(1 for r in resultados if r["con_hub_encontrado"])
    hubs_match = sum(1 for r in resultados if r["hub_match"])

    print(f"\n{'Métrica':<30} {'SIN Hub':<15} {'CON Hub':<15}")
    print(f"{'─' * 60}")
    print(f"{'Recall@5 (encontrados)':<30} {exitos_sin}/{len(resultados)} ({exitos_sin/len(resultados)*100:.0f}%){'':<5} {exitos_con}/{len(resultados)} ({exitos_con/len(resultados)*100:.0f}%)")
    print(f"{'Hubs matcheados':<30} {'N/A':<15} {hubs_match}/{len(resultados)} ({hubs_match/len(resultados)*100:.0f}%)")

    print(f"\n{'Detalle por caso:'}")
    for r in resultados:
        status_sin = "✅" if r["sin_hub_encontrado"] else "❌"
        status_con = "✅" if r["con_hub_encontrado"] else "❌"
        pos_sin = f"TOP{r['sin_hub_posicion']}" if r["sin_hub_encontrado"] else "-"
        pos_con = f"TOP{r['con_hub_posicion']}" if r["con_hub_encontrado"] else "-"
        print(f"  Caso {r['caso']}: {status_sin} {pos_sin} → {status_con} {pos_con}  | {r['query'][:50]}")

    # Guardar resultados
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "concept_hub_eval_results.json"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "fecha": time.strftime("%Y-%m-%d %H:%M"),
            "total_casos": len(resultados),
            "exitos_sin_hub": exitos_sin,
            "exitos_con_hub": exitos_con,
            "hubs_matcheados": hubs_match,
            "resultados": resultados
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Resultados guardados en: {output_path}")

    cerebro.cerrar_sistema()
    return resultados


if __name__ == "__main__":
    evaluar_concept_hub()
