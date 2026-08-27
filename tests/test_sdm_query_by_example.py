#!/usr/bin/env python3
"""
Test aislado: SDM Query-by-Example
===================================
Prueba si el SDM puede encontrar nodos conceptualmente similares
usando vectores de nodos existentes en vez de texto del query.

Este test NO modifica archivos existentes. Es 100% aislado.
"""

import sys
import os
import time

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sdm import (
    generar_vector_sdm, distancia_hamming, similitud_sdm,
    SDM_BITS, SDM_BYTES, SEGMENTO_DIMENSIONES, _hash_token_a_bit
)


def test_01_vectores_mismas_dimensiones():
    """Prueba 1: Vectores con mismas dimensiones → Hamming bajo."""
    print("\n" + "="*60)
    print("PRUEBA 1: Vectores con dimensiones compartidas")
    print("="*60)

    # Crear vectores con las mismas dimensiones pero texto diferente
    vec_gato = generar_vector_sdm(
        concepto="gato",
        contenido="animal domestico Felis catus pequeno",
        dimensiones=[1, 5, 10, 15]
    )
    vec_felino = generar_vector_sdm(
        concepto="felino",
        contenido="felino salvaje Panthera grande",
        dimensiones=[1, 5, 10, 15]  # mismas dimensiones
    )
    vec_auto = generar_vector_sdm(
        concepto="automovil",
        contenido="vehiculo motor cuatro ruedas",
        dimensiones=[20, 25, 30]  # dimensiones distintas
    )
    vec_programa = generar_vector_sdm(
        concepto="programa",
        contenido="codigo fuente compilador ejecutable",
        dimensiones=[40, 45, 50]  # otras dimensiones distintas
    )

    dist_gato_felino = distancia_hamming(vec_gato, vec_felino)
    dist_gato_auto = distancia_hamming(vec_gato, vec_auto)
    dist_gato_programa = distancia_hamming(vec_gato, vec_programa)
    dist_felino_auto = distancia_hamming(vec_felino, vec_auto)

    print(f"\nResultados (de {SDM_BITS} bits totales):")
    print(f"  gato ↔ felino:  {dist_gato_felino:4d} bits  (mismas dimensiones)")
    print(f"  gato ↔ auto:    {dist_gato_auto:4d} bits  (dimensiones distintas)")
    print(f"  gato ↔ programa:{dist_gato_programa:4d} bits  (dimensiones distintas)")
    print(f"  felino ↔ auto:  {dist_felino_auto:4d} bits  (dimensiones distintas)")

    # Cálculo de similitud Jaccard
    sim_gf = similitud_sdm(vec_gato, vec_felino)
    sim_ga = similitud_sdm(vec_gato, vec_auto)
    print(f"\nSimilitud Jaccard:")
    print(f"  gato ↔ felino:  {sim_gf:.4f}")
    print(f"  gato ↔ auto:    {sim_ga:.4f}")

    # Veredicto
    radio = 250
    print(f"\nRadio Hamming: {radio}")
    print(f"  gato ↔ felino DENTRO del radio: {dist_gato_felino <= radio}")
    print(f"  gato ↔ auto FUERA del radio: {dist_gato_auto > radio}")

    assert dist_gato_felino < dist_gato_auto


