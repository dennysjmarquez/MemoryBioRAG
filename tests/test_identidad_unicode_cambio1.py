"""E3 cambio 1: identidad compartida. La conservación de sustantivos es cambio 2."""

import asyncio
import unicodedata

import pytest

from core.concept_hub import ANGULOS_OFICIALES, validar_bridges
from core.identidad_unicode import normalizar_identidad
from core.memory.constants import normalizar_sustantivos_clave
from core.memory_store import SQLiteMemoryBioRAG
from core import memory_service
from core.mcp_server import search, write
from core.mcp_server._shared import _sustantivo_valido
from scripts.evaluar_qa_guardado_nativo_b2 import texto_tool
from scripts.evaluar_qa_multilingue_mcp_e3a import parsear_mcp


@pytest.mark.parametrize("entrada,esperada", [
    ("ＡＢＣ", "ABC"),
    ("ｶﾞﾗｽ", "ガラス"),
    ("カ\u3099ラス", "ガラス"),
    ("Ｃａｆｅ\u0301", "Café"),
    ("ａ\u3000ｂ", "a b"),
    ("ﾡ", "ㄱ"),
    ("ㅋㅏㄳ", "ㅋㅏㄳ"),
    ("① ² ™ ﬁ", "① ² ™ ﬁ"),
    ("カ\u309b", "カ\u309b"),  # La marca espaciada no se interpreta como U+3099.
])
def test_identidad_selectiva(entrada, esperada):
    assert normalizar_identidad(entrada) == esperada
    assert normalizar_identidad(esperada) == esperada


def test_la_funcion_conserva_marcas_y_no_aplica_nfkc_general():
    assert normalizar_identidad("ガラス") != normalizar_identidad("カラス")
    assert normalizar_identidad("niño") == normalizar_identidad("nin\u0303o")
    assert normalizar_identidad("①²™ﬁ") != unicodedata.normalize("NFKC", "①²™ﬁ")
    assert normalizar_identidad("カ\u309b") != "ガ"


def test_bloque_completo_y_espacio_son_idempotentes():
    for codigo in range(0xFF00, 0xFFF0):
        actual = normalizar_identidad(chr(codigo))
        assert normalizar_identidad(actual) == actual
    assert normalizar_identidad("\u3000") == " "


def test_texto_preserva_puntuacion_cjk_y_solo_pliega_letras_y_numeros():
    texto = "你好，世界！（测试）：ＡＢＣ１２３　ｘ＋ｙ／ｶﾞﾗｽ"
    esperado = "你好，世界！（测试）：ABC123　x＋y／ガラス"
    assert normalizar_identidad(texto, ancho_solo_letras_numeros=True) == esperado
    assert normalizar_identidad("你好，世界！（测试）", ancho_solo_letras_numeros=True) == "你好，世界！（测试）"
    # NFC global también cambia algunos símbolos: el modo de texto los conserva.
    simbolos = "\u037e\u2329\u1fee\U0001d15e"
    assert normalizar_identidad(simbolos, ancho_solo_letras_numeros=True) == simbolos
    assert normalizar_identidad("Ｃａｆｅ\u0301", ancho_solo_letras_numeros=True) == "Café"


def test_modo_texto_preserva_signos_y_simbolos_de_todo_el_bloque():
    for codigo in range(0xFF00, 0xFFF0):
        char = chr(codigo)
        actual = normalizar_identidad(char, ancho_solo_letras_numeros=True)
        if unicodedata.category(char)[0] in "LN":
            assert actual == normalizar_identidad(char)
        else:
            assert actual == char
    assert normalizar_identidad("\u3000", ancho_solo_letras_numeros=True) == "\u3000"


def test_sustantivos_usan_identidad_antes_de_separar_y_validar():
    assert normalizar_sustantivos_clave("ａｌｆａ，ｂｅｔａ") == "alfa,beta"
    assert _sustantivo_valido("ａｂ")
    assert not _sustantivo_valido("－ａ")
    # Todavía se aplica el normalizador histórico sin marcas y con NFKD:
    # identidad exacta de sustantivos y su comparación quedan para el cambio 2.
    assert normalizar_sustantivos_clave("ガラス,カラス") == "カラス"
    assert normalizar_sustantivos_clave("①①,11") == "11"
    assert normalizar_sustantivos_clave("ﬁﬁ,fifi") == "fifi"


