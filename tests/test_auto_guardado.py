"""Autoguardado (middleware/auto_guardado.py) — Fase 1: cortar la entrada de basura.

Antes: cada herramienta del MCP alimentaba un búfer (consultas de recordar,
salida de consola del sueño, "activos:N dormidos:M", "a <--> b", ecos de
aprender) y un disparador por SUBCADENAS lo guardaba como nodo con la clave
"3 primeras palabras largas". Ahora: heurístico apagado por defecto, salidas de
máquina fuera del búfer, contexto_fin guarda solo el resumen y las palabras
clave se comparan como palabra completa.
"""
import json
import time

import pytest

from middleware import auto_guardado as ag
from core.memory_store import SQLiteMemoryBioRAG

SALIDA_SUENO = (
    "--- Iniciando Ciclo de Consolidación (Sueño) ---\n"
    "[Inferencia Transitiva] 8156 sinapsis latentes\n[SDM] 543 vectores"
)


@pytest.fixture(autouse=True)
def _buffer_limpio(monkeypatch):
    monkeypatch.delenv("BIORAG_AUTOGUARDADO_HEURISTICO", raising=False)
    ag.buffer_global.limpiar()
    yield
    ag.buffer_global.limpiar()


@pytest.fixture
def cerebro(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "autoguardado.db"))
    yield c
    c.cerrar_sistema()


def _n_corto(c):
    return c.cursor.execute("SELECT COUNT(*) FROM corto_plazo").fetchone()[0]


def _n_largo(c):
    return c.cursor.execute("SELECT COUNT(*) FROM largo_plazo").fetchone()[0]


# ── Flag y búfer ─────────────────────────────────────────────────────────────

def test_heuristico_apagado_por_defecto():
    assert ag.autoguardado_heuristico_activo() is False


def test_por_defecto_no_guarda_nada_por_herramienta(cerebro):
    # Texto largo, con muchas palabras disparadoras, desde acciones que antes guardaban.
    ag.registrar_accion("comunicar", "Athena -> Artemis: lección importante, error clave, siempre evitar esto, regla nueva")
    ag.registrar_accion("leer_mensajes", "aprendí una solución crítica: nunca usar REPLACE, conclusión importante")
    assert ag.analizar_y_autoguardar(cerebro) is None
    assert _n_corto(cerebro) == 0


@pytest.mark.parametrize("accion,texto", [
    ("recordar", "hijo Dennys familia hijo nombre padre importante"),
    ("aprender", "clave_x: contenido que ya se guardó como nodo, lección importante"),
    ("consolidar", SALIDA_SUENO),
    ("introspeccion", "activos:480 dormidos:15"),
    ("vincular", "nodo_a <--> nodo_b"),
    ("mapear", "mapa completo del grafo"),
])
def test_salidas_de_maquina_y_consultas_no_entran_al_buffer(accion, texto):
    ag.registrar_accion(accion, texto)
    entrada = ag.buffer_global.obtener()[-1]
    assert entrada["accion"] == accion
    assert entrada["texto"] == ""


def test_mensajes_entre_agentes_si_entran_al_buffer():
    ag.registrar_accion("comunicar", "Athena -> Artemis: hola")
    assert ag.buffer_global.obtener()[-1]["texto"] == "Athena -> Artemis: hola"


# ── Palabra completa, no subcadena ───────────────────────────────────────────

@pytest.mark.parametrize("texto,termino", [
    ("el resultado fue normal", "mal"),
    ("también funciona", "bien"),
    ("revisar sustantivos_clave del nodo", "clave"),
    ("un animal doméstico", "mal"),
])
def test_no_coincide_por_subcadena(texto, termino):
    assert ag._contiene_termino(texto, termino) is False


@pytest.mark.parametrize("texto,termino", [
    ("esto salió mal", "mal"),
    ("la clave es esta", "clave"),
    ("lección: no usar replace", "lección"),
    ("es un nuevo patrón de diseño", "nuevo patrón"),
])
def test_coincide_por_palabra_completa(texto, termino):
    assert ag._contiene_termino(texto, termino) is True


def test_extraer_categoria_ignora_subcadenas():
    # "regla" dentro de "arreglado" ya no clasifica como Principle.
    assert ag._extraer_categoria("quedó arreglado y normal") == "General"
    assert ag._extraer_categoria("una regla nueva") == "Principle"


# ── Comportamiento histórico detrás del flag ─────────────────────────────────