def test_02_vectores_mismos_vecinos():
    """Prueba 2: Vectores con mismos vecinos sinápticos → Hamming bajo."""
    print("\n" + "="*60)
    print("PRUEBA 2: Vectores con vecinos sinápticos compartidos")
    print("="*60)

    vec_gato = generar_vector_sdm(
        concepto="gato",
        contenido="animal domestico",
        dimensiones=[1, 5],
        vecinos=["veterinario", "mascota", "comida_gato"]
    )
    vec_felino = generar_vector_sdm(
        concepto="felino",
        contenido="felino salvaje",
        dimensiones=[2, 6],  # dimensiones DISTINTAS
        vecinos=["veterinario", "mascota", "comida_gato"]  # mismos vecinos
    )
    vec_auto = generar_vector_sdm(
        concepto="automovil",
        contenido="vehiculo motor",
        dimensiones=[20, 25],
        vecinos=["mecanico", "gasolina", "ruedas"]  # vecinos distintos
    )

    dist_gato_felino = distancia_hamming(vec_gato, vec_felino)
    dist_gato_auto = distancia_hamming(vec_gato, vec_auto)

    print(f"\nResultados:")
    print(f"  gato ↔ felino:  {dist_gato_felino:4d} bits  (mismos vecinos)")
    print(f"  gato ↔ auto:    {dist_gato_auto:4d} bits  (vecinos distintos)")

    radio = 250
    print(f"\nRadio: {radio}")
    print(f"  gato ↔ felino DENTRO: {dist_gato_felino <= radio}")
    print(f"  gato ↔ auto FUERA: {dist_gato_auto > radio}")

    assert dist_gato_felino < dist_gato_auto, f"gato↔felino ({dist_gato_felino}) no es menor que gato↔auto ({dist_gato_auto})"


def test_03_bit_masking():
    """Prueba 3: Ignorar bits de texto, solo comparar bits semánticos."""
    print("\n" + "="*60)
    print(f"PRUEBA 3: Bit Masking — ignorar bits de texto ({SEGMENTO_DIMENSIONES[0]}-{SEGMENTO_DIMENSIONES[1]-1})")
    print("="*60)

    vec_gato = generar_vector_sdm(
        concepto="gato",
        contenido="animal domestico Felis catus",
        dimensiones=[1, 5, 10]
    )
    vec_felino = generar_vector_sdm(
        concepto="felino",
        contenido="felino salvaje Panthera",
        dimensiones=[1, 5, 10]  # mismas dimensiones
    )
    vec_auto = generar_vector_sdm(
        concepto="automovil",
        contenido="vehiculo motor cuatro ruedas",
        dimensiones=[20, 25]  # dimensiones distintas
    )

    # Convertir a enteros para masking
    int_gato = int.from_bytes(vec_gato, 'big')
    int_felino = int.from_bytes(vec_felino, 'big')
    int_auto = int.from_bytes(vec_auto, 'big')

    # Máscara: solo bits del segmento de dimensiones (bits semánticos).
    # Los demás segmentos (contenido, concepto, categoría, vecinos) enmascarados a 0.
    inicio_sem, fin_sem = SEGMENTO_DIMENSIONES
    mask_semantico = 0
    for i in range(inicio_sem, fin_sem):
        mask_semantico |= (1 << (SDM_BITS - 1 - i))

    # Aplicar máscara
    gato_sem = int_gato & mask_semantico
    felino_sem = int_felino & mask_semantico
    auto_sem = int_auto & mask_semantico

    # Calcular Hamming sobre bits semánticos
    dist_gato_felino_sem = (gato_sem ^ felino_sem).bit_count()
    dist_gato_auto_sem = (gato_sem ^ auto_sem).bit_count()

    # Hamming normal para comparar
    dist_gato_felino_full = distancia_hamming(vec_gato, vec_felino)
    dist_gato_auto_full = distancia_hamming(vec_gato, vec_auto)

    print(f"\nHamming NORMAL (todos los bits):")
    print(f"  gato ↔ felino:  {dist_gato_felino_full:4d} bits")
    print(f"  gato ↔ auto:    {dist_gato_auto_full:4d} bits")

    total_sem = fin_sem - inicio_sem
    print(f"\nHamming SOLO bits semánticos ({inicio_sem}-{fin_sem-1}):")
    print(f"  gato ↔ felino:  {dist_gato_felino_sem:4d} bits  (de {total_sem} posibles)")
    print(f"  gato ↔ auto:    {dist_gato_auto_sem:4d} bits  (de {total_sem} posibles)")

    print(f"\n¿El masking mejora la distinción?")
    if dist_gato_auto_sem > 0:
        print(f"  Ratio normal:    {dist_gato_felino_full/dist_gato_auto_full:.2f}x")
        print(f"  Ratio semántico: {dist_gato_felino_sem/dist_gato_auto_sem:.2f}x")

    assert dist_gato_felino_sem < dist_gato_auto_sem