def _puentes(primero, segundo="corte red general"):
    textos = [primero, segundo, "apagar encender motor", "periodo trabajo rural", "sin luces visibles"]
    return [{"text": texto, "angle": angulo}
            for texto, angulo in zip(textos, ANGULOS_OFICIALES)]


def test_bridges_cuentan_tras_plegar_y_guardan_el_contrato_de_validacion():
    for raw in ("１２３４", "ｇｏ\u3000ｔｏ"):
        validos, _ = validar_bridges(_puentes(raw), "farol_costero")
        assert all(item["text"] != raw for item in validos)
    raw = "ｌｕｎａ\u3000ａｚｕｌ"
    validos, _ = validar_bridges(_puentes(raw), "farol_costero")
    assert any(item["text"] == raw for item in validos)  # el validador no reescribe el texto devuelto


def test_puentes_duplicados_y_antidestinatario_usan_la_misma_identidad():
    validos, rechazados = validar_bridges(_puentes("ＬＵＮＡ　ＡＺＵＬ", "luna azul"), "farol_costero")
    assert len(validos) == 4
    assert any("texto repetido" in motivo for motivo in rechazados)
    validos, rechazados = validar_bridges(_puentes("ｆａｒｏ ｃｏｓｔｅｒｏ"), "faro_costero")
    assert all(item["text"] != "ｆａｒｏ ｃｏｓｔｅｒｏ" for item in validos)
    assert any("variación morfológica" in motivo for motivo in rechazados)


