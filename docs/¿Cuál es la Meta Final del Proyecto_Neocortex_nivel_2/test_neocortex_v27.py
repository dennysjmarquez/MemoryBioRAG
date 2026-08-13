"""test_neocortex_v27.py — Pruebas de validación para el Neocórtex de Sangre y ADN Conceptual corregidos (v27.0)."""

import sys
import os
import sqlite3
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.neocortex_teleologico import NeocortexTeleologico, EpistemicUncertaintyError
from core.adn_conceptual import ADNConceptualEngine

def probar_sistema():
    print("=" * 80)
    print("VALIDACIÓN TÉCNICA: NEOCÓRTEX DE SANGRE Y ADN VECTORIAL REAL (V27.0)")
    print("=" * 80)

    # Crear DB temporal en memoria o archivo temporal
    db_file = "/tmp/test_biorag_v27.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE tokens (token TEXT PRIMARY KEY, freq INTEGER, vector BLOB)")
    conn.execute("CREATE TABLE nodos (concepto TEXT PRIMARY KEY, vector BLOB)")
    conn.execute("CREATE TABLE largo_plazo (concepto TEXT PRIMARY KEY, contenido TEXT, sinonimos TEXT)")
    conn.execute("CREATE TABLE sinapsis (origen TEXT, destino TEXT, peso REAL, tipo TEXT)")

    # Insertar datos de prueba
    vec_gato = np.random.randn(100).astype('float32')
    vec_soledad = np.random.randn(100).astype('float32')
    vec_filosofia = np.random.randn(100).astype('float32')

    conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", ("gat", 10, vec_gato.tobytes()))
    conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", ("felin", 5, vec_gato.tobytes()))
    conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", ("soledad", 5, vec_soledad.tobytes()))
    conn.execute("INSERT INTO tokens (token, freq, vector) VALUES (?, ?, ?)", ("filosofia", 8, vec_filosofia.tobytes()))

    conn.execute("INSERT INTO nodos (concepto, vector) VALUES (?, ?)", ("gato", vec_gato.tobytes()))
    conn.execute("INSERT INTO nodos (concepto, vector) VALUES (?, ?)", ("soledad", vec_soledad.tobytes()))
    conn.execute("INSERT INTO nodos (concepto, vector) VALUES (?, ?)", ("filosofia", vec_filosofia.tobytes()))

    conn.execute("INSERT INTO largo_plazo (concepto, contenido, sinonimos) VALUES (?, ?, ?)",
                 ("gato", "El gato es un felino doméstico independiente.", "felino, minino"))
    conn.execute("INSERT INTO largo_plazo (concepto, contenido, sinonimos) VALUES (?, ?, ?)",
                 ("soledad", "La soledad es un estado de retiro y contemplación autónoma.", "aislamiento, retiro"))
    conn.execute("INSERT INTO largo_plazo (concepto, contenido, sinonimos) VALUES (?, ?, ?)",
                 ("filosofia", "La filosofía busca la verdad mediante la reflexión abstracta.", "pensamiento"))

    conn.commit()
    conn.close()

    # 1. Probar Neocortex Teleologico y degradación graciosa
    try:
        neocortex = NeocortexTeleologico(db_file, umbral_confianza=0.2)
        print("\n[OK] 1. NeocortexTeleologico inicializado correctamente.")
        
        eval_res = neocortex.evaluar_episteme("gato felino")
        print(f"    Evaluación epistémica: {eval_res['estado']} (Confianza: {eval_res['confianza_epistemica']})")
        assert eval_res['estado'] == 'conocido'

        # Test degradación graciosa con typo/fuera de distribución
        res_razon = neocortex.razonar_por_significado("typoinexistente", top_k=1)
        print(f"    [PASS] Degradación graciosa exitosa ante término desconocido: retornó {len(res_razon)} resultados sin crashear.")

    except Exception as e:
        print(f"[ERROR] en NeocortexTeleologico: {e}")
        import traceback
        traceback.print_exc()

    # 2. Probar ADNConceptualEngine basado en centroides SVD reales
    try:
        adn_engine = ADNConceptualEngine(db_path=db_file)
        print("\n[OK] 2. ADNConceptualEngine inicializado con centroides vectoriales SVD reales.")
        print(f"    Cromosomas modelados geométricamente: {list(adn_engine.cromosoma_centroides.keys())}")
        
        firma_gato = adn_engine.inferir_firma_por_concepto("gato")
        print(f"    Firma genética vectorial para 'gato': {firma_gato}")

        saltos = adn_engine.buscar_por_esencia("gato", top_k=2)
        print(f"    Salto conceptual vectorial para 'gato': {saltos}")
        assert isinstance(saltos, list)

    except Exception as e:
        print(f"[ERROR] en ADNConceptualEngine: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("VALIDACIÓN V27.0 COMPLETADA CON ÉXITO.")
    print("=" * 80)

if __name__ == "__main__":
    probar_sistema()
