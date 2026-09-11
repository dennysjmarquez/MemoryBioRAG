"""
Tests de verificación para Wake-On-Access en Expansión Sináptica BFS (MemoryBioRAG).

Verifica que:
1. Cuando profundidad == 'profundo':
   - El BFS atraviesa hacia nodos en estado 'dormido'.
   - Los nodos dormidos alcanzados son despertados en la base de datos (estado -> 'activo').
   - Se les aplica potenciación a largo plazo (LTP: peso_sinaptico += 0.15, max 1.0).
   - Se actualiza su marca temporal de ultimo_acceso.
   - En la lista de contextos devuelta aparecen con estado 'activo' y peso actualizado.
2. Cuando profundidad == 'activos':
   - El BFS respeta el filtro estricto (l.estado = 'activo').
   - Los nodos dormidos NO son atravesados ni alterados en la base de datos.
"""

import os
import sys
import time
import pytest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from core.memory_store import SQLiteMemoryBioRAG


@pytest.fixture
def cerebro_con_nodos_dormidos(tmp_path):
    """Crea una instancia aislada de SQLiteMemoryBioRAG con nodos activos y dormidos interconectados."""
    db_file = str(tmp_path / "test_wake_on_access.db")
    cerebro = SQLiteMemoryBioRAG(db_path=db_file)
    cursor = cerebro.cursor

    # Nodo activo inicial (raíz de búsqueda)
    cursor.execute("""
        INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso)
        VALUES ('nodo_raiz_activo', 'Nodo activo principal de busqueda', 0.9, 'activo', 'nodo_vecino_dormido', 1000.0)
    """)

    # Nodo dormido conectado al nodo activo
    cursor.execute("""
        INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso)
        VALUES ('nodo_vecino_dormido', 'Contenido valioso en reposo sinaptico', 0.5, 'dormido', 'nodo_raiz_activo,nodo_subvecino_dormido', 500.0)
    """)

    # Nodo dormido en segundo salto (depth=2)
    cursor.execute("""
        INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado, asociaciones, ultimo_acceso)
        VALUES ('nodo_subvecino_dormido', 'Contenido profundo en segundo nivel', 0.4, 'dormido', 'nodo_vecino_dormido', 400.0)
    """)

    # Sinapsis entre raiz -> vecino_dormido y vecino_dormido -> subvecino_dormido
    cursor.execute("""
        INSERT INTO sinapsis (origen, destino, peso)
        VALUES ('nodo_raiz_activo', 'nodo_vecino_dormido', 0.85)
    """)
    cursor.execute("""
        INSERT INTO sinapsis (origen, destino, peso)
        VALUES ('nodo_vecino_dormido', 'nodo_subvecino_dormido', 0.75)
    """)
    cerebro.conn.commit()
    return cerebro


def test_bfs_profundo_despierta_nodos_dormidos(cerebro_con_nodos_dormidos):
    """Verifica que en modo 'profundo', el BFS despierta nodos dormidos y aplica LTP."""
    cerebro = cerebro_con_nodos_dormidos
    primarios = [("nodo_raiz_activo", "Nodo activo principal de busqueda", 0.9, "activo", 0.95, "")]
    
    t_antes = time.time()
    _, contextos = cerebro.expandir_contexto_vecinos(
        primarios,
        depth=2,
        profundidad="profundo"
    )

    # 1. Verificar que los nodos dormidos fueron alcanzados en el contexto
    conceptos_encontrados = [c[0] for c in contextos]
    assert "nodo_vecino_dormido" in conceptos_encontrados, "El vecino dormido debe ser alcanzado en modo profundo"
    assert "nodo_subvecino_dormido" in conceptos_encontrados, "El sub-vecino dormido a depth 2 debe ser alcanzado"

    # 2. Verificar que en la tupla retornada su estado es 'activo' y peso subió
    item_vecino = next(c for c in contextos if c[0] == "nodo_vecino_dormido")
    assert item_vecino[3] == "activo", f"El estado retornado debe ser 'activo', fue {item_vecino[3]}"
    assert item_vecino[2] == pytest.approx(0.65, 0.01), f"El peso debe haber aumentado en +0.15 (0.50 -> 0.65), fue {item_vecino[2]}"

    # 3. Verificar persistencia real en la base de datos (wake-on-access)
    cursor = cerebro.conn.execute("SELECT estado, peso_sinaptico, ultimo_acceso FROM largo_plazo WHERE concepto = 'nodo_vecino_dormido'")
    row = cursor.fetchone()
    assert row[0] == "activo", "En base de datos el estado debe haber mutado a 'activo'"
    assert row[1] == pytest.approx(0.65, 0.01), "En base de datos el peso sináptico debe ser 0.65 (LTP aplicado)"
    assert row[2] >= t_antes, "En base de datos el ultimo_acceso debe haberse actualizado"

    # Verificar segundo nivel en base de datos
    cursor_sub = cerebro.conn.execute("SELECT estado, peso_sinaptico FROM largo_plazo WHERE concepto = 'nodo_subvecino_dormido'")
    row_sub = cursor_sub.fetchone()
    assert row_sub[0] == "activo", "El segundo nivel también debe despertar"
    assert row_sub[1] == pytest.approx(0.55, 0.01), "El segundo nivel debe tener LTP (0.40 -> 0.55)"


def test_bfs_activos_no_toca_nodos_dormidos(cerebro_con_nodos_dormidos):
    """Verifica que en modo 'activos', el BFS ignora y no despierta nodos dormidos."""
    cerebro = cerebro_con_nodos_dormidos
    primarios = [("nodo_raiz_activo", "Nodo activo principal de busqueda", 0.9, "activo", 0.95, "")]
    
    _, contextos = cerebro.expandir_contexto_vecinos(
        primarios,
        depth=2,
        profundidad="activos"
    )

    # 1. En modo activos, los dormidos no deben aparecer en contextos
    conceptos_encontrados = [c[0] for c in contextos]
    assert "nodo_vecino_dormido" not in conceptos_encontrados, "El vecino dormido NO debe ser alcanzado en modo activos"
    assert "nodo_subvecino_dormido" not in conceptos_encontrados

    # 2. En la base de datos deben permanecer inalterados
    cursor = cerebro.conn.execute("SELECT estado, peso_sinaptico, ultimo_acceso FROM largo_plazo WHERE concepto = 'nodo_vecino_dormido'")
    row = cursor.fetchone()
    assert row[0] == "dormido", "En base de datos el estado debe seguir siendo 'dormido'"
    assert row[1] == pytest.approx(0.50, 0.01), "El peso sináptico NO debe haber mutado"
    assert row[2] == pytest.approx(500.0, 0.01), "El timestamp de ultimo_acceso NO debe haber mutado"