@pytest.fixture()
def cerebro(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_DMN_ESTADO_PATH", str(tmp_path / "estado.json"))
    db = SQLiteMemoryBioRAG(str(tmp_path / "memoria.db"))
    yield db
    db.cerrar_sistema()


def test_escritura_nueva_y_consolidacion_directa(cerebro):
    cerebro.percibir_corto_plazo("Ｎｕｅｖｏ", "Pieza ｶﾞﾗｽ y Ｃａｆｅ\u0301", sinonimos="ｖａｓｏ，ｔａｚａ")
    assert cerebro.conn.execute(
        "SELECT contenido, sinonimos FROM corto_plazo WHERE concepto=?", ("nuevo",)
    ).fetchone() == ("Pieza ガラス y Café", "vaso，taza")
    assert cerebro.consolidar_concepto("Ｎｕｅｖｏ")
    assert cerebro.conn.execute("SELECT concepto FROM largo_plazo WHERE concepto='nuevo'").fetchone() == ("nuevo",)


def test_guardado_directo_preserva_puntuacion_en_contenido_y_sinonimos(cerebro):
    memory_service.aprender(
        cerebro, "ejemplo_cjk", "你好，世界！（测试）：ＡＢＣ１２３　終",
        sinonimos="　方案，ＡＢＣ！（测试）　",
    )
    assert cerebro.conn.execute(
        "SELECT contenido, sinonimos FROM largo_plazo WHERE concepto='ejemplo_cjk'"
    ).fetchone() == ("你好，世界！（测试）：ABC123　終", "　方案，ABC！（测试）　")


def test_fusion_de_sinonimos_conserva_espacio_ideografico(cerebro):
    cerebro.percibir_corto_plazo("sinonimos", "primero", sinonimos="　Ａ　")
    cerebro.percibir_corto_plazo(
        "sinonimos", "segundo", sinonimos="　Ｂ！　, X ,Ａ,　"
    )
    assert cerebro.conn.execute(
        "SELECT sinonimos FROM corto_plazo WHERE concepto='sinonimos'"
    ).fetchone() == ("　A　,　B！　,X",)
    assert cerebro.consolidar_concepto("sinonimos")
    memory_service.aprender(cerebro, "sinonimos", "tercero", sinonimos="　Ｃ　")
    assert cerebro.conn.execute(
        "SELECT sinonimos FROM largo_plazo WHERE concepto='sinonimos'"
    ).fetchone() == ("　A　,　B！　,X,　C　",)


def test_consolidacion_prioriza_clave_exacta_si_coexisten_ambas(cerebro):
    cerebro.conn.execute("INSERT INTO corto_plazo(concepto, contenido, timestamp) VALUES (?, ?, 0)", ("ａｂｃ", "viejo"))
    cerebro.conn.execute("INSERT INTO corto_plazo(concepto, contenido, timestamp) VALUES (?, ?, 0)", ("abc", "nuevo"))
    cerebro.conn.commit()
    assert cerebro.consolidar_concepto("ａｂｃ")
    assert cerebro.conn.execute("SELECT concepto, contenido FROM corto_plazo").fetchall() == [("abc", "nuevo")]
    assert cerebro.conn.execute("SELECT concepto, contenido FROM largo_plazo").fetchall() == [("ａｂｃ", "viejo")]


def test_consolidacion_no_desvia_una_referencia_antigua_en_largo(cerebro):
    cerebro.conn.execute(
        "INSERT INTO largo_plazo(concepto, contenido) VALUES (?, ?)", ("ａｂｃ", "viejo")
    )
    cerebro.conn.execute(
        "INSERT INTO corto_plazo(concepto, contenido, timestamp) VALUES (?, ?, 0)", ("abc", "nuevo")
    )
    cerebro.conn.commit()
    assert not cerebro.consolidar_concepto("ａｂｃ")
    assert cerebro.conn.execute("SELECT concepto, contenido FROM largo_plazo").fetchall() == [("ａｂｃ", "viejo")]
    assert cerebro.conn.execute("SELECT concepto, contenido FROM corto_plazo").fetchall() == [("abc", "nuevo")]


def test_aprender_actualiza_clave_antigua_exacta_sin_crear_duplicado(cerebro):
    cerebro.conn.execute(
        "INSERT INTO largo_plazo(concepto, contenido, peso_sinaptico, estado) VALUES (?, ?, ?, ?)",
        ("ｇｏ_ｔｏ", "dato antiguo", 0.5, "activo"),
    )
    cerebro.conn.commit()
    id_antes = cerebro.conn.execute("SELECT id FROM largo_plazo WHERE concepto=?", ("ｇｏ_ｔｏ",)).fetchone()[0]
    resultado = memory_service.aprender(cerebro, "ｇｏ_ｔｏ", "actualizado")
    assert resultado["concepto"] == "ｇｏ_ｔｏ"
    filas = cerebro.conn.execute(
        "SELECT id, concepto, contenido, peso_sinaptico FROM largo_plazo"
    ).fetchall()
    assert len(filas) == 1
    assert filas[0][:3] == (id_antes, "ｇｏ_ｔｏ", "dato antiguo | Actualización: actualizado")
    assert filas[0][3] == pytest.approx(0.7)  # consolidación existente: +0,20
    assert cerebro.conn.execute("SELECT COUNT(*) FROM corto_plazo").fetchone() == (0,)
    assert cerebro.conn.execute("SELECT COUNT(*) FROM largo_plazo WHERE concepto='go_to'").fetchone() == (0,)


def test_aprender_prioriza_original_incluso_si_la_normalizada_coexiste(cerebro):
    cerebro.conn.execute("INSERT INTO corto_plazo(concepto, contenido, timestamp) VALUES (?, ?, 0)",
                         ("ｌｅｇａｃｙ", "dato antiguo"))
    cerebro.conn.execute("INSERT INTO corto_plazo(concepto, contenido, timestamp) VALUES (?, ?, 0)",
                         ("legacy", "dato distinto"))
    cerebro.conn.commit()
    resultado = memory_service.aprender(cerebro, "ｌｅｇａｃｙ", "actualizado", consolidar=False)
    assert resultado["concepto"] == "ｌｅｇａｃｙ"
    assert cerebro.conn.execute(
        "SELECT concepto, contenido FROM corto_plazo ORDER BY concepto"
    ).fetchall() == [("legacy", "dato distinto"), ("ｌｅｇａｃｙ", "dato antiguo | Actualización: actualizado")]
    assert cerebro.conn.execute("SELECT COUNT(*) FROM largo_plazo").fetchone() == (0,)


def test_aprender_con_colision_en_largo_actualiza_solo_el_original(cerebro):
    cerebro.conn.executemany(
        "INSERT INTO largo_plazo(concepto, contenido, peso_sinaptico, estado) VALUES (?, ?, 1.0, 'activo')",
        [("ｇｏ_ｔｏ", "original"), ("go_to", "otro recuerdo")],
    )
    cerebro.conn.commit()
    resultado = memory_service.aprender(cerebro, "ｇｏ_ｔｏ", "actualizado")
    assert resultado["concepto"] == "ｇｏ_ｔｏ"
    assert cerebro.conn.execute("SELECT concepto, contenido FROM largo_plazo ORDER BY concepto").fetchall() == [
        ("go_to", "otro recuerdo"), ("ｇｏ_ｔｏ", "original | Actualización: actualizado")
    ]


def test_memory_service_usa_la_clave_normalizada_en_la_misma_escritura(cerebro):
    resultado = memory_service.aprender(cerebro, "Ｐｒｕｅｂａ", "Señal ｃｅｌｅｓｔｅ")
    assert resultado["concepto"] == "prueba"
    assert cerebro.conn.execute(
        "SELECT contenido FROM largo_plazo WHERE concepto='prueba'"
    ).fetchone() == ("Señal celeste",)


def test_busqueda_directa_igual_para_los_dos_anchos_nuevos(cerebro):
    memory_service.aprender(cerebro, "nodo_unico", "Objeto de ｶﾞﾗｽ azul resistente")
    argumentos = dict(profundidad="activos", limite=5, ignore_peso_sinaptico=True)
    medio, _ = cerebro.buscar_por_frase("ｶﾞﾗｽ", **argumentos)
    normal, _ = cerebro.buscar_por_frase("ガラス", **argumentos)
    assert [fila[0] for fila in medio] == [fila[0] for fila in normal]
    assert any(fila[0] == "nodo_unico" for fila in medio)


@pytest.fixture()
def mcp_cerebro(cerebro, monkeypatch):
    from core.mcp_server.server import _build_server
    from middleware.auto_guardado import buffer_global

    monkeypatch.setenv("BIORAG_AUTOGUARDADO_HEURISTICO", "0")
    monkeypatch.setenv("BIORAG_MCP_AUTO_PARAFRASIS", "0")
    monkeypatch.setenv("BIORAG_MCP_AUTO_DIMS", "0")
    cerebro._persistente = True
    monkeypatch.setattr(write, "_get_cerebro", lambda: cerebro)
    monkeypatch.setattr(search, "_get_cerebro", lambda: cerebro)
    buffer_global.limpiar()
    yield _build_server(), cerebro
    buffer_global.limpiar()
    cerebro._persistente = False


def _llamar(mcp, nombre, **argumentos):
    return parsear_mcp(texto_tool(asyncio.run(mcp.call_tool(nombre, argumentos))))


def test_preflight_rechaza_antes_de_procesar_contenido():
    import json

    respuesta = json.loads(write._aprender_impl("ｎｕｅｖｏ", None, bridges=None, busqueda_previa=False))
    assert respuesta["codigo"] == "BUSQUEDA_PREVIA_REQUERIDA"


def test_mcp_limita_el_texto_antes_de_normalizar(mcp_cerebro, monkeypatch):
    mcp, _ = mcp_cerebro
    llamadas = []
    real = search.normalizar_identidad

    def medir(texto):
        llamadas.append(len(texto))
        return real(texto)

    monkeypatch.setattr(search, "normalizar_identidad", medir)
    respuesta = _llamar(
        mcp, "recordar", query="ａｂ " * 400, parafrasis="ｃｄ " * 400,
        rafaga_palabras="ｅｆ " * 400, sustantivos_clave="test", limite=5,
    )
    assert respuesta.get("status") != "error"
    assert llamadas and max(llamadas) <= 500


@pytest.mark.parametrize("tool_name", ["aprender", "guardar"])
def test_mcp_consulta_y_escritura_nueva_comparten_identidad(mcp_cerebro, monkeypatch, tool_name):
    mcp, db = mcp_cerebro
    observadas = []
    real = db.buscar_por_frase

    def buscar(frase, *args, **kwargs):
        observadas.append((frase, kwargs.get("parafrasis_list"), kwargs.get("sustantivos_clave_boost")))
        return real(frase, *args, **kwargs)

    monkeypatch.setattr(db, "buscar_por_frase", buscar)
    previa = _llamar(mcp, "recordar", query="ａｌｆａ\u3000ｂｅｔａ", sustantivos_clave="ｃａｆｅ",
                      parafrasis="ｒｏｊｏ，ａｚｕｌ", limite=5, asociados=False)
    assert previa.get("status") != "error"
    assert observadas and observadas[0][0] == "alfa beta"
    assert observadas[0][1] == ["rojo", "azul"]
    assert observadas[0][2] == "cafe"

    resultado = _llamar(
        mcp, tool_name, concepto="Ｌｕｚ\u3000Ａｚｕｌ", contenido="Ｃａｆｅ\u0301 y ｶﾞﾗｽ azul",
        syn="Ｂｅｂｉｄａ，ｆｒｕｔａ", cat="General", dimensiones=None, bridges=_puentes("ｌｕｎａ\u3000ａｚｕｌ"),
        sustantivos_clave="ｃａｆｅ，ｐａｐｅｌ", busqueda_previa=True,
    )
    assert resultado["status"] == "ok"
    assert resultado["concepto"] == "luz_azul"
    assert db.conn.execute(
        "SELECT contenido, sinonimos, sustantivos_clave FROM corto_plazo WHERE concepto='luz_azul'"
    ).fetchone() == ("Café y ガラス azul", "Bebida，fruta", "cafe,papel")
    puentes = [row[0] for row in db.conn.execute(
        "SELECT bridge_text FROM concept_hub_bridges WHERE hub_id='hub_luz_azul' ORDER BY angle"
    )]
    assert len(puentes) == 5 and "luna azul" in puentes
    update = _llamar(mcp, "agregar_sustantivos", concepto="Ｌｕｚ\u3000Ａｚｕｌ", sustantivos_clave="ａｚｕｌ，ｐａｐｅｌ")
    assert update["status"] == "ok" and update["concepto"] == "luz_azul"
    lectura = _llamar(mcp, "sustantivos", concepto="Ｌｕｚ\u3000Ａｚｕｌ")
    assert lectura["status"] == "ok" and lectura["sustantivos_clave"] == "azul,papel"


def test_mcp_preserva_signos_cjk_en_contenido_y_sinonimos(mcp_cerebro):
    mcp, db = mcp_cerebro
    previa = _llamar(mcp, "recordar", query="ejemplo cjk", sustantivos_clave="ejemplo", limite=5)
    assert previa.get("status") != "error"
    resultado = _llamar(
        mcp, "aprender", concepto="ejemplo_cjk", contenido="你好，世界！（测试）：ＡＢＣ１２３　終",
        syn="　方案，ＡＢＣ！（测试）　", cat="General", dimensiones=None,
        bridges=_puentes("luna azul"), sustantivos_clave="cafe,papel", busqueda_previa=True,
    )
    assert resultado["status"] == "ok"
    assert db.conn.execute(
        "SELECT contenido, sinonimos FROM corto_plazo WHERE concepto='ejemplo_cjk'"
    ).fetchone() == ("你好，世界！（测试）：ABC123　終", "　方案，ABC！（测试）　")


def test_mcp_prioriza_clave_antigua_exacta_si_coexisten_ambas(mcp_cerebro):
    mcp, db = mcp_cerebro
    db.conn.execute("INSERT INTO corto_plazo(concepto,contenido,timestamp,sustantivos_clave) VALUES (?, ?, 0, ?)",
                    ("ｌｅｇａｃｙ", "dato antiguo", "antiguo,valor"))
    db.conn.execute("INSERT INTO corto_plazo(concepto,contenido,timestamp,sustantivos_clave) VALUES (?, ?, 0, ?)",
                    ("legacy", "dato nuevo", "nuevo,valor"))
    db.conn.commit()
    previa = _llamar(mcp, "recordar", query="ｌｅｇａｃｙ", sustantivos_clave="antiguo", limite=5)
    assert previa.get("status") != "error"
    guardado = _llamar(mcp, "aprender", concepto="ｌｅｇａｃｙ", contenido="actualizado",
                       dimensiones=None, cat="General", bridges=_puentes("luna azul"),
                       sustantivos_clave="antiguo,valor", busqueda_previa=True)
    assert guardado["status"] == "ok" and guardado["concepto"] == "ｌｅｇａｃｙ"
    assert db.conn.execute("SELECT contenido FROM corto_plazo WHERE concepto='legacy'").fetchone() == ("dato nuevo",)
    assert db.conn.execute("SELECT contenido FROM corto_plazo WHERE concepto='ｌｅｇａｃｙ'").fetchone() == (
        "dato antiguo | Actualización: actualizado",
    )
    lectura = _llamar(mcp, "sustantivos", concepto="ｌｅｇａｃｙ")
    assert lectura["concepto"] == "ｌｅｇａｃｙ" and lectura["sustantivos_clave"] == "antiguo,valor"
    cambio = _llamar(mcp, "agregar_sustantivos", concepto="ｌｅｇａｃｙ", sustantivos_clave="otro,valor")
    assert cambio["concepto"] == "ｌｅｇａｃｙ"
    assert db.conn.execute("SELECT sustantivos_clave FROM corto_plazo WHERE concepto='legacy'").fetchone() == ("nuevo,valor",)
