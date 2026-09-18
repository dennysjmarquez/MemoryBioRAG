"""
Tests Spec 003 — Descubrimiento del parámetro `sustantivos_clave` por parte del agente.

Antecedente: Specs 001/002 implementaron el núcleo temático en el motor
(`core/memory_store.py`), en las tools MCP y en el CLI (`biorag.py`). Quedaba
pendiente la CAPA DE DESCUBRIMIENTO: que el agente encuentre y use el parámetro
por sí solo, con el mismo nivel de exposición que ya tienen `deep` (búsqueda
profunda) y `parafrasis` (parafraseo).

RFs cubiertos:
  RF-D1  El parámetro aparece en las instrucciones de nivel sistema (ORACLE_PROMPT)
         con plantilla propia, errores comunes, árbol de decisión y protocolo de guardado.
  RF-D2  Cada resultado de `recordar`/`buscar` expone su propio `sustantivos_clave`
         (descubrimiento por observación + detección de nodos legacy vacíos).
  RF-D3  `recordar` emite un ⚠️ pedagógico cuando el parámetro se omite, igual que
         lo hace para `parafrasis`, `dias` y `dimensiones`.
  RF-D4  El alias legacy `buscar` acepta Y APLICA `sustantivos_clave` (paridad con
         `recordar`), incluida la validación fail-fast de RF-20.
  RF-D5  Las descripciones de tools (`recordar`, `buscar`, `aprender`, `guardar`)
         documentan el parámetro — es lo que el cliente MCP muestra al agente.
  RF-D6  El prompt MCP `biorag-system-prompt` (el que el agente copia a su system
         prompt) incluye la regla del núcleo temático.
  RF-D7  La búsqueda queda registrada en `log_busquedas` con el valor NORMALIZADO
         que realmente se aplicó (observabilidad/auditoría de adopción).
"""

import json
import sqlite3
import pytest


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    """DB temporal + BIORAG_PATH + server MCP completo. Resetea el singleton."""
    db_path = str(tmp_path / "descubrimiento.db")
    monkeypatch.setenv("BIORAG_PATH", db_path)
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path)
    cerebro.cerrar_sistema()

    from core.memory_service import reset_cerebro
    reset_cerebro()

    import mcp_server as m
    mcp = m._build_server()
    tools = {t.name: t.fn for t in mcp._tool_manager.list_tools()}
    yield tools, db_path, mcp, m
    reset_cerebro()


