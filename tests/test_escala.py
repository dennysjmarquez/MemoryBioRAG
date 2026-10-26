"""Invariancia de escala del buscador (core/memory/escala.py, v35.1).

Cubre: palabras raras (typos) con su umbral de frecuencia, la ventana de candidatos
por parecido en vez de por orden de guardado, el caso «la memoria cabe entera»
(consulta de siempre, byte-idéntica), filtros de estado, interruptor y fallos.
"""
import sqlite3

import pytest

from core.memory import escala as E


def _db(docs, extra_inactivos=()):
    """docs: lista de (concepto, contenido). Crea largo_plazo + los dos índices FTS."""
    c = sqlite3.connect(":memory:")
    cur = c.cursor()
    cur.execute("CREATE TABLE largo_plazo (concepto TEXT, contenido TEXT, sinonimos TEXT, "
                "sustantivos_clave TEXT, estado TEXT, categoria INTEGER)")
    cur.execute("CREATE VIRTUAL TABLE largo_plazo_fts USING fts5(concepto, contenido, sinonimos, "
                "sustantivos_clave, tokenize='trigram')")
    cur.execute("CREATE VIRTUAL TABLE largo_plazo_fts_unicode USING fts5(concepto, contenido, "
                "sinonimos, tokenize='unicode61')")
    filas = [(con, cont, "activo") for con, cont in docs] + [(con, cont, "dormido") for con, cont in extra_inactivos]
    for con, cont, est in filas:
        cur.execute("INSERT INTO largo_plazo (concepto, contenido, sinonimos, sustantivos_clave, estado, categoria) "
                    "VALUES (?, ?, '', '', ?, 1)", (con, cont, est))
        rid = cur.lastrowid
        cur.execute("INSERT INTO largo_plazo_fts (rowid, concepto, contenido, sinonimos, sustantivos_clave) "
                    "VALUES (?, ?, ?, '', '')", (rid, con, cont))
        cur.execute("INSERT INTO largo_plazo_fts_unicode (rowid, concepto, contenido, sinonimos) "
                    "VALUES (?, ?, ?, '')", (rid, con, cont))
    c.commit()
    return c, cur


# ───────────────────────── A. palabras raras ─────────────────────────

def test_typo_es_palabra_rara_y_la_palabra_real_no():
    _, cur = _db([("arquitectura_memoria", "la arquitectura de la memoria biorag"),
                  ("memoria_v5", "memoria y optimizaciones"),
                  ("otra", "memoria persistente")])
    raras = E.palabras_desconocidas(cur, {"arquitectura", "memovria", "memoria"})
    assert "memovria" in raras
    assert "memoria" not in raras  # está en 3 recuerdos


def test_typo_citado_en_un_recuerdo_sigue_siendo_raro():
    # Un recuerdo que cita el typo (p. ej. una nota sobre fallos de la QA) no debe
    # apagar el rescate: la frecuencia de un typo no crece con la memoria.
    _, cur = _db([("nota_qa", "fallo la consulta arquitectura memovria biroag"),
                  ("a", "memoria"), ("b", "memoria")])
    assert set(E.palabras_desconocidas(cur, {"memovria", "biroag"})) == {"memovria", "biroag"}


def test_umbral_de_frecuencia_configurable(monkeypatch):
    _, cur = _db([("nota_qa", "memovria"), ("b", "memovria otra vez")])
    assert E.palabras_desconocidas(cur, {"memovria"}) == []  # en 2 recuerdos: ya no es rara
    monkeypatch.setenv("BIORAG_ESCALA_DF_RARA", "2")
    assert E.palabras_desconocidas(cur, {"memovria"}) == ["memovria"]
    monkeypatch.setenv("BIORAG_ESCALA_DF_RARA", "basura")
    assert E.palabras_desconocidas(cur, {"memovria"}) == []  # vuelve al valor por defecto (1)


def test_palabras_cortas_y_numeros_no_cuentan():
    _, cur = _db([("a", "texto cualquiera")])
    assert E.palabras_desconocidas(cur, {"cv", "20", "1234"}) == []


def test_sin_indice_unicode_devuelve_vacio_no_lanza():
    c = sqlite3.connect(":memory:")
    assert E.palabras_desconocidas(c.cursor(), {"memovria"}) == []


