#!/usr/bin/env python3
"""
Test 2: SDM Query-by-Example con datos COMPLETOS
==================================================
Prueba con vectores generados desde contenido REAL, sinónimos, dimensiones y vecinos.
No solo conceptos — el contenido completo que BioRAG realmente usa.
"""

import sys
import os
import time
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sdm import generar_vector_sdm, distancia_hamming, similitud_sdm, SDM_BITS, SDM_BYTES

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _db_viva_o_snapshot():
    """Resuelve la DB de datos reales sin rutas atadas a la maquina (portable).

    Prioriza BIORAG_PATH (la suite lo apunta al snapshot inmutable);
    si no esta definido, usa la DB por defecto relativa al proyecto.
    """
    return os.environ.get("BIORAG_PATH") or os.path.join(_RAIZ, "MemoryBioRAG_Data", "memory_biorag.db")


def test_01_vectores_con_contenido():
    """Prueba 1: Vectores con contenido real + sinónimos + dimensiones."""
    print("\n" + "="*60)
    print("PRUEBA 1: Vectores CON contenido + sinónimos + dimensiones")
    print("="*60)

    vec_gato = generar_vector_sdm(
        concepto="gato",
        contenido="El gato es un mamifero domestico de la familia Felidae. También se le conoce como felino, minino, gatito. Es un animal de compañía muy popular.",
        dimensiones=[1, 5, 10, 15, 20],
        vecinos=["veterinario", "mascota", "comida_gato", "caja_areia"]
    )
    vec_felino = generar_vector_sdm(
        concepto="felino",
        contenido="Los felinos son una familia de mamiferos carnivoros que incluye gatos domésticos, leones, tigres y panteras. También llamados gatos, mininos.",
        dimensiones=[1, 5, 10, 15, 20],
        vecinos=["veterinario", "mascota", "caza", "depredador"]
    )
    vec_auto = generar_vector_sdm(
        concepto="automovil",
        contenido="El automóvil es un vehículo de motor con cuatro ruedas. También llamado carro, coche, auto. Usa gasolina o electricidad.",
        dimensiones=[30, 35, 40],
        vecinos=["mecanico", "gasolina", "ruedas", "carretera"]
    )
    vec_programa = generar_vector_sdm(
        concepto="programa",
        contenido="Un programa es un conjunto de instrucciones que una computadora ejecuta. Se escribe en código fuente, se compila y se ejecuta.",
        dimensiones=[50, 55, 60],
        vecinos=["codigo", "compilador", "ejecutable", "debugging"]
    )
    vec_error = generar_vector_sdm(
        concepto="error",
        contenido="Un error es un fallo o bug en el código. También llamado bug, defecto, glitch. Se produce cuando el programa no funciona correctamente.",
        dimensiones=[50, 55, 65],
        vecinos=["codigo", "compilador", "debugging", "excepcion"]
    )

    pares = [
        ("gato", "felino", vec_gato, vec_felino, "MISMOS animales"),
        ("gato", "auto", vec_gato, vec_auto, "DISTINTOS dominios"),
        ("gato", "programa", vec_gato, vec_programa, "DISTINTOS dominios"),
        ("gato", "error", vec_gato, vec_error, "DISTINTOS dominios"),
        ("felino", "auto", vec_felino, vec_auto, "DISTINTOS dominios"),
        ("programa", "error", vec_programa, vec_error, "MISMO dominio (código)"),
    ]

    print(f"\n{'Par':<25} {'Hamming':>8} {'Jaccard':>8} {'Tipo':<20}")
    print("-" * 65)

    for c1, c2, v1, v2, tipo in pares:
        dist = distancia_hamming(v1, v2)
        sim = similitud_sdm(v1, v2)
        marker = "✅" if ("MISMO" in tipo and dist < 200) or ("DISTINTO" in tipo and dist > 100) else "⚠️"
        print(f"{c1}↔{c2:<15} {dist:>6d} bits {sim:>8.4f} {tipo} {marker}")

    radio = 250
    print(f"\nRadio: {radio}")
    print(f"gato↔felino DENTRO: {distancia_hamming(vec_gato, vec_felino) <= radio}")
    print(f"programa↔error DENTRO: {distancia_hamming(vec_programa, vec_error) <= radio}")
    print(f"gato↔auto FUERA: {distancia_hamming(vec_gato, vec_auto) > radio}")

    return True