def _insert_lp(db_path, concepto, contenido, sk=""):
    """Inserta un nodo consolidado y sincroniza la FTS5 (trigger-equivalente)."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO largo_plazo (concepto, contenido, categoria, estado, peso_sinaptico, sustantivos_clave) "
        "VALUES (?, ?, 1, 'activo', 1.0, ?)",
        (concepto, contenido, sk),
    )
    conn.commit()
    # No hace falta tocar largo_plazo_fts: los triggers _ai/_ad/_au la sincronizan
    # solos en cada INSERT/UPDATE (Spec 001 · T2). Intentar poblarla a mano choca
    # con el rowid ya indexado (IntegrityError).
    conn.close()


def _json_de(raw):
    """Las tools anteponen ⚠️ como texto plano; el JSON empieza en la primera '{'."""
    start = raw.find("{")
    return json.loads(raw[start:]) if start >= 0 else json.loads(raw)


def _prefijo(raw):
    """Texto de warnings anterior al JSON ('' si no hubo warnings)."""
    start = raw.find("{")
    return raw[:start].strip() if start > 0 else ""


class TestRFD3WarningPedagogico:
    """RF-D3: el agente descubre el parámetro EN RUNTIME cuando lo omite."""

    def test_omitir_sustantivos_clave_emite_warning(self, ctx):
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_servidor", "el servidor backend se cae por timeout")

        raw = tools["recordar"](query="servidor timeout")
        prefijo = _prefijo(raw)

        assert "sustantivos_clave" in prefijo, (
            "recordar() debe advertir la ausencia del núcleo temático, "
            "igual que lo hace con parafrasis/dias/dimensiones"
        )
        # El warning tiene que enseñar, no solo quejarse: formato + ejemplo.
        assert "4.0x" in prefijo
        assert "TRATAN" in prefijo

    def test_warning_convive_con_los_demas(self, ctx):
        """No reemplaza a los warnings existentes (parafrasis, dias, asociados)."""
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_servidor", "el servidor backend se cae por timeout")

        prefijo = _prefijo(tools["recordar"](query="servidor timeout"))
        assert "parafrasis=None" in prefijo
        assert "sustantivos_clave=None" in prefijo

    def test_proveer_sustantivos_clave_no_emite_warning(self, ctx):
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_servidor", "el servidor backend se cae por timeout")

        prefijo = _prefijo(
            tools["recordar"](query="servidor timeout", sustantivos_clave="servidor,timeout")
        )
        assert "sustantivos_clave=None" not in prefijo

    def test_string_vacio_trata_como_omision(self, ctx):
        """'' = sin boost (RF-19) → corresponde el aviso pedagógico."""
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_servidor", "el servidor backend se cae por timeout")

        prefijo = _prefijo(tools["recordar"](query="servidor timeout", sustantivos_clave=""))
        assert "sustantivos_clave=None" in prefijo

    def test_warning_no_bloquea_la_busqueda(self, ctx):
        """Es pedagógico: la búsqueda DEBE ejecutarse igual (RF-19, opcional)."""
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_servidor", "el servidor backend se cae por timeout")

        raw = tools["recordar"](query="servidor timeout")
        res = _json_de(raw)
        assert "resultados" in res
        assert res["total"] >= 1


class TestRFD2VisibilidadEnResultados:
    """RF-D2: el campo se ve en cada resultado → descubrimiento por observación."""

    def test_resultado_expone_sustantivos_clave(self, ctx):
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_contaminacion", "los automoviles botan humo en la ciudad",
                   sk="contaminacion,aire")

        res = _json_de(tools["recordar"](query="humo ciudad", sustantivos_clave="contaminacion,aire"))
        assert res["resultados"], "la búsqueda debe devolver el nodo"
        item = res["resultados"][0]
        assert item["sustantivos_clave"] == "contaminacion,aire"
        assert item["sustantivos_clave_items"] == ["contaminacion", "aire"]

    def test_nodo_legacy_muestra_nucleo_vacio(self, ctx):
        """'' delata un nodo pre-Spec-001 → el agente sabe que puede enriquecerlo."""
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_legacy", "texto antiguo sin nucleo tematico", sk="")

        res = _json_de(tools["recordar"](query="texto antiguo"))
        assert res["resultados"]
        item = res["resultados"][0]
        assert item["sustantivos_clave"] == ""
        assert item["sustantivos_clave_items"] == []

    def test_visibilidad_tambien_por_alias_buscar(self, ctx):
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_contaminacion", "los automoviles botan humo en la ciudad",
                   sk="contaminacion,aire")

        res = _json_de(tools["buscar"](query="humo ciudad"))
        assert res["resultados"][0]["sustantivos_clave"] == "contaminacion,aire"


class TestRFD4AliasLegacyBuscar:
    """RF-D4: `buscar` debe tener paridad real con `recordar` (no solo aceptar el kwarg)."""

    def test_buscar_acepta_el_parametro(self, ctx):
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_servidor", "el servidor backend se cae por timeout",
                   sk="servidor,timeout")

        res = _json_de(tools["buscar"](query="servidor", sustantivos_clave="servidor,timeout"))
        assert "resultados" in res
        assert res["total"] >= 1

    def test_buscar_valida_formato_fail_fast(self, ctx):
        """RF-20 vía alias: término inválido → error y la búsqueda NO se ejecuta."""
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_servidor", "el servidor backend se cae por timeout")

        res = _json_de(tools["buscar"](query="servidor", sustantivos_clave="servidor,termino invalido"))
        assert res["status"] == "error"
        assert res["codigo"] == "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO"
        assert "resultados" not in res

    def test_paridad_de_ranking_entre_recordar_y_buscar(self, ctx):
        """El boost se APLICA igual por ambas rutas (mismo orden de resultados).

        Pool de 5 candidatos con contenido idéntico: el único con núcleo temático
        debe quedar primero en ambas tools (el boost rompe el empate BM25).
        """
        tools, db_path, mcp, m = ctx
        for i in range(4):
            _insert_lp(db_path, f"nodo_base_{i}", "establecer conexion segura", sk="")
        _insert_lp(db_path, "nodo_boost", "establecer conexion segura", sk="timeout,servidor")

        top_recordar = [r["concepto"] for r in _json_de(
            tools["recordar"](query="conexion", sustantivos_clave="timeout,servidor")
        )["resultados"]]
        top_buscar = [r["concepto"] for r in _json_de(
            tools["buscar"](query="conexion", sustantivos_clave="timeout,servidor")
        )["resultados"]]

        assert top_recordar and top_recordar[0] == "nodo_boost"
        assert top_buscar == top_recordar, (
            "el alias legacy debe aplicar el boost exactamente igual que recordar"
        )


class TestRFD1InstruccionesDeSistema:
    """RF-D1: ORACLE_PROMPT es `instructions=` de FastMCP → contexto base del agente."""

    def test_plantilla_propia_como_parafasis_y_rafaga(self, ctx):
        tools, db_path, mcp, m = ctx
        assert "PLANTILLA SUSTANTIVOS_CLAVE" in m.ORACLE_PROMPT
        # Mismo nivel de exposición que sus dos hermanos.
        assert "PLANTILLA PARÁFRASIS" in m.ORACLE_PROMPT
        assert "PLANTILLA RÁFAGA" in m.ORACLE_PROMPT

    def test_flujo_paso1_ya_incluye_el_parametro(self, ctx):
        tools, db_path, mcp, m = ctx
        assert "sustantivos_clave='nucleo1,nucleo2,nucleo3'" in m.ORACLE_PROMPT

    def test_arbol_de_decision_cubre_busqueda_por_tema(self, ctx):
        tools, db_path, mcp, m = ctx
        assert "¿Busco por TEMA" in m.ORACLE_PROMPT
        assert "deep=true" in m.ORACLE_PROMPT  # el hermano preexistente sigue ahí

    def test_errores_comunes_incluyen_nucleo_tematico(self, ctx):
        tools, db_path, mcp, m = ctx
        assert "SUSTANTIVOS_CLAVE_AUSENTES" in m.ORACLE_PROMPT
        assert "Confundir sustantivos_clave con syn" in m.ORACLE_PROMPT

    def test_protocolo_de_guardado_lo_menciona_obligatorio(self, ctx):
        tools, db_path, mcp, m = ctx
        assert "¿De QUÉ TRATA esto?" in m.ORACLE_PROMPT

    def test_prueba_del_automovil_presente(self, ctx):
        """El ejemplo canónico del spec (RF-23/CL-14) tiene que estar a la vista."""
        tools, db_path, mcp, m = ctx
        assert "contaminacion" in m.ORACLE_PROMPT

    def test_server_instructions_es_el_oracle_prompt(self, ctx):
        """Garantiza que lo editado es efectivamente lo que recibe el agente."""
        tools, db_path, mcp, m = ctx
        assert mcp.instructions == m.ORACLE_PROMPT
        assert "sustantivos_clave" in mcp.instructions


class TestRFD5DescripcionesDeTools:
    """RF-D5: el cliente MCP muestra descripciones + schema de parámetros."""

    def _desc(self, mcp, nombre):
        return mcp._tool_manager._tools[nombre].description

    @pytest.mark.parametrize("tool", ["recordar", "buscar", "aprender", "guardar",
                                      "sustantivos", "agregar_sustantivos"])
    def test_descripcion_menciona_el_parametro(self, ctx, tool):
        tools, db_path, mcp, m = ctx
        assert "sustantivos_clave" in self._desc(mcp, tool), (
            f"la descripción de '{tool}' debe documentar sustantivos_clave"
        )

    def test_aprender_advierte_que_es_obligatorio(self, ctx):
        tools, db_path, mcp, m = ctx
        desc = self._desc(mcp, "aprender")
        assert "OBLIGATORIO" in desc
        assert "SUSTANTIVOS_CLAVE_AUSENTES" in desc

    def test_recordar_explica_el_peso_bm25(self, ctx):
        tools, db_path, mcp, m = ctx
        assert "4.0x" in self._desc(mcp, "recordar")

    def test_recordar_incluye_nota_textual_de_rf19(self, ctx):
        """RF-19 pedía textualmente esta nota en la descripción del parámetro.

        Se verifica sobre el JSON Schema que el servidor publica — que es
        exactamente lo que el cliente MCP le muestra al agente.
        """
        tools, db_path, mcp, m = ctx
        props = mcp._tool_manager._tools["recordar"].parameters["properties"]
        assert "sustantivos_clave" in props
        desc_param = props["sustantivos_clave"]["description"]
        assert "centro de gravedad temático suben al top" in desc_param

    def test_buscar_tiene_el_parametro_en_su_schema(self, ctx):
        """No basta con que la descripción lo nombre: debe ser aceptado y opcional."""
        tools, db_path, mcp, m = ctx
        import inspect
        tool = mcp._tool_manager._tools["buscar"]
        assert "sustantivos_clave" in tool.parameters["properties"]
        assert "sustantivos_clave" not in tool.parameters.get("required", [])
        sig = inspect.signature(tools["buscar"])
        assert sig.parameters["sustantivos_clave"].default is None

    def test_aprender_y_guardar_lo_publican_en_schema(self, ctx):
        """El cliente MCP arma la llamada desde el schema: si no está ahí, no existe."""
        tools, db_path, mcp, m = ctx
        for nombre in ("aprender", "guardar"):
            props = mcp._tool_manager._tools[nombre].parameters["properties"]
            assert "sustantivos_clave" in props, nombre
            assert "OBLIGATORIO" in props["sustantivos_clave"]["description"], nombre


class TestRFD6PromptMCP:
    """RF-D6: `biorag-system-prompt` es lo que el agente incorpora a su system prompt."""

    def test_prompt_incluye_regla_de_nucleo_tematico(self, ctx):
        tools, db_path, mcp, m = ctx
        prompts = mcp._prompt_manager._prompts
        assert "biorag-system-prompt" in prompts
        texto = prompts["biorag-system-prompt"].description + json.dumps(
            [str(getattr(prompts["biorag-system-prompt"], "arguments", ""))],
            ensure_ascii=False,
        )
        # El cuerpo se renderiza al invocarlo; se verifica vía la función registrada.
        fn = prompts["biorag-system-prompt"].fn if hasattr(prompts["biorag-system-prompt"], "fn") else None
        if fn is not None:
            cuerpo = fn()
            assert "sustantivos_clave" in cuerpo
            assert "NÚCLEO TEMÁTICO" in cuerpo
            assert "agregar_sustantivos" in cuerpo
        else:
            assert "sustantivos_clave" in texto


class TestRFD7Observabilidad:
    """RF-D7: log_busquedas registra el valor normalizado realmente aplicado.

    Precondición explícita: la telemetría se desactiva con BIORAG_NO_LOG=1
    (core/memory_store.py, Phase 2D). Otros módulos de test/benchmark fijan esa
    variable con setdefault() y no la restauran, así que se filtra al proceso
    completo. Estos tests declaran su propia precondición para no depender del
    orden de ejecución ni de la higiene ajena.
    """

    @pytest.fixture(autouse=True)
    def _telemetria_activa(self, monkeypatch):
        monkeypatch.delenv("BIORAG_NO_LOG", raising=False)

    def test_parametro_queda_registrado_normalizado(self, ctx):
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_servidor", "el servidor backend se cae por timeout")

        # Entrada con mayúsculas, tildes y espacios → debe loguearse normalizada.
        tools["recordar"](query="servidor", sustantivos_clave=" Servidor, CONEXIÓN ")

        conn = sqlite3.connect(db_path)
        filas = conn.execute(
            "SELECT params_json FROM log_busquedas ORDER BY rowid DESC LIMIT 5"
        ).fetchall()
        conn.close()

        registros = [json.loads(f[0]) for f in filas if f[0]]
        assert registros, "la búsqueda debe quedar registrada en log_busquedas"
        con_sk = [r for r in registros if r.get("sustantivos_clave")]
        assert con_sk, f"el parámetro debe constar en el log: {registros[:2]}"
        assert con_sk[0]["sustantivos_clave"] == "servidor,conexion"

    def test_omision_se_registra_como_none(self, ctx):
        """Permite auditar la adopción real del parámetro por parte de los agentes."""
        tools, db_path, mcp, m = ctx
        _insert_lp(db_path, "nodo_servidor", "el servidor backend se cae por timeout")

        tools["recordar"](query="servidor")

        conn = sqlite3.connect(db_path)
        fila = conn.execute(
            "SELECT params_json FROM log_busquedas ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        conn.close()
        assert fila and fila[0]
        registro = json.loads(fila[0])
        assert "sustantivos_clave" in registro
        assert registro["sustantivos_clave"] is None