def test_04_reponderar_vectores():
    """Prueba 4: Reponderar vectores — más bits a semántica, menos a texto."""
    print("\n" + "="*60)
    print("PRUEBA 4: Reponderación — vectores con más peso semántico")
    print("="*60)

    def generar_vector_reponderado(concepto, contenido="", dimensiones=None, vecinos=None):
        """Vector con más bits para dimensiones y vecinos."""
        bit_array = [0] * SDM_BITS

        # Texto: solo 200 bits (antes 400)
        if contenido:
            from core.stemmer_es import stem
            tokens = [stem(t.lower()) for t in contenido.split() if len(t) >= 3]
            for tok in set(tokens[:30]):
                b = _hash_token_a_bit(tok, 0, 200)
                bit_array[b] = 1

        # Concepto: 100 bits (antes 200)
        from core.stemmer_es import stem
        tokens_c = [stem(t.lower()) for t in concepto.split() if len(t) >= 2]
        for tok in tokens_c:
            b = _hash_token_a_bit(tok, 200, 300)
            bit_array[b] = 1

        # Dimensiones: 400 bits (antes 200) — MÁS PESO
        if dimensiones:
            for dim in dimensiones:
                b = _hash_token_a_bit(str(dim).lower(), 300, 700)
                bit_array[b] = 1

        # Categoría: 124 bits
        b = _hash_token_a_bit("general", 700, 824)
        bit_array[b] = 1

        # Vecinos: 200 bits (antes 124) — MÁS PESO
        if vecinos:
            for vec in vecinos:
                b = _hash_token_a_bit(str(vec).lower(), 824, 1024)
                bit_array[b] = 1

        # Empaquetar
        bytes_list = bytearray(SDM_BYTES)
        for i in range(SDM_BITS):
            if bit_array[i]:
                byte_idx = i // 8
                bit_idx = i % 8
                bytes_list[byte_idx] |= (1 << (7 - bit_idx))
        return bytes(bytes_list)

    vec_gato = generar_vector_reponderado(
        concepto="gato",
        contenido="animal domestico Felis catus",
        dimensiones=[1, 5, 10],
        vecinos=["veterinario", "mascota"]
    )
    vec_felino = generar_vector_reponderado(
        concepto="felino",
        contenido="felino salvaje Panthera",
        dimensiones=[1, 5, 10],  # mismas dimensiones
        vecinos=["veterinario", "mascota"]  # mismos vecinos
    )
    vec_auto = generar_vector_reponderado(
        concepto="automovil",
        contenido="vehiculo motor cuatro ruedas",
        dimensiones=[20, 25],  # dimensiones distintas
        vecinos=["mecanico", "gasolina"]  # vecinos distintos
    )

    dist_gato_felino = distancia_hamming(vec_gato, vec_felino)
    dist_gato_auto = distancia_hamming(vec_gato, vec_auto)

    print(f"\nVectores reponderados (400 bits semánticos vs 200 texto):")
    print(f"  gato ↔ felino:  {dist_gato_felino:4d} bits")
    print(f"  gato ↔ auto:    {dist_gato_auto:4d} bits")

    radio = 250
    print(f"\nRadio: {radio}")
    print(f"  gato ↔ felino DENTRO: {dist_gato_felino <= radio}")
    print(f"  gato ↔ auto FUERA: {dist_gato_auto > radio}")

    assert dist_gato_felino < dist_gato_auto


