#!/usr/bin/env python3
"""
Test de colisión SDM: 2048 vs 10,000 bits
Usa nodos REALES de por_tema que fallan + sus distractores.
Mide colisiones falsas (nodos no relacionados con Hamming bajo).
"""

import sys
import os
import time
import hashlib
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sdm import (
    generar_vector_sdm, similitud_sdm, distancia_hamming,
    SDM_BITS, SDM_BYTES, _cargar_hebbianos,
    SEGMENTO_CONTENIDO, SEGMENTO_CONCEPTO, SEGMENTO_DIMENSIONES,
    SEGMENTO_CATEGORIA, SEGMENTO_VECINOS,
    PESO_TOKEN, PESO_DIMENSION, PESO_CATEGORIA, PESO_VECINO,
    _hash_token_a_bit, _activar_ventana, _obtener_cluster_dim,
    _obtener_idf_dim, _calcular_rango_cluster
)

# Nodos reales de por_tema que fallan + distractores conocidos
TEST_CASES = [
    {
        "query": "operativo capa rag",
        "expected": "oracle_custom_prompt_arsitecura_que_funciona",
        "distractors": [
            "fallo_clasificador_wordnet_query_dimensiones",
            "capa3_pseudo_relevance_feedback_dimensional",
            "auto_vincular_tres_capas_semantica",
        ]
    },
    {
        "query": "relevantes biomimética mejor",
        "expected": "benchmark_antes_despues_fix3",
        "distractors": [
            "oracle_auditoria_patrones_mejora_athena",
            "biorag_v16_0_estado",
            "mejora_skills_por_uso_real",
        ]
    },
    {
        "query": "activa largo archivos",
        "expected": "biorag_v11_1_detalle_tecnico",
        "distractors": [
            "oec_comms_version_final_solo_archivos",
            "poda-contextual-archivos-configuracion",
            "lesson_biorag_hook_retroactivo",
        ]
    },
    {
        "query": "modelo typos completa",
        "expected": "sin_vectores_sin_ml_sin_dependencias",
        "distractors": [
            "biorag_fts5_trigram_lesson",
            "hermes_optimizacion_completada_20260615",
            "artemis_sesion_v10_3_optimizacion_completa",
        ]
    },
    {
        "query": "paráfrasis vectores búsqueda",
        "expected": "arquitectura_dos_niveles_biorag",
        "distractors": [
            "v13_1_parafrasis_expansion_semantica",
            "principio_paráfrasis_nivel_dios",
            "arquitectura_dimensiones_ortogonales",
        ]
    },
]

# === Versión modificada de generar_vector para D bits arbitrarios ===

def _hash_token_a_bit_arbitrary(token, min_bit, max_bit, total_bits):
    """Hash un token a posición de bit en rango dado, para vector de total_bits."""
    rango = max_bit - min_bit
    if rango <= 0:
        return min_bit
    # Escalar rango al total_bits disponible
    scaled_min = int(min_bit * total_bits / SDM_BITS)
    scaled_max = int(max_bit * total_bits / SDM_BITS)
    scaled_range = max(scaled_max - scaled_min, 1)
    h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
    return scaled_min + (h % scaled_range)


def _activar_ventana_arbitrary(bit_array, pos_base, rango_inicio, rango_fin, n_bits, total_bits):
    """Activa ventana de bits para vector de total_bits."""
    scaled_inicio = int(rango_inicio * total_bits / SDM_BITS)
    scaled_fin = int(rango_fin * total_bits / SDM_BITS)
    rango_tam = scaled_fin - scaled_inicio
    if rango_tam <= 0:
        return
    for i in range(n_bits):
        pos = scaled_inicio + ((pos_base + i) % rango_tam)
        if 0 <= pos < len(bit_array):
            bit_array[pos] = 1


