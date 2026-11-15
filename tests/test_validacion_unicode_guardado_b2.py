"""B2: escritura y actualización comparten el formato Unicode de B1."""
import asyncio

import pytest

from core.mcp_server import search, write
from core.mcp_server._shared import _sustantivo_valido
from core.memory_store import (SQLiteMemoryBioRAG, normalizar_sustantivos_clave,
                               normalizar_sustantivos_clave_exacto)
from scripts.evaluar_qa_guardado_nativo_b2 import cargar_entradas, resumen, texto_tool
from scripts.evaluar_qa_multilingue_mcp_e3a import parsear_mcp


# Aíslan la validación de sustantivos. La medición de los 80 usa puentes nativos.
BRIDGES = [
    {"text": "corte intempestivo de comunicacion backend", "angle": "sinonimo"},
    {"text": "pagina en blanco sin respuesta del servidor", "angle": "problema"},
    {"text": "reintentos exponenciales y keepalive configurado", "angle": "solucion"},
    {"text": "usuario reportando caida intermitente de la web", "angle": "situacion"},
    {"text": "la web se cae sola y no carga", "angle": "ingenuo"},
]

CASOS = [
    ("海岸灯塔", "海岸灯塔照亮礁石。", "海岸,灯塔", "灯塔,礁石", "海岸,礁石"),
    ("海辺の灯台", "海辺の灯台は岩場を照らす。", "海辺,灯台", "灯台,岩場", "海辺,岩場"),
    ("바닷가 등대", "바닷가 등대가 암초를 비춘다.", "바닷가,등대", "등대,암초", "바닷가,암초"),
    ("морской маяк", "Морской маяк освещает скалы у берега.", "маяк,скалы", "маяк,берег", "скалы,берег"),
]


def llamar(mcp, nombre, **argumentos):
    """FastMCP valida el esquema y despacha la tool en proceso."""
    return parsear_mcp(texto_tool(asyncio.run(mcp.call_tool(nombre, argumentos))))


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    from core.mcp_server.server import _build_server
    from middleware.auto_guardado import buffer_global

    monkeypatch.setenv("BIORAG_AUTOGUARDADO_HEURISTICO", "0")
    monkeypatch.setenv("BIORAG_DMN_ESTADO_PATH", str(tmp_path / "estado_hormiga.json"))
    monkeypatch.setenv("BIORAG_MCP_AUTO_PARAFRASIS", "0")
    monkeypatch.setenv("BIORAG_MCP_AUTO_DIMS", "0")
    cerebro = SQLiteMemoryBioRAG(str(tmp_path / "b2.db"))
    cerebro._persistente = True
    monkeypatch.setattr(write, "_get_cerebro", lambda: cerebro)
    monkeypatch.setattr(search, "_get_cerebro", lambda: cerebro)
    mcp = _build_server()
    buffer_global.limpiar()
    try:
        yield mcp, cerebro
    finally:
        buffer_global.limpiar()
        cerebro._persistente = False
        cerebro.cerrar_sistema()


@pytest.mark.parametrize("tool_name", ["aprender", "guardar"])
@pytest.mark.parametrize("concepto,contenido,inicial,corto,largo", CASOS)
def test_guardar_y_agregar_nativos_en_corto_y_largo(ctx, monkeypatch, tool_name,
                                                    concepto, contenido, inicial, corto, largo):
    mcp, cerebro = ctx
    llamadas = []

    def observador(termino):
        llamadas.append(termino)
        return _sustantivo_valido(termino)

    monkeypatch.setattr(write, "_sustantivo_valido", observador)
    # Búsqueda real anterior al guardado, con un término válido de los mismos datos.
    previa = llamar(mcp, "recordar", query=concepto, sustantivos_clave=inicial.split(",")[0],
                     deep=False, limite=5)
    assert previa.get("status") != "error" and "resultados" in previa
    args = dict(concepto=concepto, contenido=contenido, dimensiones=None, cat="General",
                bridges=BRIDGES, sustantivos_clave=inicial, busqueda_previa=True)
    guardado = llamar(mcp, tool_name, **args)
    assert guardado["status"] == "ok"
    clave = concepto.lower().replace(" ", "_")
    valor = cerebro.conn.execute("SELECT sustantivos_clave, sustantivos_clave_exactos FROM corto_plazo WHERE concepto=?", (clave,)).fetchone()
    assert valor == (normalizar_sustantivos_clave(inicial), normalizar_sustantivos_clave_exacto(inicial))

    update = llamar(mcp, "agregar_sustantivos", concepto=concepto, sustantivos_clave=corto)
    assert update["status"] == "ok"
    assert update["sustantivos_anteriores"] == normalizar_sustantivos_clave(inicial)
    assert update["sustantivos_nuevos"] == normalizar_sustantivos_clave(corto)
    assert cerebro.conn.execute("SELECT sustantivos_clave, sustantivos_clave_exactos FROM corto_plazo WHERE concepto=?", (clave,)).fetchone() == (normalizar_sustantivos_clave(corto), normalizar_sustantivos_clave_exacto(corto))

    assert cerebro.consolidar_concepto(clave)
    update = llamar(mcp, "agregar_sustantivos", concepto=concepto, sustantivos_clave=largo)
    assert update["status"] == "ok"
    assert update["sustantivos_anteriores"] == normalizar_sustantivos_clave(corto)
    assert update["sustantivos_nuevos"] == normalizar_sustantivos_clave(largo)
    assert cerebro.conn.execute("SELECT sustantivos_clave, sustantivos_clave_exactos FROM largo_plazo WHERE concepto=?", (clave,)).fetchone() == (normalizar_sustantivos_clave(largo), normalizar_sustantivos_clave_exacto(largo))
    esperadas = [term for lista in (inicial, corto, largo)
                 for term in normalizar_sustantivos_clave_exacto(lista).split(",")]
    assert llamadas == esperadas