def test_05_datos_reales():
    """Prueba 5: Usar nodos REALES de la DB."""
    print("\n" + "="*60)
    print("PRUEBA 5: Datos reales de la DB")
    print("="*60)

    db_path = "/mnt/recursos_compartidos_y_otros/MemoryBioRAG/MemoryBioRAG_Data/memory_biorag.db"
    if not os.path.exists(db_path):
        print(f"  DB no encontrada: {db_path}")
        print("  Saltando prueba 5")
        assert False, "DB no encontrada"

    import sqlite3
    conn = sqlite3.connect(db_path)

    # Verificar que hay nodos SDM
    count = conn.execute("SELECT COUNT(*) FROM nodos_sdm").fetchone()[0]
    print(f"\n  Nodos SDM indexados: {count}")

    if count < 10:
        print("  Muy pocos nodos para probar")
        return None

    # Obtener todos los vectores
    nodos = conn.execute("SELECT concepto, vector FROM nodos_sdm").fetchall()
    print(f"  Nodos cargados: {len(nodos)}")

    # Para cada nodo, encontrar los 5 más cercanos
    print(f"\n  Top-3 similares por nodo:")
    resultados_buenos = 0

    for concepto, vector in nodos[:10]:  # solo primeros 10
        int_vec = int.from_bytes(vector, 'big')
        distancias = []

        for c2, v2 in nodos:
            if c2 != concepto:
                dist = distancia_hamming(vector, v2)
                if dist <= 300:  # radio amplio para ver más
                    distancias.append((c2, dist))

        distancias.sort(key=lambda x: x[1])
        top3 = distancias[:3]

        if top3:
            print(f"\n  {concepto}:")
            for c, d in top3:
                print(f"    → {c}: {d} bits, sim={similitud_sdm(vector, conn.execute('SELECT vector FROM nodos_sdm WHERE concepto=?', (c,)).fetchone()[0]):.4f}")

            # Verificar si hay al menos uno conceptualmente parecido
            top1 = top3[0][0]
            if top1 != concepto:
                resultados_buenos += 1

    conn.close()

    print(f"\n  Nodos con al menos 1 similar: {resultados_buenos}/10")
    assert resultados_buenos > 0, f"Nodos con al menos 1 similar: {resultados_buenos}/10"


def main():
    print("="*60)
    print("SDM QUERY-BY-EXAMPLE: Test Aislado")
    print("="*60)
    print(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Bits por vector: {SDM_BITS}")
    print(f"Bytes por vector: {SDM_BYTES}")

    resultados = {}

    # Ejecutar todas las pruebas
    resultados['prueba_1'] = test_01_vectores_mismas_dimensiones()
    resultados['prueba_2'] = test_02_vectores_mismos_vecinos()
    resultados['prueba_3'] = test_03_bit_masking()
    resultados['prueba_4'] = test_04_reponderar_vectores()
    resultados['prueba_5'] = test_05_datos_reales()

    # Resumen
    print("\n" + "="*60)
    print("RESUMEN DE RESULTADOS")
    print("="*60)

    for prueba, ok in resultados.items():
        if ok is None:
            status = "⏭️  SKIP"
        elif ok:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        print(f"  {prueba}: {status}")

    # Veredicto
    passed = sum(1 for v in resultados.values() if v is True)
    total = sum(1 for v in resultados.values() if v is not None)

    print(f"\n  Total: {passed}/{total} pruebas pasaron")

    if passed >= 3:
        print("\n🎉 CONCEPTO VALIDADO: SDM query-by-example FUNCIONA")
        print("   Se puede implementar en el código real.")
    elif passed >= 1:
        print("\n⚠️  CONCEPTO PARCIAL: Algunas opciones funcionan")
        print("   Revisar qué opciones específicas pasaron.")
    else:
        print("\n❌ CONCEPTO NO VALIDADO: Ninguna opción funcionó")
        print("   Reconsiderar el enfoque.")


if __name__ == "__main__":
    main()
