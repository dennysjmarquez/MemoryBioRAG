"""
Tests T3 — Validación fail-fast de sustantivos_clave en _aprender_impl (Spec 001).

RFs cubiertos: RF-1, RF-2, RF-3, RF-9, RF-14, RF-21.

Hecho cuando:
  ✗ sin sustantivos_clave  → error SUSTANTIVOS_CLAVE_AUSENTES, nodo NO guardado
  ✗ 1 término              → SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA
  ✗ 5 términos             → SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA
  ✗ "servidor, s"          → SUSTANTIVOS_CLAVE_FORMATO_INVALIDO (s = 1 char)
  ✗ "server@backend,timeout" → SUSTANTIVOS_CLAVE_FORMATO_INVALIDO (@ no permitido)
  ✗ "s" (1 char)           → SUSTANTIVOS_CLAVE_FORMATO_INVALIDO
  ✓ "servidor,servidor,backend" → dedup "servidor,backend" (2 únicos) → OK, nodo guardado
  ✗ alias guardar sin campo → mismo error SUSTANTIVOS_CLAVE_AUSENTES
"""

import json
import os
import sqlite3
import pytest

# Bridges válidos de ejemplo (5 ángulos requeridos)
VALID_BRIDGES = [
    {"text": "corte intempestivo de comunicacion backend", "angle": "sinonimo"},
    {"text": "pagina en blanco sin respuesta del servidor", "angle": "problema"},
    {"text": "reintentos exponenciales y keepalive configurado", "angle": "solucion"},
    {"text": "usuario reportando caida intermitente de la web", "angle": "situacion"},
    {"text": "la web se cae sola y no carga", "angle": "ingenuo"},
]

# Args base válidos (sustantivos_clave se omite/overridea por test)
_BASE_ARGS = dict(
    concepto="test_t3_nodo",
    contenido="Contenido de prueba para T3 con suficiente texto largo para ser aceptado.",
    dimensiones='{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
    syn="test,t3,validacion,sustantivo,sustantivos,validar,rechazar,aprender",
    cat="Lesson",
    bridges=VALID_BRIDGES,
)


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    """DB temporal + BIORAG_PATH + tools MCP. Al final resetea singleton."""
    db_path = str(tmp_path / "t3_test.db")
    monkeypatch.setenv("BIORAG_PATH", db_path)
    from core.memory_store import SQLiteMemoryBioRAG
    SQLiteMemoryBioRAG(db_path)
    from core.memory_service import reset_cerebro
    reset_cerebro()

    import mcp_server as m
    mcp = m._build_server()
    tools = {t.name: t.fn for t in mcp._tool_manager.list_tools()}
    yield tools, db_path
    reset_cerebro()


# ─── Helpers ────────────────────────────────────────────────────────────────

def _call(tool_name, tools, **overrides):
    """Llama una tool MCP con BASE_ARGS + overrides, retorna dict JSON."""
    args = {**_BASE_ARGS, **overrides}
    raw = tools[tool_name](**args)
    idx = raw.find("{")
    if idx > 0:
        raw = raw[idx:]
    return json.loads(raw)


def _exists(db_path, concepto):
    conn = sqlite3.connect(db_path)
    n = conn.execute(
        "SELECT COUNT(*) FROM corto_plazo WHERE concepto = ?",
        (concepto.lower().strip(),),
    ).fetchone()[0]
    conn.close()
    return n > 0


def _sk(db_path, concepto):
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT sustantivos_clave FROM corto_plazo WHERE concepto = ?",
        (concepto.lower().strip(),),
    ).fetchone()
    conn.close()
    return row[0] if row else None


# ─── Tests T3 — Validación fail-fast ────────────────────────────────────────

class TestT3Validacion:
    """Algoritmo A: ausente → normalizar → dedup → cantidad (2-4) → formato (2-15 chars, [a-z0-9_ñ])."""

    def test_ausente_nodo_no_se_guarda(self, ctx):
        """RF-1, RF-21: sin sustantivos_clave → error + nodo NO existe en DB."""
        tools, db = ctx
        r = _call("aprender", tools, sustantivos_clave=None)
        assert r["status"] == "error"
        assert r["codigo"] == "SUSTANTIVOS_CLAVE_AUSENTES"
        assert "sustantivos_clave" in r["mensaje"].lower()
        assert r["parametro_faltante"] == "sustantivos_clave"
        assert not _exists(db, "test_t3_nodo"), "Nodo no debe existir en corto_plazo"

    def test_un_termino_cantidad_invalida(self, ctx):
        """RF-2, RF-9: 1 término → CANTIDAD_INVALIDA."""
        tools, _ = ctx
        r = _call("aprender", tools, sustantivos_clave="servidor")
        assert r["status"] == "error"
        assert r["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"
        assert r["cantidad_recibida"] == 1

    def test_cinco_terminos_cantidad_invalida(self, ctx):
        """RF-2, RF-9: 5 términos → CANTIDAD_INVALIDA."""
        tools, _ = ctx
        r = _call("aprender", tools, sustantivos_clave="a,b,c,d,e")
        assert r["status"] == "error"
        assert r["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"
        assert r["cantidad_recibida"] == 5

    def test_un_termino_con_arroba_cantidad(self, ctx):
        """'server@backend' = 1 término → CANTIDAD_INVALIDA (viene antes que formato)."""
        tools, _ = ctx
        r = _call("aprender", tools, sustantivos_clave="server@backend")
        assert r["status"] == "error"
        assert r["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"

    def test_formato_con_espacio(self, ctx):
        """RF-3: 'servidor,s' → 's' tiene 1 char → FORMATO_INVALIDO."""
        tools, _ = ctx
        r = _call("aprender", tools, sustantivos_clave="servidor, s")
        assert r["status"] == "error"
        assert r["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"
        assert r["termino_invalido"] == "s"

    def test_formato_caracter_especial(self, ctx):
        """RF-3: 'server@backend,timeout' → '@' no alfanumérico → FORMATO_INVALIDO."""
        tools, _ = ctx
        r = _call("aprender", tools, sustantivos_clave="server@backend,timeout")
        assert r["status"] == "error"
        assert r["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"
        assert r["termino_invalido"] == "server@backend"

    def test_dedup_valido_nodo_se_guarda(self, ctx):
        """RF-14, RF-21: dedup preserva orden → 2 únicos válidos → nodo guardado con valor."""
        tools, db = ctx
        r = _call("aprender", tools, sustantivos_clave="servidor,servidor,backend")
        assert r["status"] == "ok"
        assert r["concepto"] == "test_t3_nodo"
        assert _exists(db, "test_t3_nodo")
        assert _sk(db, "test_t3_nodo") == "servidor,backend"

    def test_guardar_alias_sin_campo(self, ctx):
        """Alias 'guardar' sin sustantivos_clave → SUSTANTIVOS_CLAVE_AUSENTES."""
        tools, db = ctx
        raw = tools["guardar"](**{k: v for k, v in _BASE_ARGS.items()})
        idx = raw.find("{")
        if idx > 0:
            raw = raw[idx:]
        r = json.loads(raw)
        assert r["status"] == "error"
        assert r["codigo"] == "SUSTANTIVOS_CLAVE_AUSENTES"
        assert not _exists(db, "test_t3_nodo")