@pytest.mark.parametrize("termino", ["水", "문", "a", "я", "a" * 16, "海@岸"])
def test_limites_siguen_rechazados_en_aprender_y_agregar(ctx, termino):
    mcp, cerebro = ctx
    args = dict(concepto="nodo_prueba", contenido="Contenido suficiente", dimensiones=None,
                cat="General", bridges=BRIDGES, sustantivos_clave=f"海岸,{termino}",
                busqueda_previa=True)
    antes = llamar(mcp, "aprender", **args)
    assert antes["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"
    assert cerebro.conn.execute("SELECT 1 FROM corto_plazo WHERE concepto='nodo_prueba'").fetchone() is None
    despues = llamar(mcp, "agregar_sustantivos", concepto="nodo_prueba", sustantivos_clave=f"海岸,{termino}")
    assert despues["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"


def test_cantidad_y_deduplicacion_no_cambian(ctx):
    mcp, _ = ctx
    for sk in ("海岸,海岸", ",".join(f"n{i}" for i in range(11))):
        args = dict(concepto="nodo_prueba", contenido="Contenido", dimensiones=None,
                    cat="General", bridges=BRIDGES, sustantivos_clave=sk, busqueda_previa=True)
        assert llamar(mcp, "aprender", **args)["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"
        assert llamar(mcp, "agregar_sustantivos", concepto="nodo_prueba", sustantivos_clave=sk)["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"


def test_insumos_fijos_tienen_ochenta_y_ningun_espacio_forzado_zh_ja():
    filas = cargar_entradas()
    assert len(filas) == 80
    for idioma in ("zh", "ja", "ko", "ru"):
        assert sum(x["idioma"] == idioma for x in filas) == 20
    for x in filas:
        if x["idioma"] in ("zh", "ja"):
            assert all(not any(c.isspace() for c in b["text"]) for b in x["bridges"])


def test_resumen_distingue_guardados_y_primer_rechazo():
    filas = [
        {"idioma": "zh", "id": "zh-01", "busqueda_previa_ejecutada": True,
         "guardado_en_db": False, "confirmado_por_mcp": False, "consolidado": False,
         "primer_rechazo": "BRIDGES_INVALIDOS", "excepcion": None},
        {"idioma": "ru", "id": "ru-01", "busqueda_previa_ejecutada": True,
         "guardado_en_db": True, "confirmado_por_mcp": True, "consolidado": True,
         "primer_rechazo": None, "excepcion": None},
    ]
    r = resumen(filas)
    assert r["zh"]["guardados"] == 0 and r["zh"]["primeros_rechazos"] == {"BRIDGES_INVALIDOS": 1}
    assert r["ru"]["guardados"] == 1 and r["ru"]["primeros_rechazos"] == {}


def test_marcas_exactas_se_cuentan_y_se_consolidan_sin_alterar_columna_legacy(ctx):
    mcp, cerebro = ctx
    args = dict(
        concepto="material_lamina", contenido="Una lámina transparente permite ver el interior.",
        dimensiones=None, cat="General", bridges=BRIDGES,
        sustantivos_clave="ガラス,カラス", busqueda_previa=True,
    )
    respuesta = llamar(mcp, "aprender", **args)
    assert respuesta["status"] == "ok", respuesta
    fila = cerebro.conn.execute(
        "SELECT sustantivos_clave, sustantivos_clave_exactos FROM corto_plazo WHERE concepto='material_lamina'"
    ).fetchone()
    assert fila == ("カラス", "ガラス,カラス")
    assert cerebro.consolidar_concepto("material_lamina")
    fila = cerebro.conn.execute(
        "SELECT sustantivos_clave, sustantivos_clave_exactos FROM largo_plazo WHERE concepto='material_lamina'"
    ).fetchone()
    assert fila == ("カラス", "ガラス,カラス")


def test_actualizar_mcp_sincroniza_columna_exacta(ctx):
    """Actualizar MCP cambia plegado y exacto juntos, sin dejar metadatos obsoletos."""
    mcp, cerebro = ctx
    cerebro.percibir_corto_plazo(
        "nodo_actualizable", "Nodo inicial", sustantivos_clave="カラス",
        sustantivos_clave_exactos="ガラス,カラス",
    )
    assert cerebro.consolidar_concepto("nodo_actualizable")

    resultado = llamar(
        mcp, "actualizar", concepto="nodo_actualizable", sustantivos_clave="perro,gato",
    )
    assert resultado["status"] == "ok", resultado
    fila = cerebro.conn.execute(
        "SELECT sustantivos_clave, sustantivos_clave_exactos FROM largo_plazo "
        "WHERE concepto='nodo_actualizable'"
    ).fetchone()
    assert fila == ("perro,gato", "perro,gato")
