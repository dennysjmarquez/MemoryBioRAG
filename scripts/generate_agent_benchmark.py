#!/usr/bin/env python3
"""
Generador automático de benchmark para memoria de agente.
Se deriva de log_busquedas: pares query-real + nodo-útil, con pesos de señal.

Señales:
- STRONG (weight=1.0): log_busquedas.util = 1 (feedback explícito positivo)
  O re-referencia: misma query → mismo concepto en múltiples búsquedas
- WEAK (weight=0.3): log_busquedas.util IS NULL y no hubo corrección posterior
  (ausencia de corrección no = confirmación, pero es mejor que nada)

Salida: agent_benchmark_v1.jsonl (formato compatible con casos_qa_baseline)
"""

import sqlite3
import json
import sys
import os
from collections import defaultdict
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.memory_store import SQLiteMemoryBioRAG

DB_PATH = Path(__file__).parent.parent / "MemoryBioRAG_Data" / "memory_biorag.db"
OUTPUT_PATH = Path(__file__).parent.parent / "agent_benchmark_v1.jsonl"
COLD_START_PATH = Path(__file__).parent.parent / "agent_benchmark_coldstart.jsonl"

# Mapeo de categoría BioRAG → prioridad agente (P0-P5)
CAT_TO_PRIORITY = {
    'Principle': 0,      # P0: Núcleo inmutable
    'Protocol': 1,       # P1: Reglas operativas
    'Profile': 1,        # P1: Identidad relacional
    'Relation': 1,       # P1: Vínculos
    'Architecture': 2,   # P2: Decisiones de diseño
    'Cognition': 2,      # P2: Procesos cognitivos
    'Lesson': 3,         # P3: Aprendizaje episódico
    'Personal': 3,       # P3: Personal
    'Project': 3,        # P3: Proyectos activos
    'General': 4,        # P4: Táctico general
    'System': 4,         # P4: Sistema
}

def get_categoria_name(conn, cat_id):
    """Obtiene nombre de categoría por ID."""
    row = conn.execute("SELECT name FROM categories WHERE id = ?", (cat_id,)).fetchone()
    return row[0] if row else 'General'

def find_best_concept(cerebro, query, exclude_concepts=set()):
    """Usa el motor de búsqueda real para encontrar el mejor concepto."""
    # Usar buscar_por_frase con query limpia
    results, total = cerebro.buscar_por_frase(
        query, 
        profundidad="activos", 
        limite=5,
        categoria=None
    )
    for concepto, contenido, peso, estado, score, asociaciones in results:
        if concepto not in exclude_concepts:
            # Obtener categoría del concepto
            row = cerebro.cursor.execute(
                "SELECT categoria FROM largo_plazo WHERE concepto = ?", (concepto,)
            ).fetchone()
            return concepto, row[0] if row else 1
    return None, None

def main():
    if not DB_PATH.exists():
        print(f"❌ DB no encontrada: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Initialize cerebro for real search
    cerebro = SQLiteMemoryBioRAG()

    # 1. Leer casos cold-start (fallback hardcodeado)
    cold_start_cases = []
    if COLD_START_PATH.exists():
        with open(COLD_START_PATH, 'r') as f:
            for line in f:
                if line.strip():
                    cold_start_cases.append(json.loads(line))

    # 2. Analizar log_busquedas para señales reales
    cursor = conn.execute("""
        SELECT 
            lb.query,
            lb.resultados_count,
            lb.top_score,
            lb.creado_en,
            lb.util,
            lb.params_json
        FROM log_busquedas lb
        WHERE lb.resultados_count > 0
        ORDER BY lb.creado_en DESC
    """)
    
    query_counts = defaultdict(int)
    query_first_seen = {}
    positive_cases = []  # util=1
    weak_cases = []      # util IS NULL, sin corrección detectada
    
    for row in cursor:
        q = row['query']
        query_counts[q] += 1
        if q not in query_first_seen:
            query_first_seen[q] = row['creado_en']
        
        if row['util'] == 1:
            positive_cases.append({
                'query': q,
                'timestamp': row['creado_en'],
                'weight': 1.0,
                'signal_type': 'explicit_positive'
            })
        elif row['util'] is None:
            weak_cases.append({
                'query': q,
                'timestamp': row['creado_en'],
                'weight': 0.3,
                'signal_type': 'no_correction'
            })

    # 3. Detectar re-referencias (misma query aparece múltiples veces)
    reref_queries = {q for q, count in query_counts.items() if count >= 2}
    
    # 4. Generar casos desde señales reales usando búsqueda real
    cold_start_concepts = {c['concepto_esperado'] for c in cold_start_cases}
    cold_start_queries = {c['query'] for c in cold_start_cases}
    
    generated_cases = []
    used_concepts = set()
    case_id = len(cold_start_cases) + 1
    
    # Procesar casos positivos (señal fuerte)
    for case in positive_cases:
        q = case['query']
        if q in cold_start_queries:
            continue
        if case_id > 50:
            break
            
        # Buscar mejor match con motor real
        concepto, cat_id = find_best_concept(cerebro, q, exclude_concepts=used_concepts | cold_start_concepts)
        if concepto and concepto not in cold_start_concepts:
            cat_name = get_categoria_name(conn, cat_id)
            priority = CAT_TO_PRIORITY.get(cat_name, 3)
            
            weight = case['weight']
            if q in reref_queries:
                weight = 1.0  # re-referencia = señal fuerte
            
            generated_cases.append({
                'id': f"ab_{case_id:03d}",
                'categoria': 'literal',
                'query': q,
                'concepto_esperado': concepto,
                'prioridad': priority,
                'signal_weight': weight,
                'notes': f"Auto-derivado: {case['signal_type']}{' + reref' if q in reref_queries else ''}",
                'deep': False
            })
            used_concepts.add(concepto)
            case_id += 1

    # Procesar casos weak (señal débil) - solo si hay espacio y no duplican
    for case in weak_cases:
        if case_id > 50:
            break
        q = case['query']
        if q in cold_start_queries or q in {c['query'] for c in generated_cases}:
            continue
            
        concepto, cat_id = find_best_concept(cerebro, q, exclude_concepts=used_concepts | cold_start_concepts)
        if concepto:
            cat_name = get_categoria_name(conn, cat_id)
            priority = CAT_TO_PRIORITY.get(cat_name, 3)
            
            generated_cases.append({
                'id': f"ab_{case_id:03d}",
                'categoria': 'literal',
                'query': q,
                'concepto_esperado': concepto,
                'prioridad': priority,
                'signal_weight': case['weight'],
                'notes': f"Auto-derivado: {case['signal_type']} (débil)",
                'deep': False
            })
            used_concepts.add(concepto)
            case_id += 1

    # 5. Combinar: cold-start primero (P0/P1 prioritarios), luego generados ordenados por signal_weight
    all_cases = cold_start_cases + sorted(generated_cases, key=lambda c: -c['signal_weight'])

    # 6. Escribir archivo congelado
    with open(OUTPUT_PATH, 'w') as f:
        for case in all_cases:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')

    print(f"✅ Benchmark generado: {OUTPUT_PATH}")
    print(f"   Cold-start: {len(cold_start_cases)} casos")
    print(f"   Auto-derivados: {len(generated_cases)} casos")
    print(f"   Total: {len(all_cases)} casos")
    for p in range(6):
        cnt = sum(1 for c in all_cases if c.get('prioridad', 3) == p)
        if cnt:
            print(f"   P{p}: {cnt}")

    cerebro.cerrar_sistema()
    conn.close()

if __name__ == "__main__":
    main()