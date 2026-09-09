"""
Evaluación del Abismo Léxico — EXP-Q: Rescate por Grafo Sináptico (v31.0).

Mide la capacidad de MemoryBioRAG para recuperar nodos donde existe un
"Abismo Léxico" (stem(query) ∩ stem(gold) = ∅; cero solapamiento de palabras).
Compara la búsqueda primaria estándar (context_window=0) contra la
recuperación contextual por grafo sináptico (context_window=2).

Sensibilidad al tamaño del corpus y freno de seguridad:
    La tasa de rescate depende de cuántos nodos activos y sinapsis tenga el
    grafo: a mayor corpus, más candidatos compiten por los slots del BFS,
    y el gold puede quedar fuera del corte de BIORAG_MAX_CONTEXTOS.
    Como le pusimos un freno de seguridad estricto para que la búsqueda nunca se
    congele ni se ponga lenta (fíjate que la expansión toma apenas ~0.019 segundos),
    el algoritmo se detiene honestamente si a 2 saltos no lo encuentra, en vez de
    quedarse buscando en bucle.
    Queda documentado para que más adelante se pueda implementar un algoritmo
    que recorra todo el grafo sin congelar (ej. Random Walk / PPR, BFS heurístico).
    Esta suite usa el snapshot congelado para garantizar reproducibilidad.
    Para evaluar la DB viva, pasar BIORAG_PATH explícitamente.

Uso:
    python3 scripts/test_abismo_lexico.py
    BIORAG_PATH=MemoryBioRAG_Data/memory_biorag.db python3 scripts/test_abismo_lexico.py
"""

import sys
import os
import time

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG


# Casos auditados de evaluación con 0 solapamiento léxico / raíces
CASOS_ABISMO_LEXICO = [
    {
        "id": "EXP-Q-01",
        "query": "panel visual de desarrollo para despacho de tareas",
        "nodo_esperado": "kilo_vscode_extension_principal",
        "descripcion": "Extensión IDE y despacho de tareas en entorno visual",
        "categoria": "Herramientas / Infraestructura de Desarrollo"
    },
    {
        "id": "EXP-Q-02",
        "query": "comprobacion fidedigna de ficheros previo a emitir dictamenes",
        "nodo_esperado": "regla_verificar_codigo_real_antes_de_diagnostico",
        "descripcion": "Regla metodológica de verificación de código real (cero coincidencia de raíz)",
        "categoria": "Metacognición / Reglas de Validación"
    },
    {
        "id": "EXP-Q-03",
        "query": "resolucion de colisiones valorativas en bifurcaciones",
        "nodo_esperado": "ajuste_tejedora_valencia_desempate_fase1",
        "descripcion": "Desempate de valencia somática en bifurcaciones de red",
        "categoria": "Topología Sináptica / Desempates"
    }
]


