"""
Tests T5 — `biorag_recordar` con `sustantivos_clave` (Spec 001).

RFs cubiertos: RF-5 (BM25 4 pesos), RF-18 (acentos en queries), RF-19 (boost),
RF-20 (validación de formato).

Hecho cuando:
  ✓ `recordar` con `sustantivos_clave` opcional boostea nodos cuyo sustantivos_clave coincide
  ✓ Query con tilde ("conexión") matchea nodo con "conexion" almacenado sin tilde (RF-18)
  ✓ `recordar(sustantivos_clave="x@y")` → error SUSTANTIVOS_CLAVE_FORMATO_INVALIDO, búsqueda NO se ejecuta
  ✓ `recordar(sustantivos_clave="")` → búsqueda normal (sin boost)
  ✓ BM25 con 4 pesos prioriza match en columna sustantivos_clave (RF-5)
"""

import json
import sqlite3
import pytest


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    """DB temporal + BIORAG_PATH + tools MCP. Resetea singleton al inicio y fin."""
    db_path = str(tmp_path / "t5_test.db")
    monkeypatch.setenv("BIORAG_PATH", db_path)
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path)
    cerebro.cerrar_sistema()

    from core.memory_service import reset_cerebro
    reset_cerebro()

    import mcp_server as m
    mcp = m._build_server()
    tools = {t.name: t.fn for t in mcp._tool_manager.list_tools()}
    yield tools, db_path
    reset_cerebro()


def _insert_lp(db_path, concepto, contenido="Contenido de prueba", sk=""):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO largo_plazo (concepto, contenido, categoria, estado, peso_sinaptico, sustantivos_clave) "
        "VALUES (?, ?, 1, 'activo', 1.0, ?)",
        (concepto, contenido, sk),
    )
    conn.commit()
    conn.close()


def _raw_json(raw):
    """Extraer el JSON de la respuesta de la tool."""
    start = raw.find("{")
    return json.loads(raw[start:]) if start >= 0 else json.loads(raw)


class TestT5BM25CuatroPesos:
    """RF-5: el 4° peso de bm25() actúa sobre la columna sustantivos_clave."""

    def test_bm25_4_pesos_prioriza_sustantivos_clave(self, ctx):
        tools, db_path = ctx
        # Nodo A: su sustantivos_clave contiene el término buscado en la columna dedicada
        _insert_lp(db_path, "nodo_con_sustantivo", contenido="problema servidor lento", sk="servidor,timeout")
        # Nodo B: idéntico en contenido pero sin sustantivo
        _insert_lp(db_path, "nodo_sin_sustantivo", contenido="problema servidor lento", sk="")

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT l.concepto, bm25(largo_plazo_fts, 5.0, 1.0, 2.0, 4.0) AS b "
            "FROM largo_plazo_fts f CROSS JOIN largo_plazo l ON l.rowid = f.rowid "
            "WHERE largo_plazo_fts MATCH 'servidor' "
            "ORDER BY b "
        ).fetchall()
        conn.close()
        conceptos = [r[0] for r in row]
        # Desde el 4° peso (correlación inversa bm25): el nodo con match en la columna
        # sustantivos_clave debe rankear mejor (b menor / primero) que el que solo matchea contenido.
        assert "nodo_con_sustantivo" in conceptos
        assert conceptos.index("nodo_con_sustantivo") <= conceptos.index("nodo_sin_sustantivo")


class TestT5RecordarSustantivosBoost:
    """RF-19: `recordar` con `sustantivos_clave` boostea nodos por lo que TRATAN.

    El FTS indexa la columna sustantivos_clave con peso BM25 4.0x (RF-4/RF-5),
    así que una query que toca ese campo ya matchea el nodo. El valor del boost
    RF-19 es el caso complementario: la query NO cubre el sustantivo del nodo,
    pero el agente pasa los términos temáticos explícitos → el match en la
    columna dedicada sube ese nodo al top (rompe el empate BM25).

    Para que la normalización min-max del scoring preserve discriminación,
    necesitamos >=5 candidatos (el pool mínimo para que bm25 norm sea
    significativamente distinto entre el mejor y el segundo mejor).
    """

    def test_recordar_con_sustantivos_clave_subiria_top(self, ctx):
        tools, db_path = ctx
        # Pool de 5+ candidatos: contenido idéntico = mismo bm25 base.
        # nodo_boost "trata" de timeout/servidor; otros no.
        for i in range(4):
            _insert_lp(db_path, f"nodo_base_{i}", contenido="establecer conexion segura", sk="")
        _insert_lp(db_path, "nodo_boost", contenido="establecer conexion segura", sk="timeout,servidor")

        # Sin boost: todos matchean por contenido → ranking estable (empate, orden motor)
        raw = tools["recordar"](query="conexion")
        res = _raw_json(raw)
        assert "resultados" in res
        sin_boost = [r["concepto"] for r in res.get("resultados", [])]
        assert len(sin_boost) >= 5

        # Con boost: los términos temáticos suben nodo_boost al top por su columna.
        raw = tools["recordar"](query="conexion", sustantivos_clave="timeout,servidor")
        res = _raw_json(raw)
        assert "resultados" in res
        con_boost = [r["concepto"] for r in res.get("resultados", [])]
        # nodo_boost debe quedar primero (el boost agrega match en columna dedicada → bm25 mejor)
        assert con_boost and con_boost[0] == "nodo_boost", (
            f"Se esperaba nodo_boost en top-1, se obtuvo: {con_boost[:3]}"
        )


class TestT5AcentosEnQuery:
    """RF-18: query con tilde matchea contenido almacenado sin tilde."""

    def test_query_con_tilde_matchea_sin_tilde(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_conexion", contenido="establecer conexion con base de datos", sk="conexion,base_datos")

        raw = tools["recordar"](query="conexión")
        res = _raw_json(raw)
        assert "resultados" in res
        assert any(r["concepto"] == "nodo_conexion" for r in res.get("resultados", []))


class TestT5RecordarValidacion:
    """RF-20: `recordar` valida formato de sustantivos_clave; error → búsqueda NO se ejecuta."""

    def test_formato_invalido_no_ejecuta_busqueda(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        raw = tools["recordar"](query="algoritmo", sustantivos_clave="x@y")
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"
        # Búsqueda NO se ejecutó: no hay resultados aunque el nodo exista y matchee
        assert "resultados" not in res
        assert "total" not in res

    def test_vacio_es_busqueda_normal(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        raw = tools["recordar"](query="algoritmo", sustantivos_clave="")
        res = _raw_json(raw)
        assert "resultados" in res
        assert any(r["concepto"] == "nodo_existente" for r in res.get("resultados", []))

    def test_omitido_es_busqueda_normal(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        raw = tools["recordar"](query="algoritmo")
        res = _raw_json(raw)
        assert "resultados" in res
        assert any(r["concepto"] == "nodo_existente" for r in res.get("resultados", []))