def generar_vector_arbitrary(concepto, contenido="", categoria="",
                              dimensiones=None, vecinos=None, total_bits=10000):
    """Genera vector SDM con total_bits arbitrarios (mismo algoritmo, más ancho)."""
    bit_array = [0] * total_bits
    data = _cargar_hebbianos()
    clusters = data.get('clusters', [])
    total_clusters = len(clusters)

    # 1. Tokens de contenido
    if contenido:
        from core.stemmer_es import stem
        tokens_contenido = [stem(t.lower()) for t in contenido.split() if len(t) >= 3]
        for tok in set(tokens_contenido[:50]):
            pos = _hash_token_a_bit_arbitrary(tok, *SEGMENTO_CONTENIDO, total_bits)
            _activar_ventana_arbitrary(bit_array, pos, *SEGMENTO_CONTENIDO, 4, total_bits)

    # 2. Tokens de concepto
    from core.stemmer_es import stem
    tokens_concepto = [stem(t.lower()) for t in concepto.split() if len(t) >= 2]
    for tok in tokens_concepto:
        pos = _hash_token_a_bit_arbitrary(tok, *SEGMENTO_CONCEPTO, total_bits)
        _activar_ventana_arbitrary(bit_array, pos, *SEGMENTO_CONCEPTO, 4, total_bits)

    # 3. Dimensiones Hebbianas
    if dimensiones and total_clusters > 0:
        for dim_id in dimensiones:
            cluster_idx = _obtener_cluster_dim(dim_id)
            idf = _obtener_idf_dim(dim_id)
            if idf > 3.0:
                n_bits = 16
            elif idf > 1.5:
                n_bits = 12
            elif idf > 0.5:
                n_bits = 8
            else:
                n_bits = 4
            if cluster_idx >= 0:
                rango = _calcular_rango_cluster(cluster_idx, total_clusters)
            else:
                rango = SEGMENTO_DIMENSIONES
            pos = _hash_token_a_bit_arbitrary(str(dim_id), *rango, total_bits)
            _activar_ventana_arbitrary(bit_array, pos, *rango, n_bits, total_bits)

    # 4. Categoría
    if categoria is not None:
        pos = _hash_token_a_bit_arbitrary(str(categoria).lower(), *SEGMENTO_CATEGORIA, total_bits)
        _activar_ventana_arbitrary(bit_array, pos, *SEGMENTO_CATEGORIA, 8, total_bits)

    # 5. Vecinos
    if vecinos:
        for vec in vecinos:
            pos = _hash_token_a_bit_arbitrary(str(vec).lower(), *SEGMENTO_VECINOS, total_bits)
            _activar_ventana_arbitrary(bit_array, pos, *SEGMENTO_VECINOS, 4, total_bits)

    # Empaquetar
    nbytes = total_bits // 8
    bytes_list = bytearray(nbytes)
    for i in range(min(total_bits, nbytes * 8)):
        if bit_array[i]:
            byte_idx = i // 8
            bit_idx = i % 8
            bytes_list[byte_idx] |= (1 << (7 - bit_idx))

    return bytes(bytes_list)


def hamming_arbitrary(vec1, vec2):
    """Hamming distance para vectores de bytes arbitrarios."""
    if len(vec1) != len(vec2):
        return max(len(vec1), len(vec2)) * 8
    int1 = int.from_bytes(vec1, 'big')
    int2 = int.from_bytes(vec2, 'big')
    return (int1 ^ int2).bit_count()


def similitud_jaccard_arbitrary(vec1, vec2):
    """Jaccard simple (sin ponderación) para vectores arbitrarios."""
    if len(vec1) != len(vec2):
        return 0.0
    int1 = int.from_bytes(vec1, 'big')
    int2 = int.from_bytes(vec2, 'big')
    inter = (int1 & int2).bit_count()
    union = (int1 | int2).bit_count()
    return round(inter / union, 4) if union > 0 else 0.0


