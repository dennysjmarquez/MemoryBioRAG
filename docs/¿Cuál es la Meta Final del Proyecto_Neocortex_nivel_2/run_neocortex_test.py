"""run_neocortex_test.py — Script de ejecución y validación limpia del Neocórtex Sintético Auto-Teleológico.
Cumple con las instrucciones de prueba reproducible (#15, #19, #21).
"""

import sys
import os
import sqlite3
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.neocortex_teleologico import NeocortexTeleologico, EpistemicUncertaintyError


def ejecutar_pruebas():
    print("=" * 70)
    print("INICIANDO PRUEBAS DE VALIDACIÓN: NEOCÓRTEX SINTÉTICO AUTO-TELEOLÓGICO")
    print("=" * 70)

    # Crear base de datos temporal limpia
    db_path = "/tmp/test_biorag_limpio.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE tokens (
            token TEXT PRIMARY KEY,
            freq INTEGER,
            vector BLOB
        )
    """)
    conn.execute("""
        CREATE TABLE nodos (
            concepto TEXT PRIMARY KEY,
            vector BLOB
        )
    """)
    conn.execute("""
        CREATE TABLE largo_plazo (
            concepto TEXT PRIMARY KEY,
            contenido TEXT,
            sinonimos TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE sinapsis (
            origen TEXT,
            destino TEXT,
            peso REAL,
            tipo TEXT
        )
    """)

    # Vectores sintéticos deterministas
    np.random.seed(42)
    vec_gato = np.random.rand(100).astype('float32') + 0.1
    vec_auto = np.random.rand(100).astype('float32') + 0.1

    # Insertar múltiples nodos para que n_docs > freq (asegurando IDF positivo)
    conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", 
                 ("gato", 2, vec_gato.tobytes()))
    conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", 
                 ("felino", 1, vec_gato.tobytes()))
    conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", 
                 ("automovil", 2, vec_auto.tobytes()))

    for i in range(15):
        conn.execute("INSERT INTO nodos (concepto, vector) VALUES (?, ?)", 
                     (f"concepto_{i}", np.random.rand(100).astype('float32').tobytes()))

    conn.execute("INSERT INTO nodos (concepto, vector) VALUES (?, ?)", 
                 ("gato", vec_gato.tobytes()))
    conn.execute("INSERT INTO nodos (concepto, vector) VALUES (?, ?)", 
                 ("automovil", vec_auto.tobytes()))

    conn.execute("INSERT INTO largo_plazo (concepto, contenido, sinonimos) VALUES (?, ?, ?)",
                 ("gato", "El gato es un felino doméstico y mamífero de compañía.", "felino, minino, gatito"))
    conn.execute("INSERT INTO largo_plazo (concepto, contenido, sinonimos) VALUES (?, ?, ?)",
                 ("automovil", "El automóvil es un vehículo de motor y transporte terrestre.", "carro, coche, auto"))

    conn.execute("INSERT INTO sinapsis (origen, destino, peso, tipo) VALUES (?, ?, ?, ?)",
                 ("gato", "automovil", 0.15, "pmi_hebbiano"))

    conn.commit()
    conn.close()

    try:
        neocortex = NeocortexTeleologico(db_path, umbral_confianza=0.2)
        
        # Prueba 1: Evaluación epistémica de concepto conocido
        print("\n[Prueba 1] Evaluando concepto conocido ('gato')...")
        res_conocido = neocortex.evaluar_episteme("gato")
        print(f"Resultado: {res_conocido}")
        assert res_conocido["estado"] == "conocido", f"Estado esperado 'conocido', obtenido {res_conocido['estado']}"
        assert res_conocido["confianza_epistemica"] >= 0.2
        print("-> [ÉXITO] Prueba 1 superada.")

        # Prueba 2: Evaluación epistémica de concepto desconocido (Sabe que no sabe)
        print("\n[Prueba 2] Evaluando concepto desconocido ('astrofisica cuantica')...")
        res_ignoto = neocortex.evaluar_episteme("astrofisica cuantica avanzada")
        print(f"Resultado: {res_ignoto}")
        assert res_ignoto["estado"].startswith("ignoto"), f"Estado esperado 'ignoto', obtenido {res_ignoto['estado']}"
        assert res_ignoto["incertidumbre"] > 0.5
        print("-> [ÉXITO] Prueba 2 superada.")

        # Prueba 3: Razonamiento por significado puro exitoso
        print("\n[Prueba 3] Ejecutando razonamiento por significado ('gato')...")
        resultados = neocortex.razonar_por_significado("gato", top_k=1)
        print(f"Resultados recuperados: {resultados}")
        assert len(resultados) == 1
        assert resultados[0]["concepto"] == "gato"
        print("-> [ÉXITO] Prueba 3 superada.")

        # Prueba 4: Excepción explícita ante incertidumbre (Cero resultados silenciosos)
        print("\n[Prueba 4] Verificando excepción ante consulta fuera de distribución con umbral alto...")
        neocortex_estricto = NeocortexTeleologico(db_path, umbral_confianza=0.95)
        try:
            neocortex_estricto.razonar_por_significado("materia oscura", top_k=1)
            raise AssertionError("Se esperaba EpistemicUncertaintyError")
        except EpistemicUncertaintyError as e:
            print(f"Capturada excepción esperada: {e}")
            print(f"Incertidumbre cuantificada: {e.incertidumbre}, Confianza: {e.confianza}")
            assert e.incertidumbre > 0.5
        print("-> [ÉXITO] Prueba 4 superada.")

        print("\n" + "=" * 70)
        print("TODAS LAS PRUEBAS DEL NEOCÓRTEX SINTÉTICO AUTO-TELEOLÓGICO FINALIZARON CON ÉXITO.")
        print("=" * 70)

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == "__main__":
    ejecutar_pruebas()
