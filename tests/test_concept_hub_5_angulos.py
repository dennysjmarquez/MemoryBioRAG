"""
Suite de pruebas obligatorias para Concept Hub con los 5 Ángulos Semánticos (BioRAG v29.1).
Valida los 9 casos del protocolo de integridad y calidad.
"""

import os
import sqlite3
import pytest
import tempfile
from core.concept_hub import (
    crear_tablas,
    crear_hub,
    agregar_bridges,
    agregar_nodos,
    eliminar_hub,
    listar_hubs,
    expandir_query_con_hub,
    validar_bridges,
    ANGULOS_OFICIALES,
)


# ─── FIXTURE ───

@pytest.fixture
def test_db():
    """Crea una base de datos temporal en memoria/archivo con tablas de BioRAG y Concept Hub."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    
    # Esquema mínimo de BioRAG
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS largo_plazo (
            concepto TEXT PRIMARY KEY,
            contenido TEXT,
            peso_sinaptico REAL DEFAULT 1.0,
            estado TEXT DEFAULT 'activo',
            asociaciones TEXT DEFAULT '',
            categoria INTEGER DEFAULT 1,
            creado_en REAL DEFAULT 0,
            sinonimos TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS corto_plazo (
            concepto TEXT PRIMARY KEY,
            contenido TEXT,
            sinonimos TEXT DEFAULT '',
            categoria TEXT DEFAULT 'General',
            dimensiones TEXT DEFAULT '',
            predicados TEXT DEFAULT '',
            valencia_somatica REAL DEFAULT 0.0,
            creado_en REAL DEFAULT 0
        );
    """)
    crear_tablas(conn)
    
    # Insertar algunos nodos canónicos para pruebas
    conn.execute("INSERT INTO largo_plazo (concepto, contenido) VALUES ('nodo_canónico_demo', 'Contenido de prueba para el nodo canónico')")
    conn.execute("INSERT INTO largo_plazo (concepto, contenido) VALUES ('nodo_secundario_demo', 'Contenido de prueba secundario')")
    conn.execute("INSERT INTO corto_plazo (concepto, contenido) VALUES ('nodo_en_corto_plazo', 'Contenido recién percibido')")
    conn.commit()

    yield conn, path

    conn.close()
    if os.path.exists(path):
        os.unlink(path)


# ─── 5 BRIDGES VÁLIDOS PARA REUTILIZAR ───

BRIDGES_5_VALIDOS = [
    {"text": "concepto analogo equivalente", "angle": "sinonimo"},
    {"text": "falla critica de comunicacion", "angle": "problema"},
    {"text": "estrategia de mitigacion y guard", "angle": "solucion"},
    {"text": "desarrollador revisando logs", "angle": "situacion"},
    {"text": "como arreglar la falla rapido", "angle": "ingenuo"},
]


# ─── TESTS ───

def test_01_hub_valido_5_angulos(test_db):
    """1. Un hub válido tiene cinco bridges y cinco ángulos distintos."""
    conn, _ = test_db
    crear_hub(conn, "hub_demo_1", "nodo_canónico_demo", "Descripción del hub")
    
    res = agregar_bridges(conn, "hub_demo_1", BRIDGES_5_VALIDOS)
    assert res["status"] == "ok"
    assert res["bridges_agregados"] == 5

    hubs = listar_hubs(conn)
    hub = next(h for h in hubs if h["hub_id"] == "hub_demo_1")
    assert len(hub["bridges"]) == 5
    angulos_guardados = {b["angle"] for b in hub["bridges"]}
    assert angulos_guardados == set(ANGULOS_OFICIALES)


def test_02_hub_4_bridges_rechazado(test_db):
    """2. Un hub con cuatro bridges es rechazado en la validación."""
    conn, _ = test_db
    crear_hub(conn, "hub_demo_2", "nodo_canónico_demo", "Test 4 bridges")
    
    bridges_4 = BRIDGES_5_VALIDOS[:4]  # Solo 4 bridges
    
    with pytest.raises(ValueError, match="Bridges inválidos"):
        agregar_bridges(conn, "hub_demo_2", bridges_4)


def test_03_bridges_duplicados_o_mismo_angulo_rechazados(test_db):
    """3. Dos bridges con el mismo ángulo son rechazados en la validación."""
    conn, _ = test_db
    crear_hub(conn, "hub_demo_3", "nodo_canónico_demo", "Prueba duplicados ángulo")
    
    # 5 bridges pero con ángulo repetido (dos 'sinonimo')
    bridges_con_angulo_repetido = [
        {"text": "concepto analogo equivalente uno", "angle": "sinonimo"},
        {"text": "concepto analogo equivalente dos", "angle": "sinonimo"},  # mismo ángulo
        {"text": "falla critica de comunicacion", "angle": "problema"},
        {"text": "estrategia de mitigacion y guard", "angle": "solucion"},
        {"text": "desarrollador revisando logs", "angle": "situacion"},
    ]
    # Falta 'ingenuo' y 'sinonimo' repetido
    
    with pytest.raises(ValueError, match="Bridges inválidos"):
        agregar_bridges(conn, "hub_demo_3", bridges_con_angulo_repetido)


