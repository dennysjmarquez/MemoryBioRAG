"""
Tests de regresión para el refuerzo Hebbiano multi-padre en BFS (P1 / v31.0+).

Verifica que:
1. El refuerzo Hebbiano multi-padre se propaga efectivamente a los resultados primarios
   cuando un nodo primario es alcanzado como vecino de otro nodo primario.
2. Los resultados primarios preservan el ordenamiento monotónico descendente por score.
3. El refuerzo converge y actualiza nodos de contexto descubiertos por múltiples caminos.
"""

import os
import sys
import sqlite3
import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from core.memory_store import SQLiteMemoryBioRAG


@pytest.fixture
def cerebro_en_memoria(tmp_path):
    """Crea una instancia aislada de SQLiteMemoryBioRAG en memoria/disco temporal."""
    db_file = str(tmp_path / "test_hebbian.db")
    cerebro = SQLiteMemoryBioRAG(db_path=db_file)
    
    # Insertar nodos de prueba en largo_plazo
    cursor = cerebro.cursor
    cursor.execute("""
        INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, asociaciones)
        VALUES ('nodo_alfa', 'Contenido de nodo alfa para pruebas', 1.0, 'activo', 'nodo_beta')
    """)
    cursor.execute("""
        INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, asociaciones)
        VALUES ('nodo_beta', 'Contenido de nodo beta para pruebas', 1.0, 'activo', 'nodo_alfa,nodo_gamma')
    """)
    cursor.execute("""
        INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, asociaciones)
        VALUES ('nodo_gamma', 'Contenido de nodo gamma destino de convergencia', 1.0, 'activo', '')
    """)
    
    # Conectar alfa -> beta (sinapsis fuerte)
    cursor.execute("""
        INSERT INTO sinapsis (origen, destino, peso)
        VALUES ('nodo_alfa', 'nodo_beta', 0.95)
    """)
    
    # Conectar alfa -> gamma y beta -> gamma (convergencia multi-padre hacia gamma)
    cursor.execute("""
        INSERT INTO sinapsis (origen, destino, peso)
        VALUES ('nodo_alfa', 'nodo_gamma', 0.85)
    """)
    cursor.execute("""
        INSERT INTO sinapsis (origen, destino, peso)
        VALUES ('nodo_beta', 'nodo_gamma', 0.80)
    """)
    cerebro.conn.commit()
    
    yield cerebro
    cerebro.conn.close()


def test_refuerzo_hebbiano_propaga_a_primarios(cerebro_en_memoria):
    """Verifica que un nodo primario que recibe sinapsis de otro primario
    ve reflejado su boost en la lista retornada (Fix Bug P1)."""
    cerebro = cerebro_en_memoria
    
    # Tupla estándar de resultados primarios:
    # (concepto, contenido, peso_sinaptico, estado, score_final, asociaciones)
    primario_alfa = ("nodo_alfa", "Contenido alfa", 1.0, "activo", 0.80, "nodo_beta")
    primario_beta = ("nodo_beta", "Contenido beta", 1.0, "activo", 0.60, "nodo_alfa")
    
    pagina_inicial = [primario_alfa, primario_beta]
    
    primarios_out, contextos_out = cerebro._expandir_contexto_bfs(pagina_inicial, depth=1)
    
    # Buscar nodo_beta en primarios_out
    beta_out = next((r for r in primarios_out if r[0] == "nodo_beta"), None)
    assert beta_out is not None, "nodo_beta debe seguir estando presente en primarios"
    
    # El score de beta debe haber recibido el refuerzo Hebbiano (> 0.60 original)
    score_beta_original = primario_beta[4]
    score_beta_nuevo = beta_out[4]
    assert score_beta_nuevo > score_beta_original, (
        f"El score de nodo_beta ({score_beta_nuevo}) debió recibir refuerzo Hebbiano sobre {score_beta_original}"
    )


def test_refuerzo_hebbiano_preserva_monotonia_primarios(cerebro_en_memoria):
    """Verifica que primarios_actualizados mantenga scores descendentes."""
    cerebro = cerebro_en_memoria
    
    # Configuramos scores muy cercanos para que el boost altere el orden relativo
    primario_alfa = ("nodo_alfa", "Contenido alfa", 1.0, "activo", 0.61, "nodo_beta")
    primario_beta = ("nodo_beta", "Contenido beta", 1.0, "activo", 0.60, "nodo_alfa")
    
    pagina_inicial = [primario_alfa, primario_beta]
    primarios_out, _ = cerebro._expandir_contexto_bfs(pagina_inicial, depth=1)
    
    scores = [r[4] for r in primarios_out]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1], f"Violación monotónica en primarios: {scores}"


def test_refuerzo_hebbiano_multi_padre_en_contextos(cerebro_en_memoria):
    """Verifica que un nodo de contexto alcanzado por dos caminos reciba boost."""
    cerebro = cerebro_en_memoria
    
    # Solo alfa y beta son primarios; gamma es un vecino descubierto por ambos
    primario_alfa = ("nodo_alfa", "Contenido alfa", 1.0, "activo", 0.85, "nodo_beta,nodo_gamma")
    primario_beta = ("nodo_beta", "Contenido beta", 1.0, "activo", 0.75, "nodo_gamma")
    
    # Con depth=1, alfa visita gamma, y luego beta también visita gamma (convergencia)
    _, contextos_out = cerebro._expandir_contexto_bfs([primario_alfa, primario_beta], depth=1)
    
    gamma_out = next((r for r in contextos_out if r[0] == "nodo_gamma"), None)
    assert gamma_out is not None, "nodo_gamma debió ser descubierto en contextos"
    
    # Calcular el score base esperado sin convergencia:
    # Por alfa: score_contexto = round(min(1.0, 0.85 * 0.6 + 0.85 * 0.2), 4) = 0.6800
    # Por beta: convergencia multi-padre suma boost_multi
    assert gamma_out[4] > 0.6800, f"nodo_gamma debió recibir boost multi-padre: {gamma_out[4]}"