def evaluar_abismo_lexico():
    """Ejecuta la evaluación de rescate por grafo sináptico."""
    print("=" * 75)
    print("EVALUACIÓN ABISMO LÉXICO (EXP-Q): Rescate por Grafo Sináptico")
    print("=" * 75)

    db_path = os.environ.get("BIORAG_PATH") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "snapshots", "qa_escape_qcr_20260811.db"
    )

    if not os.path.exists(db_path):
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "MemoryBioRAG_Data", "memory_biorag.db"
        )

    limite_mcp = int(os.environ.get("BIORAG_LIMITE_MCP", "10"))
    cerebro = SQLiteMemoryBioRAG(db_path)

    print(f"\n[INFO] DB Evaluada: {db_path}")
    cursor = cerebro.conn.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado='activo'")
    print(f"[INFO] Nodos activos: {cursor.fetchone()[0]}")
    cursor = cerebro.conn.execute("SELECT COUNT(*) FROM sinapsis")
    print(f"[INFO] Sinapsis en el grafo: {cursor.fetchone()[0]}")
    print(f"[INFO] Límite de anclajes primarios evaluados: {limite_mcp}")

    rescatados_count = 0
    total_casos = len(CASOS_ABISMO_LEXICO)
    resultados = []

    for i, caso in enumerate(CASOS_ABISMO_LEXICO, 1):
        print(f"\n{'─' * 75}")
        print(f"CASO {i} [{caso['id']}]: {caso['descripcion']}")
        print(f"  Categoría:  {caso['categoria']}")
        print(f"  Query:      \"{caso['query']}\"")
        print(f"  Esperado:   {caso['nodo_esperado']}")

        # 1. Búsqueda primaria FTS5 / PPMI estándar (context_window=0)
        start_prim = time.time()
        primarios, _ = cerebro.buscar_por_frase(caso['query'], context_window=0, limite=limite_mcp)
        tiempo_prim = time.time() - start_prim

        en_primarios = any(r[0] == caso['nodo_esperado'] for r in primarios)
        top1_primario = primarios[0][0] if primarios else "Ninguno"
        score_top1 = primarios[0][4] if primarios else 0.0

        print(f"\n  [BÚSQUEDA PRIMARIA - FTS5 / Léxica]")
        print(f"    Tiempo:       {tiempo_prim:.3f}s")
        print(f"    Top-1:        {top1_primario} (score: {score_top1:.4f})")
        print(f"    Encontrado:   {'✅ Sí' if en_primarios else '❌ No (Abismo Léxico puro: 0 overlap)'}")

        # 2. Expansión por Grafo Sináptico (context_window=2)
        start_grafo = time.time()
        _, contexto_vecinos = cerebro.expandir_contexto_vecinos(primarios, depth=2)
        tiempo_grafo = time.time() - start_grafo

        hallazgos = [idx for idx, v in enumerate(contexto_vecinos) if v[0] == caso['nodo_esperado']]
        rescatado = len(hallazgos) > 0

        print(f"\n  [EXPANSIÓN POR GRAFO SINÁPTICO - Anti-Sesgo Alfabético + Hebbiano]")
        print(f"    Tiempo:       {tiempo_grafo:.3f}s")
        print(f"    Vecinos BFS:  {len(contexto_vecinos)} candidatos relacionales")

        if rescatado:
            pos = hallazgos[0] + 1
            score_ctx = contexto_vecinos[hallazgos[0]][4]
            print(f"    Rescate:      ✅ RESCATADO en posición {pos} (score contextual: {score_ctx:.4f})")
            rescatados_count += 1
        else:
            print(f"    Rescate:      ❌ No alcanzado a profundidad 2")

        resultados.append({
            "id": caso['id'],
            "query": caso['query'],
            "esperado": caso['nodo_esperado'],
            "en_primarios": en_primarios,
            "rescatado": rescatado,
            "posicion": hallazgos[0] + 1 if rescatado else None
        })

    print("\n" + "=" * 75)
    print("RESUMEN DE RESCATE EN EL ABISMO LÉXICO")
    print("=" * 75)
    print(f"Tasa de Rescate por Grafo Sináptico: {rescatados_count}/{total_casos} ({rescatados_count/total_casos*100:.1f}%)")
    print("-" * 75)
    for r in resultados:
        prim_str = "✅ TOP" if r["en_primarios"] else "❌ 0 Overlap"
        if r["rescatado"]:
            grafo_str = f"✅ RESCATADO (Pos #{r['posicion']})"
        else:
            grafo_str = "❌ No alcanzado"
        print(f"  {r['id']}: Primaria: {prim_str:<12} -> Grafo: {grafo_str} | {r['esperado'][:35]}")
    print("=" * 75)

    return rescatados_count == total_casos


if __name__ == "__main__":
    exito = evaluar_abismo_lexico()
    if not exito:
        print("\n[AVISO] Algunos casos no fueron rescatados a la profundidad evaluada.")
    else:
        print("\n[OK] ¡Todos los casos de abismo léxico auditados fueron rescatados con éxito por el grafo sináptico!")