def test_04_angle_invalido_rechazado(test_db):
    """4. Un bridge con angle inválido es rechazado por la validación."""
    conn, _ = test_db
    crear_hub(conn, "hub_demo_4", "nodo_canónico_demo")
    
    # Deep copy para no mutar el original
    import copy
    bridges_invalidos = copy.deepcopy(BRIDGES_5_VALIDOS)
    bridges_invalidos[0]["angle"] = "angulo_prohibido"
    
    with pytest.raises(ValueError, match="Bridges inválidos"):
        agregar_bridges(conn, "hub_demo_4", bridges_invalidos)

    # Intentar INSERT directo en SQLite violando CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO concept_hub_bridges (hub_id, bridge_text, angle) VALUES ('hub_demo_4', 'texto test', 'angulo_prohibido')")


def test_05_canonical_node_inexistente_rechazado(test_db):
    """5. Un canonical_node inexistente en largo_plazo y corto_plazo es rechazado antes de insertar."""
    conn, _ = test_db
    with pytest.raises(ValueError, match="no existe ni en largo_plazo ni en corto_plazo"):
        crear_hub(conn, "hub_fantasma", "nodo_que_nadie_conoce_jamas")


def test_06_eliminar_hub_cascade(test_db):
    """6. Eliminar un hub elimina sus bridges y nodos hijos (CASCADE y función explícita)."""
    conn, _ = test_db
    crear_hub(conn, "hub_para_borrar", "nodo_canónico_demo")
    agregar_bridges(conn, "hub_para_borrar", BRIDGES_5_VALIDOS)
    agregar_nodos(conn, "hub_para_borrar", ["nodo_secundario_demo"])
    
    res = eliminar_hub(conn, "hub_para_borrar")
    assert res["status"] == "ok"
    assert res["bridges_eliminados"] == 5
    assert res["nodos_eliminados"] == 2  # canonical + secundario

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM concept_hub_bridges WHERE hub_id = 'hub_para_borrar'")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM concept_hub_nodes WHERE hub_id = 'hub_para_borrar'")
    assert cur.fetchone()[0] == 0


def test_07_actualizar_hub_preserva_bridges(test_db):
    """7. Actualizar un hub con crear_hub() no elimina sus bridges existentes (prueba contra bug de INSERT OR REPLACE)."""
    conn, _ = test_db
    crear_hub(conn, "hub_actualizable", "nodo_canónico_demo", description="Versión 1")
    agregar_bridges(conn, "hub_actualizable", BRIDGES_5_VALIDOS)
    
    # Actualizar descripción o canonical
    crear_hub(conn, "hub_actualizable", "nodo_secundario_demo", description="Versión 2 actualizada")
    
    cur = conn.cursor()
    cur.execute("SELECT bridge_text FROM concept_hub_bridges WHERE hub_id = 'hub_actualizable'")
    bridges_restantes = cur.fetchall()
    assert len(bridges_restantes) == 5


def test_08_query_coincide_bridge_recupera_canonical(test_db):
    """8. Una query coincide con el bridge y recupera el canonical_node."""
    conn, _ = test_db
    crear_hub(conn, "hub_busqueda", "nodo_canónico_demo", description="Hub de recuperación")
    agregar_bridges(conn, "hub_busqueda", BRIDGES_5_VALIDOS)
    
    exp = expandir_query_con_hub("trabajos antes de programar", conn, threshold=0.20)
    assert exp is not None
    assert "nodo_canónico_demo" in exp["canonical_nodes"]
    assert exp["hub_id"] == "hub_busqueda"


def test_09_compatibilidad_formato_legacy(test_db):
    """9. El formato legacy (5 strings) se convierte a 5 ángulos en orden."""
    conn, _ = test_db
    crear_hub(conn, "hub_legacy", "nodo_canónico_demo")
    
    # Formato legacy: exactamente 5 strings → se asignan ángulos en orden
    bridges_strings = [
        "primer puente sinonimo valido",
        "segundo puente problema valido", 
        "tercer puente solucion valido",
        "cuarto puente situacion valido",
        "quinto puente ingenuo valido",
    ]
    res = agregar_bridges(conn, "hub_legacy", bridges_strings)
    assert res["status"] == "ok"
    assert res["bridges_agregados"] == 5
    
    cur = conn.cursor()
    cur.execute("SELECT bridge_text, angle FROM concept_hub_bridges WHERE hub_id = 'hub_legacy' ORDER BY angle")
    rows = cur.fetchall()
    assert len(rows) == 5
    # Verificar que tienen los 5 ángulos oficiales
    angulos = {r[1] for r in rows}
    assert angulos == set(ANGULOS_OFICIALES)


def test_10_validar_bridges_funcion_directa():
    """10. La función validar_bridges se puede usar directamente."""
    validos, rechazados = validar_bridges(BRIDGES_5_VALIDOS, "demo_test")
    assert len(validos) == 5
    assert len(rechazados) == 0
    assert {b["angle"] for b in validos} == set(ANGULOS_OFICIALES)

    # Test con bridges inválidos
    validos, rechazados = validar_bridges([{"text": "corto", "angle": "sinonimo"}], "demo")
    assert len(validos) == 0
    assert len(rechazados) > 0