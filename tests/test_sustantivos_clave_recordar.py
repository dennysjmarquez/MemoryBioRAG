"""
Tests T5 — `biorag_recordar` y `biorag_buscar` con `sustantivos_clave` (Spec 001).

RFs cubiertos: RF-5 (BM25 4 pesos), RF-18 (acentos en queries), RF-19 (boost y obligatoriedad condicional),
RF-20 (validación de límites de cantidad 1-10 y formato).

Hecho cuando:
  ✓ `recordar` con `sustantivos_clave` boostea nodos cuyo sustantivos_clave coincide (RF-19)
  ✓ Query con tilde ("conexión") matchea nodo con "conexion" almacenado sin tilde (RF-18)
  ✓ `recordar` con formato inválido ("x@y") → error SUSTANTIVOS_CLAVE_FORMATO_INVALIDO, búsqueda NO se ejecuta (RF-20)
  ✓ Búsqueda textual sin `sustantivos_clave` (omitido o vacío) → error SUSTANTIVOS_CLAVE_REQUERIDOS antes de abrir el motor (RF-19)
  ✓ Rango técnico 1 a 10 términos admitido; >10 términos rechazado con SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA (RF-20)
  ✓ Rechazo fail-fast ocurre antes de llamar a `_get_cerebro()`
  ✓ Excepciones legítimas: consultas cronológicas puras y dimensionales puras permitidas sin `sustantivos_clave`
  ✓ `buscar` comparte exactamente el mismo comportamiento, validación y parámetros que `recordar`
  ✓ Esquema MCP expone `sustantivos_clave` con la descripción canónica unificada
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
    """RF-19: `recordar` con `sustantivos_clave` boostea nodos por lo que TRATAN."""

    def test_recordar_con_sustantivos_clave_subiria_top(self, ctx):
        tools, db_path = ctx
        # Pool de 5+ candidatos: contenido idéntico = mismo bm25 base.
        # nodo_boost "trata" de timeout/servidor; otros no.
        for i in range(4):
            _insert_lp(db_path, f"nodo_base_{i}", contenido="establecer conexion segura", sk="")
        _insert_lp(db_path, "nodo_boost", contenido="establecer conexion segura", sk="timeout,servidor")

        # Sin boost temático en nodo_boost: pasamos sustantivos neutros de red
        raw = tools["recordar"](query="conexion", sustantivos_clave="red,seguridad")
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

        raw = tools["recordar"](query="conexión", sustantivos_clave="conexion,base_datos")
        res = _raw_json(raw)
        assert "resultados" in res
        assert any(r["concepto"] == "nodo_conexion" for r in res.get("resultados", []))


class TestT5RecordarValidacion:
    """Validación del protocolo cognitivo obligatorio de sustantivos_clave en recordar y buscar."""

    def test_rechazo_no_llama_get_cerebro(self, ctx, monkeypatch):
        """Aureon Mandate: ante validación fallida, _get_cerebro() NUNCA debe ser llamado."""
        tools, _ = ctx
        import core.mcp_server.search as mcp_search

        def _fail_on_call():
            pytest.fail("VIOLACIÓN: _get_cerebro() fue invocado antes de completar la validación fail-fast!")

        monkeypatch.setattr(mcp_search, "_get_cerebro", _fail_on_call)

        # 1. Parámetro ausente
        raw1 = tools["recordar"](query="algoritmo")
        res1 = _raw_json(raw1)
        assert res1["status"] == "error"
        assert res1["codigo"] == "SUSTANTIVOS_CLAVE_REQUERIDOS"

        # 2. Formato inválido
        raw2 = tools["recordar"](query="algoritmo", sustantivos_clave="inv@lid")
        res2 = _raw_json(raw2)
        assert res2["status"] == "error"
        assert res2["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"

        # 3. Cantidad inválida (>10)
        raw3 = tools["recordar"](query="algoritmo", sustantivos_clave="a,b,c,d,e,f,g,h,i,j,k")
        res3 = _raw_json(raw3)
        assert res3["status"] == "error"
        assert res3["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"

    def test_formato_invalido_no_ejecuta_busqueda(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        raw = tools["recordar"](query="algoritmo", sustantivos_clave="x@y")
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"
        assert "resultados" not in res
        assert "total" not in res

    def test_vacio_falla_con_sustantivos_clave_requeridos(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        raw = tools["recordar"](query="algoritmo", sustantivos_clave="")
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "SUSTANTIVOS_CLAVE_REQUERIDOS"
        assert "resultados" not in res

    def test_omitido_falla_con_sustantivos_clave_requeridos(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        raw = tools["recordar"](query="algoritmo")
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "SUSTANTIVOS_CLAVE_REQUERIDOS"
        assert "resultados" not in res

    def test_buscar_sin_sustantivos_clave_falla(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        raw = tools["buscar"](query="algoritmo")
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "SUSTANTIVOS_CLAVE_REQUERIDOS"
        assert "resultados" not in res

    def test_cantidades_admitidas_recordar(self, ctx):
        """Verifica que 1, 2, 4, 5, 6 y 10 términos sean aceptados en recordar."""
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        casos = [
            "algoritmo",                                                      # 1 término (atómico)
            "algoritmo,busqueda",                                             # 2 términos (pauta)
            "algoritmo,busqueda,optimizacion,rendimiento",                    # 4 términos (pauta)
            "algoritmo,busqueda,optimizacion,rendimiento,complejidad",        # 5 términos
            "algoritmo,busqueda,optimizacion,rendimiento,complejidad,grafo",  # 6 términos
            "t1,t2,t3,t4,t5,t6,t7,t8,t9,t10",                                # 10 términos (máximo técnico)
        ]
        for sk in casos:
            raw = tools["recordar"](query="algoritmo", sustantivos_clave=sk)
            res = _raw_json(raw)
            assert "resultados" in res, f"Falló para cantidad de términos en sustantivos_clave: {sk}"
            assert res.get("status") != "error"

    def test_cantidades_admitidas_buscar(self, ctx):
        """Verifica que el alias buscar admita 1 y 6 términos igualmente."""
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        for sk in ("algoritmo", "t1,t2,t3,t4,t5,t6"):
            raw = tools["buscar"](query="algoritmo", sustantivos_clave=sk)
            res = _raw_json(raw)
            assert "resultados" in res
            assert res.get("status") != "error"

    def test_mas_de_diez_sustantivos_falla_recordar(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        once_terminos = "t1,t2,t3,t4,t5,t6,t7,t8,t9,t10,t11"
        raw = tools["recordar"](query="algoritmo", sustantivos_clave=once_terminos)
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"
        assert "resultados" not in res

    def test_mas_de_diez_sustantivos_falla_buscar(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        once_terminos = "t1,t2,t3,t4,t5,t6,t7,t8,t9,t10,t11"
        raw = tools["buscar"](query="algoritmo", sustantivos_clave=once_terminos)
        res = _raw_json(raw)
        assert res["status"] == "error"
        assert res["codigo"] == "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA"
        assert "resultados" not in res

    def test_duplicados_deduplicados_y_contados_una_vez(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_existente", contenido="algoritmo de busqueda rapido", sk="")

        # Entrada con duplicados: 3 términos recibidos pero solo 2 únicos
        raw = tools["recordar"](query="algoritmo", sustantivos_clave="algoritmo,algoritmo,busqueda")
        res = _raw_json(raw)
        assert "resultados" in res
        assert res.get("status") != "error"

    def test_recordar_cronologico_sin_sustantivos_permitido(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_reciente", contenido="evento temporal registrado", sk="")

        # Consulta puramente cronológica (sin query) es una excepción legítima
        raw = tools["recordar"](dias=1)
        res = _raw_json(raw)
        assert "resultados" in res
        assert res.get("status") != "error"

    def test_recordar_dimensional_sin_sustantivos_permitido(self, ctx):
        tools, db_path = ctx
        _insert_lp(db_path, "nodo_dim", contenido="concepto puramente ontologico", sk="")

        # Consulta puramente dimensional (sin query) es una excepción legítima
        raw = tools["recordar"](dimensiones='{"escala_abstraccion":["principio"]}')
        res = _raw_json(raw)
        assert "resultados" in res
        assert res.get("status") != "error"


class TestT5EsquemaMCP:
    """Verifica el esquema MCP expuesto para búsqueda y escritura, y su contrato."""

    def test_esquema_mcp_expone_sustantivos_clave_recordar_y_buscar(self):
        import mcp_server as m
        mcp = m._build_server()
        tool_map = {t.name: t for t in mcp._tool_manager.list_tools()}
        assert "recordar" in tool_map
        assert "buscar" in tool_map

        for name in ("recordar", "buscar"):
            tool = tool_map[name]
            schema = tool.parameters
            props = schema.get("properties", {})
            assert "sustantivos_clave" in props, f"{name} debe exponer sustantivos_clave en su esquema MCP"
            desc = props["sustantivos_clave"].get("description", "")
            assert "NÚCLEO TEMÁTICO DE LA INTENCIÓN" in desc
            assert "PROHIBICIÓN DE ADIVINAR EL OBJETIVO" in desc

    def test_esquema_mcp_expone_sustantivos_clave_aprender_y_guardar(self):
        """Verifica que aprender y guardar expongan sustantivos_clave con descripción canónica."""
        import mcp_server as m
        mcp = m._build_server()
        tool_map = {t.name: t for t in mcp._tool_manager.list_tools()}
        assert "aprender" in tool_map
        assert "guardar" in tool_map

        for name in ("aprender", "guardar"):
            tool = tool_map[name]
            schema = tool.parameters
            props = schema.get("properties", {})
            assert "sustantivos_clave" in props, f"{name} debe exponer sustantivos_clave en su esquema MCP"
            desc = props["sustantivos_clave"].get("description", "")
            assert "SUSTANTIVOS CLAVE — QUÉ SON Y PARA QUÉ SIRVEN" in desc
            assert "REGLA SOBRE EL NOMBRE DEL NODO" in desc

    def test_aprender_y_guardar_rechazo_ejecucion_sustantivos_ausentes(self, ctx):
        """Verifica que la omisión de sustantivos_clave retorne error estructurado en ejecución."""
        tools, _ = ctx
        valid_bridges = [
            {"text": "sinonimo texto", "angle": "sinonimo"},
            {"text": "problema texto", "angle": "problema"},
            {"text": "solucion texto", "angle": "solucion"},
            {"text": "situacion texto", "angle": "situacion"},
            {"text": "ingenuo texto", "angle": "ingenuo"},
        ]
        # Test en aprender (dimensiones posicional, bridges provisto)
        raw_ap = tools["aprender"](
            concepto="nodo_test_sin_sk",
            contenido="texto descriptivo sobre configuracion del servidor",
            dimensiones='{"dominio":["dominio_tecnico"]}',
            bridges=valid_bridges,
            busqueda_previa=True,
            sustantivos_clave=None,
        )
        res_ap = _raw_json(raw_ap)
        assert res_ap["status"] == "error"
        assert res_ap["codigo"] == "SUSTANTIVOS_CLAVE_AUSENTES"

        # Test en guardar
        raw_gd = tools["guardar"](
            concepto="nodo_test_sin_sk_2",
            contenido="texto descriptivo sobre configuracion del servidor",
            bridges=valid_bridges,
            busqueda_previa=True,
            sustantivos_clave="",
        )
        res_gd = _raw_json(raw_gd)
        assert res_gd["status"] == "error"
        assert res_gd["codigo"] == "SUSTANTIVOS_CLAVE_AUSENTES"