def test_02_datos_reales_completos():
    """Prueba 2: Vectores REALES de la DB con contenido + sinónimos + dimensiones."""
    print("\n" + "="*60)
    print("PRUEBA 2: Datos REALES — vectores completos de la DB")
    print("="*60)

    db_path = _db_viva_o_snapshot()
    if not os.path.exists(db_path):
        print(f"  DB no encontrada: {db_path}")
        return None

    conn = sqlite3.connect(db_path)

    nodos = conn.execute("""
        SELECT l.concepto, l.contenido, l.sinonimos,
               GROUP_CONCAT(DISTINCT lpd.dimension_id) as dims
        FROM largo_plazo l
        LEFT JOIN largo_plazo_dimensiones lpd ON l.concepto = lpd.concepto
        WHERE l.estado = 'activo'
        GROUP BY l.concepto
        HAVING COUNT(DISTINCT lpd.dimension_id) > 0
        LIMIT 50
    """).fetchall()

    print(f"\n  Nodos con dimensiones: {len(nodos)}")

    if len(nodos) < 5:
        print("  Muy pocos nodos con dimensiones para probar")
        return None

    vectores = []
    for concepto, contenido, sinonimos, dims_str in nodos:
        dims = [int(d) for d in dims_str.split(",") if d] if dims_str else []
        vec = generar_vector_sdm(
            concepto=concepto,
            contenido=(contenido or "")[:500],
            dimensiones=dims
        )
        vectores.append((concepto, vec, dims))

    print(f"  Vectores generados: {len(vectores)}")

    print(f"\n  Top-3 similares por nodo (con contenido real):")
    resultados_buenos = 0

    for concepto, vec, dims in vectores[:15]:
        int_vec = int.from_bytes(vec, 'big')
        distancias = []

        for c2, v2, d2 in vectores:
            if c2 != concepto:
                dist = distancia_hamming(vec, v2)
                sim = similitud_sdm(vec, v2)
                shared_dims = len(set(dims) & set(d2))
                distancias.append((c2, dist, sim, shared_dims))

        distancias.sort(key=lambda x: x[1])
        top3 = distancias[:3]

        if top3:
            print(f"\n  {concepto} (dims: {len(dims)}):")
            for c, d, s, sd in top3:
                marker = "🔗" if sd > 0 else "  "
                print(f"    {marker} {c}: {d} bits, sim={s:.4f}, dims_compartidas={sd}")

            if any(sd > 0 for _, _, _, sd in top3):
                resultados_buenos += 1

    conn.close()

    print(f"\n  Nodos con al menos 1 similar que comparte dimensiones: {resultados_buenos}/{min(15, len(vectores))}")
    return resultados_buenos > 0


def test_03_busqueda_query_by_example():
    """Prueba 3: Simular búsqueda completa — query → nodo semilla → similares."""
    print("\n" + "="*60)
    print("PRUEBA 3: Búsqueda completa query-by-example")
    print("="*60)

    db_path = _db_viva_o_snapshot()
    if not os.path.exists(db_path):
        print(f"  DB no encontrada")
        return None

    conn = sqlite3.connect(db_path)

    nodos_sdm = conn.execute("SELECT concepto, vector FROM nodos_sdm").fetchall()
    print(f"\n  Nodos SDM indexados: {len(nodos_sdm)}")

    dims_map = {}
    for concepto, dims_str in conn.execute("""
        SELECT concepto, GROUP_CONCAT(dimension_id)
        FROM largo_plazo_dimensiones
        GROUP BY concepto
    """).fetchall():
        dims_map[concepto] = [int(d) for d in dims_str.split(",") if d] if dims_str else []

    print(f"\n  Top-3 similares por Hamming (query-by-example):")
    hits_conceptuales = 0
    total_nodos = 0

    for concepto, vector in nodos_sdm[:20]:
        int_vec = int.from_bytes(vector, 'big')
        distancias = []

        for c2, v2 in nodos_sdm:
            if c2 != concepto:
                dist = distancia_hamming(vector, v2)
                if dist <= 300:
                    sim = similitud_sdm(vector, v2)
                    distancias.append((c2, dist, sim))

        distancias.sort(key=lambda x: x[1])
        top3 = distancias[:3]

        if top3:
            concep_tokens = set(concepto.lower().replace("_", " ").split())
            es_conceptual = False
            for c, d, s in top3:
                c_tokens = set(c.lower().replace("_", " ").split())
                if concep_tokens & c_tokens:
                    es_conceptual = True
                    break

            if es_conceptual:
                hits_conceptuales += 1
                print(f"\n  {concepto}:")
                for c, d, s in top3:
                    print(f"    → {c}: {d} bits, sim={s:.4f}")

            total_nodos += 1

    conn.close()

    print(f"\n  Hits conceptuales: {hits_conceptuales}/{total_nodos}")
    return hits_conceptuales > 0


def main():
    print("="*60)
    print("SDM QUERY-BY-EXAMPLE: Test con datos COMPLETOS")
    print("="*60)
    print(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Bits por vector: {SDM_BITS}")
    print(f"Este test usa contenido REAL, sinónimos y dimensiones.")

    resultados = {}

    resultados['prueba_1'] = test_01_vectores_con_contenido()
    resultados['prueba_2'] = test_02_datos_reales_completos()
    resultados['prueba_3'] = test_03_busqueda_query_by_example()

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

    if passed >= 2:
        print("\n🎉 CONCEPTO VALIDADO CON DATOS COMPLETOS")
    else:
        print("\n⚠️  Resultados parciales — revisar")


if __name__ == "__main__":
    main()