def test_no_escribe_en_la_base_principal():
    c, cur = _db([("a", "memoria")])
    E.palabras_desconocidas(cur, {"memoria"})
    tablas_main = {r[0] for r in cur.execute("SELECT name FROM main.sqlite_master")}
    assert E._VOCAB not in tablas_main  # vive en el esquema TEMP de la conexión


# ───────────────────────── B. ventana por parecido ─────────────────────────

def test_memoria_que_cabe_en_la_ventana_usa_la_consulta_de_siempre():
    _, cur = _db([(f"n{i}", f"texto {i}") for i in range(10)])
    assert E.rowids_por_parecido(cur, "texto", "WHERE estado = 'activo'", (), 10) is None
    assert E.rowids_por_parecido(cur, "texto", "WHERE estado = 'activo'", (), 50) is None


def test_ventana_trae_el_recuerdo_nuevo_parecido_y_no_los_primeros_guardados():
    viejos = [(f"viejo_{i}", "receta de cocina con tomate y cebolla") for i in range(30)]
    nuevo = [("resolucion_timeout_hotspot_5ghz_intel", "resolucion del timeout del hotspot 5ghz en la tarjeta intel")]
    _, cur = _db(viejos + nuevo)
    # Con la regla vieja (ORDER BY rowid LIMIT 5) el recuerdo nuevo (rowid 31) quedaba fuera.
    viejos_primero = [r[0] for r in cur.execute("SELECT rowid FROM largo_plazo ORDER BY rowid LIMIT 5")]
    assert 31 not in viejos_primero
    ids = E.rowids_por_parecido(cur, "resoluciones timeouts hotspot 5ghzs intels", "WHERE estado = 'activo'", (), 5)
    assert ids is not None and ids[0] == 31


def test_ventana_respeta_el_filtro_de_estado():
    activos = [(f"a{i}", "nada que ver") for i in range(6)]
    dormidos = [("hotspot_intel", "hotspot intel timeout")]
    _, cur = _db(activos, extra_inactivos=dormidos)
    ids = E.rowids_por_parecido(cur, "hotspot intel", "WHERE estado = 'activo'", (), 3)
    rowid_dormido = cur.execute("SELECT rowid FROM largo_plazo WHERE estado='dormido'").fetchone()[0]
    assert ids is not None and rowid_dormido not in ids
    # Sin filtro (profundo) sí aparece.
    ids2 = E.rowids_por_parecido(cur, "hotspot intel", "", (), 3)
    assert ids2 is not None and ids2[0] == rowid_dormido


def test_ventana_nunca_supera_el_limite():
    _, cur = _db([(f"n{i}", "hotspot intel timeout") for i in range(40)])
    ids = E.rowids_por_parecido(cur, "hotspot", "WHERE estado = 'activo'", (), 7)
    assert ids is not None and len(ids) <= 7


@pytest.mark.parametrize("query", ["", "a", "!!"])
def test_pregunta_sin_trigramas_usa_la_consulta_de_siempre(query):
    _, cur = _db([(f"n{i}", "texto") for i in range(10)])
    assert E.rowids_por_parecido(cur, query, "WHERE estado = 'activo'", (), 3) is None


def test_comillas_en_la_pregunta_no_rompen_fts():
    _, cur = _db([(f"n{i}", 'dice "hola" mundo') for i in range(10)])
    ids = E.rowids_por_parecido(cur, 'hola "mundo"', "WHERE estado = 'activo'", (), 3)
    assert ids is not None


def test_ventana_sin_indice_trigram_devuelve_none_no_lanza():
    c = sqlite3.connect(":memory:")
    cur = c.cursor()
    cur.execute("CREATE TABLE largo_plazo (concepto TEXT, estado TEXT)")
    for i in range(10):
        cur.execute("INSERT INTO largo_plazo VALUES (?, 'activo')", (f"n{i}",))
    assert E.rowids_por_parecido(cur, "hotspot", "WHERE estado = 'activo'", (), 3) is None


# ───────────────────────── C. interruptor ─────────────────────────

def test_interruptor(monkeypatch):
    monkeypatch.delenv("BIORAG_ESCALA", raising=False)
    assert E.activa() is True
    monkeypatch.setenv("BIORAG_ESCALA", "0")
    assert E.activa() is False


def test_sin_tildes_es_la_normalizacion_del_indice():
    from core.memory import escala
    assert escala.sin_tildes("Diagnóstico") == "diagnostico"
    assert escala.sin_tildes("Semánticas") == "semanticas"
