"""
El MCP ya no le sugiere al agente qué vincular ni qué desvincular.

Por qué: las sugerencias salían de un LIKE '%palabra%' sin orden (casi al azar)
y los modelos pequeños las obedecían creando enlaces malos. Lo mismo con los
avisos de "desvinculá a↔b" en recordar, que podían señalar un enlace hecho por
el agente. Decisión de Dennys (2026-10-24):
  - quitar las sugerencias de vincular y de desvincular;
  - las herramientas vincular y desvincular SE QUEDAN (por si el agente las necesita);
  - vincular_con de aprender NO se toca.
"""

import inspect
import json
import sqlite3

import pytest

BRIDGES = [
    {"text": "corte intempestivo de comunicacion backend", "angle": "sinonimo"},
    {"text": "pagina en blanco sin respuesta del servidor", "angle": "problema"},
    {"text": "reintentos exponenciales y keepalive configurado", "angle": "solucion"},
    {"text": "usuario reportando caida intermitente de la web", "angle": "situacion"},
    {"text": "la web se cae sola y no carga", "angle": "ingenuo"},
]


def _args(concepto, contenido, **extra):
    base = dict(
        concepto=concepto,
        contenido=contenido,
        dimensiones='{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
        syn="servidor,caida,backend,timeout,web,error,red,conexion",
        cat="Lesson",
        bridges=BRIDGES,
        busqueda_previa=True,
        sustantivos_clave="servidor,backend",
    )
    base.update(extra)
    return base


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    db_path = str(tmp_path / "sin_sugerencias.db")
    monkeypatch.setenv("BIORAG_PATH", db_path)
    from core.memory_store import SQLiteMemoryBioRAG
    SQLiteMemoryBioRAG(db_path)
    from core.memory_service import reset_cerebro
    reset_cerebro()
    import mcp_server as m
    mcp = m._build_server()
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    yield tools, db_path
    reset_cerebro()


PROHIBIDAS = (
    "vinculalos",
    "Vinculalos",
    "VINCULALO",
    "biorag_vincular(",
    "desvinculá con",
    "biorag_desvincular(a=",
    "VIOLACIÓN CRÍTICA",
)


def _sin_sugerencias(texto):
    for frase in PROHIBIDAS:
        assert frase not in texto, f"queda una sugerencia: {frase!r}"


def test_aprender_no_sugiere_vincular(ctx):
    tools, _ = ctx
    aprender = tools["aprender"].fn
    # Dos nodos que comparten palabras en el nombre: el código viejo sugería
    # "¿tiene relación con estos nodos? Si sí, vinculalos: ..."
    r1 = aprender(**_args("servidor_backend_caida_web",
                          "El servidor backend se cae cuando la web recibe muchas conexiones."))
    r2 = aprender(**_args("servidor_backend_timeout_red",
                          "Timeout del servidor backend por la red lenta del proveedor."))
    _sin_sugerencias(r1)
    _sin_sugerencias(r2)
    assert "aprendido" in r2


def test_descripciones_y_prompt_sin_sugerencias(ctx):
    tools, _ = ctx
    for nombre in ("aprender", "guardar", "recordar"):
        if nombre in tools:
            _sin_sugerencias(tools[nombre].description or "")
    import core.mcp_server.prompt as prompt
    for nombre, valor in vars(prompt).items():
        if isinstance(valor, str):
            _sin_sugerencias(valor)
            assert "vincular() ANTES de consolidar" not in valor, nombre
    import core.mcp_server.search as search
    _sin_sugerencias(inspect.getsource(search))


def test_herramientas_vincular_y_desvincular_siguen_disponibles(ctx):
    tools, _ = ctx
    assert "vincular" in tools
    assert "desvincular" in tools


def test_vincular_con_sigue_igual(ctx):
    tools, db_path = ctx
    aprender = tools["aprender"].fn
    aprender(**_args("nodo_destino_prueba", "Nodo que ya existe y sera el destino del enlace."))
    raw = aprender(**_args("nodo_origen_prueba",
                           "Nodo nuevo que el agente sabe que se relaciona con el destino.",
                           vincular_con=["nodo_destino_prueba"]))
    assert "Vinculado explícitamente con: nodo_destino_prueba" in raw
    conn = sqlite3.connect(db_path)
    filas = conn.execute(
        "SELECT tipo, peso FROM sinapsis WHERE origen='nodo_origen_prueba' AND destino='nodo_destino_prueba'"
    ).fetchall()
    conn.close()
    assert filas == [("manual", 0.5)]
