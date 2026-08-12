"""test_neocortex_teleologico.py — Pruebas Unitarias y de Integración para el Neocórtex Sintético Auto-Teleológico.

Valida:
    1. Autoconocimiento epistémico (sabe lo que sabe / sabe lo que no sabe).
    2. Excepción explícita ante incertidumbre epistémica alta (Cero resultados silenciosos).
    3. Razonamiento por significado puro (PPMI/SVD + grafos sinápticos).
"""

import sys
import os
import sqlite3
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.neocortex_teleologico import NeocortexTeleologico, EpistemicUncertaintyError


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_biorag.db"
    conn = sqlite3.connect(db_file)
    
    # Crear tablas necesarias según el esquema de MemoryBioRAG
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

    # Insertar datos de prueba sintéticos pero válidos
    vec_gato = np.random.randn(100).astype('float32')
    vec_perro = np.random.randn(100).astype('float32')
    vec_auto = np.random.randn(100).astype('float32')

    conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", 
                 ("gat", 10, vec_gato.tobytes()))
    conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", 
                 ("felin", 5, vec_gato.tobytes()))
    conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", 
                 ("automovil", 8, vec_auto.tobytes()))

    conn.execute("INSERT INTO nodos (concepto, vector) VALUES (?, ?)", 
                 ("gato", vec_gato.tobytes()))
    conn.execute("INSERT INTO nodos (concepto, vector) VALUES (?, ?)", 
                 ("automovil", vec_auto.tobytes()))

    conn.execute("INSERT INTO largo_plazo (concepto, contenido, sinonimos) VALUES (?, ?, ?)",
                 ("gato", "El gato es un felino doméstico y mamífero de compañía.", "felino, minino, gatito"))
    conn.execute("INSERT INTO largo_plazo (concepto, contenido, sinonimos) VALUES (?, ?, ?)",
                 ("automovil", "El automóvil es un vehículo de motor y transporte terrestre.", "carro, coche, auto"))

    # Sinapsis Hebbiana
    conn.execute("INSERT INTO sinapsis (origen, destino, peso, tipo) VALUES (?, ?, ?, ?)",
                 ("gato", "automovil", 0.1, "pmi_hebbiano"))

    conn.commit()
    conn.close()
    return str(db_file)


def test_evaluacion_epistemica_conocido(temp_db):
    neocortex = NeocortexTeleologico(temp_db, umbral_confianza=0.3)
    eval_res = neocortex.evaluar_episteme("gato felino")
    assert eval_res["estado"] == "conocido"
    assert eval_res["confianza_epistemica"] >= 0.3
    assert eval_res["incertidumbre"] < 0.7
    print(f"\n[PASS] Evaluacion epistémica conocida: {eval_res}")


def test_evaluacion_epistemica_ignoto(temp_db):
    neocortex = NeocortexTeleologico(temp_db, umbral_confianza=0.8)
    eval_res = neocortex.evaluar_episteme("astrofisica cuantica avanzada")
    assert eval_res["estado"].startswith("ignoto")
    assert eval_res["incertidumbre"] > 0.5
    print(f"\n[PASS] Evaluacion epistémica ignota (sabe que no sabe): {eval_res}")


def test_razonamiento_por_significado_exitoso(temp_db):
    neocortex = NeocortexTeleologico(temp_db, umbral_confianza=0.2)
    resultados = neocortex.razonar_por_significado("gato minino", top_k=1)
    assert len(resultados) == 1
    assert resultados[0]["concepto"] == "gato"
    assert "felino" in resultados[0]["contenido"]
    print(f"\n[PASS] Razonamiento por significado exitoso: {resultados[0]}")


def test_excepcion_incertidumbre_epistemica(temp_db):
    neocortex = NeocortexTeleologico(temp_db, umbral_confianza=0.9)
    try:
        neocortex.razonar_por_significado("materia oscura intergalactica", top_k=1)
        pytest.fail("Se esperaba EpistemicUncertaintyError por ignorancia epistémica.")
    except EpistemicUncertaintyError as e:
        assert e.incertidumbre > 0.5
        print(f"\n[PASS] Excepción de incertidumbre epistémica capturada correctamente: {e}")