def test_flag_on_conserva_guardado_heuristico(cerebro, monkeypatch):
    monkeypatch.setenv("BIORAG_AUTOGUARDADO_HEURISTICO", "1")
    ag.registrar_accion(
        "comunicar",
        "Despliegue productivo: aprendí una lección importante sobre migraciones de esquema en SQLite",
    )
    r = ag.analizar_y_autoguardar(cerebro)
    assert r is not None
    assert r["categoria"] == "Lesson"
    assert _n_corto(cerebro) == 1


def test_flag_on_nunca_guarda_salida_del_sueno(cerebro, monkeypatch):
    monkeypatch.setenv("BIORAG_AUTOGUARDADO_HEURISTICO", "1")
    ag.registrar_accion("consolidar", SALIDA_SUENO + " importante error clave " * 5)
    assert ag.analizar_y_autoguardar(cerebro) is None
    assert _n_corto(cerebro) == 0


# ── contexto_fin: solo el resumen ────────────────────────────────────────────

def test_fin_sesion_guarda_solo_el_resumen(cerebro):
    ag.registrar_accion("recordar", "hijo Dennys familia hijo nombre importante")
    ag.registrar_accion("consolidar", SALIDA_SUENO)
    r = ag.autoguardar_fin_sesion(cerebro, "Athena OEC", "Corregimos consolidar_concepto y añadimos tests")
    fecha = time.strftime("%Y%m%d")
    assert r["concepto"] == f"sesion_athena_oec_{fecha}"
    contenido, sinonimos = cerebro.cursor.execute(
        "SELECT contenido, sinonimos FROM corto_plazo WHERE concepto = ?", (r["concepto"],)
    ).fetchone()
    assert "Corregimos consolidar_concepto y añadimos tests" in contenido
    assert "hijo" not in contenido and "Iniciando Ciclo" not in contenido
    assert "auto_guardado" in sinonimos.split(",")
    assert _n_corto(cerebro) == 1
    assert ag.buffer_global.obtener() == []


@pytest.mark.parametrize("resumen", ["", "   ", None])
def test_fin_sesion_sin_resumen_no_guarda(cerebro, resumen):
    ag.registrar_accion("comunicar", "lección importante: error clave, siempre evitar")
    assert ag.autoguardar_fin_sesion(cerebro, "athena", resumen) is None
    assert _n_corto(cerebro) == 0


def test_fin_sesion_mismo_dia_fusiona_en_un_nodo(cerebro):
    for resumen in ("primer cierre de la sesión", "segundo cierre de la sesión"):
        r = ag.autoguardar_fin_sesion(cerebro, "athena", resumen)
        assert cerebro.consolidar_concepto(r["concepto"]) is True
    filas = cerebro.cursor.execute(
        "SELECT contenido FROM largo_plazo WHERE concepto LIKE 'sesion_athena_%'"
    ).fetchall()
    assert len(filas) == 1
    assert "primer cierre" in filas[0][0] and "segundo cierre" in filas[0][0]


# ── Integración con las tools MCP ────────────────────────────────────────────

class _MCPStub:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def deco(fn):
            self.tools[name] = fn
            return fn
        return deco


def test_tool_contexto_fin_guarda_solo_resumen(tmp_path, monkeypatch):
    from core.memory_service import get_cerebro, reset_cerebro
    from core.mcp_server import session
    from core.mcp_server._shared import _interceptar

    monkeypatch.setenv("BIORAG_PATH", str(tmp_path / "mcp.db"))
    monkeypatch.setenv("BIORAG_NO_LOG", "1")
    reset_cerebro()
    try:
        c = get_cerebro()
        n_antes = _n_largo(c)
        stub = _MCPStub()
        session.register(stub)
        # Lo que antes acababa como nodo basura:
        _interceptar("recordar", "hijo Dennys familia hijo nombre padre importante error clave", c)
        _interceptar("consolidar", SALIDA_SUENO, c)
        _interceptar("introspeccion", "activos:480 dormidos:15", c)
        assert _n_corto(c) == 0

        out = json.loads(stub.tools["contexto_fin"](agente="athena", resumen="Sesión de prueba del autoguardado"))
        assert out["status"] == "ok"
        assert out["auto_guardado"]["concepto"].startswith("sesion_athena_")
        conceptos = [r[0] for r in c.cursor.execute("SELECT concepto FROM largo_plazo").fetchall()]
        assert _n_largo(c) == n_antes + 1
        assert out["auto_guardado"]["concepto"] in conceptos
        assert not any(k.startswith(("hijo_", "iniciando_", "activos_")) for k in conceptos)
    finally:
        reset_cerebro()