def load_node_data(concepto, cerebro):
    """Carga datos de un nodo para generar vector SDM."""
    row = cerebro.cursor.execute(
        "SELECT categoria, contenido FROM largo_plazo WHERE concepto = ?", (concepto,)
    ).fetchone()
    if not row:
        return None
    cat, cont = row[0] or "", row[1] or ""

    dims_rows = cerebro.cursor.execute(
        "SELECT dimension_id FROM largo_plazo_dimensiones WHERE concepto = ?", (concepto,)
    ).fetchall()
    dims = [r[0] for r in dims_rows]

    vecinos_rows = cerebro.cursor.execute(
        "SELECT destino FROM sinapsis WHERE origen = ? UNION SELECT origen FROM sinapsis WHERE destino = ?",
        (concepto, concepto)
    ).fetchall()
    vecinos = [r[0] for r in vecinos_rows]

    return {"concepto": cat, "contenido": cont, "categoria": cat, "dimensiones": dims, "vecinos": vecinos}


def run_collision_test():
    """Test principal de colisión."""
    from core.memory_store import SQLiteMemoryBioRAG as CerebroMemoria

    print("=" * 70)
    print("TEST DE COLISIÓN SDM: 2048 vs 10,000 bits")
    print("Nodos reales de por_tema (fallidos) + distractores")
    print("=" * 70)

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'MemoryBioRAG_Data', 'memory_biorag.db')
    cerebro = CerebroMemoria(db_path)

    # Recopilar todos los conceptos únicos
    all_concepts = set()
    for case in TEST_CASES:
        all_concepts.add(case["expected"])
        for d in case["distractors"]:
            all_concepts.add(d)

    # Cargar datos y generar vectores
    print("\n[1] Cargando nodos y generando vectores...")
    node_data = {}
    for c in all_concepts:
        data = load_node_data(c, cerebro)
        if data:
            node_data[c] = data

    print(f"    Nodos cargados: {len(node_data)}/{len(all_concepts)}")

    # Generar vectores 2048-bit (actual)
    vectors_2048 = {}
    for c, d in node_data.items():
        vectors_2048[c] = generar_vector_sdm(
            concepto=c, contenido=d["contenido"],
            categoria=d["categoria"], dimensiones=d["dimensiones"],
            vecinos=d["vecinos"]
        )

    # Generar vectores 10000-bit (simulación)
    vectors_10000 = {}
    for c, d in node_data.items():
        vectors_10000[c] = generar_vector_arbitrary(
            concepto=c, contenido=d["contenido"],
            categoria=d["categoria"], dimensiones=d["dimensiones"],
            vecinos=d["vecinos"], total_bits=10000
        )

    print("    Vectores generados: 2048-bit y 10000-bit")

    # === Test 1: Pares relacionados (expected vs query) ===
    print("\n" + "=" * 70)
    print("TEST 1: Pares RELACIONADOS (expected del query)")
    print("=" * 70)

    related_distances_2048 = []
    related_distances_10000 = []
    related_jaccard_2048 = []
    related_jaccard_10000 = []

    for case in TEST_CASES:
        expected = case["expected"]
        if expected not in vectors_2048:
            continue
        # Comparar expected contra cada distractor
        for d in case["distractors"]:
            if d not in vectors_2048:
                continue
            dist_2048 = hamming_arbitrary(vectors_2048[expected], vectors_2048[d])
            dist_10000 = hamming_arbitrary(vectors_10000[expected], vectors_10000[d])
            jac_2048 = similitud_jaccard_arbitrary(vectors_2048[expected], vectors_2048[d])
            jac_10000 = similitud_jaccard_arbitrary(vectors_10000[expected], vectors_10000[d])

            related_distances_2048.append(dist_2048)
            related_distances_10000.append(dist_10000)
            related_jaccard_2048.append(jac_2048)
            related_jaccard_10000.append(jac_10000)

            print(f"  {expected[:45]:45s} vs {d[:30]:30s}")
            print(f"    2048-bit: Hamming={dist_2048:4d} ({dist_2048/2048*100:.1f}%) Jaccard={jac_2048:.4f}")
            print(f"    10000-bit: Hamming={dist_10000:5d} ({dist_10000/10000*100:.1f}%) Jaccard={jac_10000:.4f}")
            print()

    if related_distances_2048:
        print(f"  RESUMEN RELACIONADOS:")
        print(f"    2048-bit: Hamming promedio = {sum(related_distances_2048)/len(related_distances_2048):.0f} ({sum(related_distances_2048)/len(related_distances_2048)/2048*100:.1f}%)")
        print(f"    10000-bit: Hamming promedio = {sum(related_distances_10000)/len(related_distances_10000):.0f} ({sum(related_distances_10000)/len(related_distances_10000)/10000*100:.1f}%)")
        print(f"    2048-bit: Jaccard promedio = {sum(related_jaccard_2048)/len(related_jaccard_2048):.4f}")
        print(f"    10000-bit: Jaccard promedio = {sum(related_jaccard_10000)/len(related_jaccard_10000):.4f}")

    # === Test 2: Pares NO relacionados (distractor vs distractor) ===
    print("\n" + "=" * 70)
    print("TEST 2: Pares NO RELACIONADOS (distractor vs otro distractor)")
    print("=" * 70)

    unrelated_distances_2048 = []
    unrelated_distances_10000 = []
    unrelated_jaccard_2048 = []
    unrelated_jaccard_10000 = []

    all_distractors = []
    for case in TEST_CASES:
        for d in case["distractors"]:
            if d in vectors_2048:
                all_distractors.append(d)

    # Comparar cada par de distractores entre sí
    tested = 0
    for i in range(len(all_distractors)):
        for j in range(i + 1, min(i + 5, len(all_distractors))):  # Limitar para no explotar
            d1, d2 = all_distractors[i], all_distractors[j]
            if d1 == d2:
                continue
            dist_2048 = hamming_arbitrary(vectors_2048[d1], vectors_2048[d2])
            dist_10000 = hamming_arbitrary(vectors_10000[d1], vectors_10000[d2])
            jac_2048 = similitud_jaccard_arbitrary(vectors_2048[d1], vectors_2048[d2])
            jac_10000 = similitud_jaccard_arbitrary(vectors_10000[d1], vectors_10000[d2])

            unrelated_distances_2048.append(dist_2048)
            unrelated_distances_10000.append(dist_10000)
            unrelated_jaccard_2048.append(jac_2048)
            unrelated_jaccard_10000.append(jac_10000)
            tested += 1

            if tested <= 6:  # Mostrar solo primeros 6
                print(f"  {d1[:40]:40s} vs {d2[:35]:35s}")
                print(f"    2048-bit: Hamming={dist_2048:4d} ({dist_2048/2048*100:.1f}%) Jaccard={jac_2048:.4f}")
                print(f"    10000-bit: Hamming={dist_10000:5d} ({dist_10000/10000*100:.1f}%) Jaccard={jac_10000:.4f}")
                print()

    if unrelated_distances_2048:
        print(f"  RESUMEN NO RELACIONADOS ({tested} pares):")
        print(f"    2048-bit: Hamming promedio = {sum(unrelated_distances_2048)/len(unrelated_distances_2048):.0f} ({sum(unrelated_distances_2048)/len(unrelated_distances_2048)/2048*100:.1f}%)")
        print(f"    10000-bit: Hamming promedio = {sum(unrelated_distances_10000)/len(unrelated_distances_10000):.0f} ({sum(unrelated_distances_10000)/len(unrelated_distances_10000)/10000*100:.1f}%)")
        print(f"    2048-bit: Jaccard promedio = {sum(unrelated_jaccard_2048)/len(unrelated_jaccard_2048):.4f}")
        print(f"    10000-bit: Jaccard promedio = {sum(unrelated_jaccard_10000)/len(unrelated_jaccard_10000):.4f}")

    # === Test 3: Tasa de colisión ===
    print("\n" + "=" * 70)
    print("TEST 3: TASA DE COLISIÓN (Hamming < 30% del total)")
    print("=" * 70)

    threshold_2048 = int(2048 * 0.30)  # 614 bits
    threshold_10000 = int(10000 * 0.30)  # 3000 bits

    collision_unrelated_2048 = sum(1 for d in unrelated_distances_2048 if d < threshold_2048)
    collision_unrelated_10000 = sum(1 for d in unrelated_distances_10000 if d < threshold_10000)

    collision_related_2048 = sum(1 for d in related_distances_2048 if d < threshold_2048)
    collision_related_10000 = sum(1 for d in related_distances_10000 if d < threshold_10000)

    print(f"  Umbral: 2048-bit < {threshold_2048} bits | 10000-bit < {threshold_10000} bits")
    print()
    print(f"  NO RELACIONADOS (deberían estar ALTO, lejos del umbral):")
    if unrelated_distances_2048:
        print(f"    2048-bit: {collision_unrelated_2048}/{len(unrelated_distances_2048)} colisionan ({collision_unrelated_2048/len(unrelated_distances_2048)*100:.1f}%)")
        print(f"    10000-bit: {collision_unrelated_10000}/{len(unrelated_distances_10000)} colisionan ({collision_unrelated_10000/len(unrelated_distances_10000)*100:.1f}%)")
    print()
    print(f"  RELACIONADOS (deberían estar BAJO, cerca del umbral):")
    if related_distances_2048:
        print(f"    2048-bit: {collision_related_2048}/{len(related_distances_2048)} colisionan ({collision_related_2048/len(related_distances_2048)*100:.1f}%)")
        print(f"    10000-bit: {collision_related_10000}/{len(related_distances_10000)} colisionan ({collision_related_10000/len(related_distances_10000)*100:.1f}%)")

    # === Test 4: Separación (gap entre relacionados y no relacionados) ===
    print("\n" + "=" * 70)
    print("TEST 4: SEPARACIÓN (gap entre relacionados y no relacionados)")
    print("=" * 70)

    if related_distances_2048 and unrelated_distances_2048:
        avg_related_2048 = sum(related_distances_2048) / len(related_distances_2048)
        avg_unrelated_2048 = sum(unrelated_distances_2048) / len(unrelated_distances_2048)
        gap_2048 = avg_unrelated_2048 - avg_related_2048

        avg_related_10000 = sum(related_distances_10000) / len(related_distances_10000)
        avg_unrelated_10000 = sum(unrelated_distances_10000) / len(unrelated_distances_10000)
        gap_10000 = avg_unrelated_10000 - avg_related_10000

        print(f"  2048-bit:")
        print(f"    Promedio relacionados: {avg_related_2048:.0f} bits ({avg_related_2048/2048*100:.1f}%)")
        print(f"    Promedio no relacionados: {avg_unrelated_2048:.0f} bits ({avg_unrelated_2048/2048*100:.1f}%)")
        print(f"    GAP: {gap_2048:.0f} bits ({gap_2048/2048*100:.1f}%)")
        print()
        print(f"  10000-bit:")
        print(f"    Promedio relacionados: {avg_related_10000:.0f} bits ({avg_related_10000/10000*100:.1f}%)")
        print(f"    Promedio no relacionados: {avg_unrelated_10000:.0f} bits ({avg_unrelated_10000/10000*100:.1f}%)")
        print(f"    GAP: {gap_10000:.0f} bits ({gap_10000/10000*100:.1f}%)")
        print()
        print(f"  MEJORA DEL GAP: {gap_10000 - gap_2048:.0f} bits ({(gap_10000 - gap_2048)/gap_2048*100:.1f}% más separación)")

    # === Test 5: Benchmark de rendimiento ===
    print("\n" + "=" * 70)
    print("TEST 5: COSTO (memoria + tiempo)")
    print("=" * 70)

    n_nodes = len(vectors_2048)
    mem_2048 = n_nodes * 256  # 2048 bits = 256 bytes
    mem_10000 = n_nodes * 1250  # 10000 bits = 1250 bytes

    print(f"  Nodos en test: {n_nodes}")
    print(f"  Memoria vectores 2048-bit: {mem_2048:,} bytes ({mem_2048/1024:.1f} KB)")
    print(f"  Memoria vectores 10000-bit: {mem_10000:,} bytes ({mem_10000/1024:.1f} KB)")
    print(f"  Overhead: +{mem_10000 - mem_2048:,} bytes (+{(mem_10000-mem_2048)/mem_2048*100:.0f}%)")
    print()

    # Proyectado a 600 nodos (corpus actual)
    mem_600_2048 = 600 * 256
    mem_600_10000 = 600 * 1250
    print(f"  PROYECCIÓN a 600 nodos (corpus actual):")
    print(f"    2048-bit: {mem_600_2048:,} bytes ({mem_600_2048/1024:.1f} KB)")
    print(f"    10000-bit: {mem_600_10000:,} bytes ({mem_600_10000/1024:.1f} KB)")
    print(f"    Overhead: +{mem_600_10000 - mem_600_2048:,} bytes (+{(mem_600_10000-mem_600_2048)/mem_600_2048*100:.0f}%)")

    # Tiempo de Hamming
    import random
    keys = list(vectors_2048.keys())
    if len(keys) >= 2:
        # Warm up
        for _ in range(100):
            k1, k2 = random.sample(keys, 2)
            hamming_arbitrary(vectors_2048[k1], vectors_2048[k2])
            hamming_arbitrary(vectors_10000[k1], vectors_10000[k2])

        # Benchmark 2048-bit
        t0 = time.time()
        for _ in range(10000):
            k1, k2 = random.sample(keys, 2)
            hamming_arbitrary(vectors_2048[k1], vectors_2048[k2])
        t_2048 = time.time() - t0

        # Benchmark 10000-bit
        t0 = time.time()
        for _ in range(10000):
            k1, k2 = random.sample(keys, 2)
            hamming_arbitrary(vectors_10000[k1], vectors_10000[k2])
        t_10000 = time.time() - t0

        print(f"\n  TIEMPO (10,000 comparaciones Hamming):")
        print(f"    2048-bit: {t_2048:.3f}s ({t_2048/10000*1000:.4f}ms por comparación)")
        print(f"    10000-bit: {t_10000:.3f}s ({t_10000/10000*1000:.4f}ms por comparación)")
        print(f"    Overhead: +{t_10000/t_2048:.1f}x más lento")

    # === CONCLUSIÓN ===
    print("\n" + "=" * 70)
    print("CONCLUSIÓN")
    print("=" * 70)

    if related_distances_2048 and unrelated_distances_2048:
        avg_rel_2048 = sum(related_distances_2048) / len(related_distances_2048)
        avg_unr_2048 = sum(unrelated_distances_2048) / len(unrelated_distances_2048)
        gap_2048 = avg_unr_2048 - avg_rel_2048

        avg_rel_10000 = sum(related_distances_10000) / len(related_distances_10000)
        avg_unr_10000 = sum(unrelated_distances_10000) / len(unrelated_distances_10000)
        gap_10000 = avg_unr_10000 - avg_rel_10000

        improvement_pct = (gap_10000 - gap_2048) / gap_2048 * 100 if gap_2048 > 0 else 0

        print(f"  Gap de separación 2048-bit: {gap_2048:.0f} bits ({gap_2048/2048*100:.1f}% del espacio)")
        print(f"  Gap de separación 10000-bit: {gap_10000:.0f} bits ({gap_10000/10000*100:.1f}% del espacio)")
        print(f"  Mejora absoluta: +{gap_10000 - gap_2048:.0f} bits")
        print(f"  Mejora relativa: +{improvement_pct:.1f}%")
        print()

        if improvement_pct > 20:
            print("  VEREDICTO: La mejora es SIGNIFICATIVA.")
            print("  Pero el costo es 5x más memoria y ~2x más lento.")
            print("  Para 600 nodos, el impacto es mínimo en RAM total.")
        elif improvement_pct > 5:
            print("  VEREDICTO: La mejora es MODERADA.")
            print("  El beneficio no justifica el cambio para corpus de 600 nodos.")
        else:
            print("  VEREDICTO: La mejora es MÍNIMA o INEXISTENTE.")
            print("  El espacio actual (2048-bit) es suficiente para el corpus.")
            print("  No vale la pena cambiar.")

    cerebro.cerrar_sistema()


if __name__ == "__main__":
    run_collision_test()
