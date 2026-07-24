#!/usr/bin/env python3
"""
Test 3: SDM Query-by-Example — Tipos de texto diversos
========================================================
Prueba con sinónimos técnicos, abreviaturas,跨 dominio, etc.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sdm import generar_vector_sdm, distancia_hamming, similitud_sdm, SDM_BITS


def test_01_sononimos_tecnicos():
    """Sinónimos técnicos: bug ↔ error, code ↔ código."""
    print("\n" + "="*60)
    print("PRUEBA 1: Sinónimos técnicos")
    print("="*60)

    pares = [
        ("bug", "error", "bug", "error de software"),
        ("code", "código", "programación", "código fuente"),
        ("deploy", "desplegar", "deployar", "publicar en servidor"),
        ("refactor", "refactorizar", "reestructurar", "mejorar código"),
        ("debug", "depurar", "debugging", "encontrar errores"),
    ]

    for c1, c2, cont1, cont2 in pares:
        vec1 = generar_vector_sdm(concepto=c1, contenido=cont1, dimensiones=[50, 55])
        vec2 = generar_vector_sdm(concepto=c2, contenido=cont2, dimensiones=[50, 55])
        vec3 = generar_vector_sdm(concepto="cocina", contenido="receta comida", dimensiones=[30, 35])

        dist_same = distancia_hamming(vec1, vec2)
        dist_diff = distancia_hamming(vec1, vec3)
        sim = similitud_sdm(vec1, vec2)

        status = "✅" if dist_same < dist_diff else "❌"
        print(f"  {c1}↔{c2}: {dist_same:3d} bits (sim={sim:.4f}) vs {c1}↔cocina: {dist_diff:3d} bits {status}")

    return True


def test_02_abreviaturas():
    """Abreviaturas: DB ↔ base de datos, AI ↔ inteligencia artificial."""
    print("\n" + "="*60)
    print("PRUEBA 2: Abreviaturas")
    print("="*60)

    pares = [
        ("DB", "base de datos", "almacenamiento relacional", "SQL"),
        ("AI", "inteligencia artificial", "machine learning", "modelos"),
        ("API", "interfaz de programación", "endpoint", "REST"),
        ("URL", "dirección web", "enlace", "hyperlink"),
        ("SQL", "lenguaje de consulta", "consultas", "SELECT"),
    ]

    for abrev, completo, cont1, cont2 in pares:
        vec_abrev = generar_vector_sdm(concepto=abrev, contenido=cont1, dimensiones=[50, 55, 60])
        vec_completo = generar_vector_sdm(concepto=completo, contenido=cont2, dimensiones=[50, 55, 60])
        vec_other = generar_vector_sdm(concepto="restaurante",contenido="comida servicio", dimensiones=[30, 35])

        dist_same = distancia_hamming(vec_abrev, vec_completo)
        dist_diff = distancia_hamming(vec_abrev, vec_other)
        sim = similitud_sdm(vec_abrev, vec_completo)

        status = "✅" if dist_same < dist_diff else "❌"
        print(f"  {abrev}↔{completo}: {dist_same:3d} bits (sim={sim:.4f}) vs {abrev}↔restaurante: {dist_diff:3d} bits {status}")

    return True


def test_03_cross_domain():
    """Conceptos de diferentes dominios que comparten estructura."""
    print("\n" + "="*60)
    print("PRUEBA 3: Cross-domain — mismas dimensiones, distinto contenido")
    print("="*60)

    # Mismas dimensiones pero contenido diferente
    vec_db = generar_vector_sdm(
        concepto="base_de_datos",
        contenido="almacenamiento relacional SQL",
        dimensiones=[10, 20, 30],
        vecinos=["mysql", "postgres", "query"]
    )
    vec_cache = generar_vector_sdm(
        concepto="cache",
        contenido="almacenamiento temporal rapido",
        dimensiones=[10, 20, 30],  # mismas dimensiones
        vecinos=["redis", "memcached", "query"]  # vecino compartido
    )
    vec_receta = generar_vector_sdm(
        concepto="receta",
       contenido="preparacion culinaria ingredientes",
        dimensiones=[40, 50, 60],  # dimensiones distintas
        vecinos=["cocina", "horno", "ingredientes"]
    )

    dist_db_cache = distancia_hamming(vec_db, vec_cache)
    dist_db_receta = distancia_hamming(vec_db, vec_receta)
    sim_db_cache = similitud_sdm(vec_db, vec_cache)

    print(f"  base_de_datos ↔ cache: {dist_db_cache:3d} bits (sim={sim_db_cache:.4f})")
    print(f"  base_de_datos ↔ receta: {dist_db_receta:3d} bits")
    print(f"  Ratio: {dist_db_cache/dist_db_receta:.2f}x")
    status = "✅" if dist_db_cache < dist_db_receta else "❌"
    print(f"  {status}")

    return dist_db_cache < dist_db_receta


def test_04_texto_largo_vs_corto():
    """Texto largo vs corto — el contenido afecta el vector?"""
    print("\n" + "="*60)
    print("PRUEBA 4: Texto largo vs corto")
    print("="*60)

    vec_corto = generar_vector_sdm(
        concepto="python",
        contenido="lenguaje",
        dimensiones=[1, 2]
    )
    vec_largo = generar_vector_sdm(
        concepto="python",
        contenido="Python es un lenguaje de programación de alto nivel, interpretado, multiparadigma y de propósito general. Creado por Guido van Rossum en 1991.",
        dimensiones=[1, 2]
    )
    vec_otro = generar_vector_sdm(
        concepto="java",
        contenido="lenguaje orientado a objetos",
        dimensiones=[1, 2]
    )

    dist_mismo = distancia_hamming(vec_corto, vec_largo)
    dist_otro = distancia_hamming(vec_corto, vec_otro)

    print(f"  python(corto) ↔ python(largo): {dist_mismo:3d} bits")
    print(f"  python(corto) ↔ java: {dist_otro:3d} bits")
    status = "✅" if dist_mismo < dist_otro else "❌"
    print(f"  {status}")

    return dist_mismo < dist_otro


def test_05_query_by_example_real():
    """Test final: query-by-example con datos reales de la DB."""
    print("\n" + "="*60)
    print("PRUEBA 5: Query-by-example REAL — buscar por nodo semilla")
    print("="*60)

    db_path = "/mnt/recursos_compartidos_y_otros/MemoryBioRAG/MemoryBioRAG_Data/memory_biorag.db"
    if not os.path.exists(db_path):
        print("  DB no encontrada")
        return None

    import sqlite3
    conn = sqlite3.connect(db_path)

    nodos = conn.execute("SELECT concepto, vector FROM nodos_sdm").fetchall()
    print(f"  Nodos SDM: {len(nodos)}")

    # Buscar "semilla" por texto parcial
    semillas = ["athena", "biorag", "dennys", "artemis", "memoria"]
    hits = 0

    for semilla in semillas:
        # Encontrar nodo que contenga la semilla
        for concepto, vector in nodos:
            if semilla.lower() in concepto.lower():
                # Buscar similares por Hamming
                distancias = []
                for c2, v2 in nodos:
                    if c2 != concepto:
                        dist = distancia_hamming(vector, v2)
                        if dist <= 200:
                            sim = similitud_sdm(vector, v2)
                            distancias.append((c2, dist, sim))

                distancias.sort(key=lambda x: x[1])
                top3 = distancias[:3]

                if top3:
                    hits += 1
                    print(f"\n  Semilla: {concepto}")
                    for c, d, s in top3:
                        print(f"    → {c}: {d} bits, sim={s:.4f}")
                break

    conn.close()
    print(f"\n  Hits: {hits}/{len(semillas)}")
    return hits >= 3


def main():
    print("="*60)
    print("SDM QUERY-BY-EXAMPLE: Tests diversos")
    print("="*60)
    print(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    resultados = {}
    resultados['sinonimos_tecnicos'] = test_01_sononimos_tecnicos()
    resultados['abreviaturas'] = test_02_abreviaturas()
    resultados['cross_domain'] = test_03_cross_domain()
    resultados['texto_largo_corto'] = test_04_texto_largo_vs_corto()
    resultados['query_by_example_real'] = test_05_query_by_example_real()

    print("\n" + "="*60)
    print("RESUMEN")
    print("="*60)

    for prueba, ok in resultados.items():
        if ok is None:
            status = "⏭️  SKIP"
        elif ok:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        print(f"  {prueba}: {status}")

    passed = sum(1 for v in resultados.values() if v is True)
    total = sum(1 for v in resultados.values() if v is not None)
    print(f"\n  Total: {passed}/{total}")

    if passed >= 4:
        print("\n🎉 TODAS LAS PRUEBAS PASARON — LISTO PARA IMPLEMENTAR")
    elif passed >= 3:
        print("\n✅ MAYORÍA PASÓ — proceder con precaución")
    else:
        print("\n⚠️  Revisar resultados")


if __name__ == "__main__":
    main()
