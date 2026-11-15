"""E1 — QA HONESTA (segunda entrega): reglas estrictas del auditor.

Las tres reglas, tal como quedaron fijadas:

  1. OBSOLETA = "YA NO declara": el esperado declaraba la palabra en el snapshot
     de origen y ya no la declara en la base medida. Comprobación obligatoria:
     midiendo el snapshot salen 0; en la base viva sale 1 (el 0674).
  2. AMBIGUA SIN "contiene": solo alias completo, o palabra entera dentro del
     nombre. Con substring, `agente` reclamaba 119 nodos (exacto: 32).
  3. AMBIGUA POR MÉTRICA: para R@5 solo se aparta con MÁS DE 5 reclamantes (con 5
     o menos todos caben en el top-5); para R@1 desde 2. Una pregunta puede contar
     para el R@5 y no para el R@1.
"""
import importlib.util
import os
import sqlite3

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("evaluar_qa", os.path.join(RAIZ, "scripts", "evaluar_qa.py"))
EQ = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(EQ)

SNAPSHOT = os.path.join(RAIZ, "snapshots", "qa_escape_qcr_20260811.db")


def _db(tmp_path, nombre, nodos):
    """DB mínima con (concepto, sinonimos). Devuelve el motor abierto."""
    from core.memory_store import SQLiteMemoryBioRAG

    ruta = str(tmp_path / nombre)
    db = SQLiteMemoryBioRAG(ruta)
    for concepto, sinonimos in nodos:
        db.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, sinonimos, estado) VALUES (?,?,?,?)",
            (concepto, f"texto {concepto}", sinonimos, "activo"),
        )
    db.conn.commit()
    return db, ruta


def _caso(id_, query, esperado, categoria="sinonimo"):
    return {"id": id_, "query": query, "concepto_esperado": esperado, "categoria": categoria}


# ── Regla 2: coincidencia ESTRICTA, sin "contiene" ────────────────────────

def test_palabra_entera_no_substring():
    """`agente` NO la declara un nodo que solo tiene `agentes` o `agencia`."""
    assert EQ._nodo_declara("ficha_agentes", "otra-cosa", ["agente"]) is False
    assert EQ._nodo_declara("ficha_agente", "otra-cosa", ["agente"]) is True
    assert EQ._nodo_declara("x", "agentes,rrhh", ["agente"]) is False
    assert EQ._nodo_declara("x", "agente,rrhh", ["agente"]) is True


def test_alias_completo_no_parte_de_un_alias():
    assert EQ._nodo_declara("x", "filtro-de-impacto", ["filtro"]) is False
    assert EQ._nodo_declara("x", "filtro", ["filtro"]) is True
    assert EQ._nodo_declara("x", "filtro-arquitecto-prolijo", ["filtro", "arquitecto", "prolijo"]) is True


def test_frase_multipalabra_en_el_nombre():
    """La consulta completa, como palabras seguidas, dentro del nombre."""
    assert EQ._nodo_declara("oracle_identification_manual", "", ["oracle", "identification"]) is True
    assert EQ._nodo_declara("identificacion_obligatoria_oraculo", "", ["oracle", "identification"]) is False


def test_separadores_y_tildes():
    assert EQ._nodo_declara("x", "Pre-Validación,compuerta", ["pre", "validacion"]) is True
    assert EQ._nodo_declara("metodología_dennys", "", ["metodologia"]) is True


# ── Regla 1: OBSOLETA = "YA NO declara", contra el snapshot de origen ─────

def test_obsoleta_exige_que_antes_si_declarara(tmp_path):
    ref, ruta_ref = _db(tmp_path, "ref.db", [
        ("compuerta-pre-validacion", "pre-validacion,filtro-arquitecto-prolijo"),
        ("otro_nodo", "cosa"),
    ])
    medido, _ = _db(tmp_path, "medido.db", [
        ("compuerta-pre-validacion", "pre-validacion,filtro-de-impacto"),   # el alias cambió
        ("otro_nodo", "cosa"),
    ])
    marcas = EQ.clasificar_casos_sinonimo(
        medido,
        [_caso("0674", "filtro-arquitecto-prolijo", "compuerta-pre-validacion")],
        ruta_ref,
    )
    assert marcas["0674"]["obsoleta"] is True


def test_si_nunca_lo_declaro_no_es_obsoleta(tmp_path):
    """Sin la referencia no se puede afirmar "YA NO": no se inventa."""
    medido, _ = _db(tmp_path, "medido.db", [("compuerta-pre-validacion", "pre-validacion")])
    marcas = EQ.clasificar_casos_sinonimo(
        medido, [_caso("0674", "filtro-arquitecto-prolijo", "compuerta-pre-validacion")], None
    )
    assert marcas["0674"]["obsoleta"] is False


def test_midiendo_el_snapshot_salen_cero_obsoletas(tmp_path):
    """Regla de comprobación del auditor: referencia == base medida -> 0.

    OJO: se trabaja sobre una COPIA. Abrir el snapshot directo con el motor lo
    pasa a modo WAL y le cambia el sha256 — regla 7 de la guía: ninguna DB real se
    toca, siempre copias. Está comprobado: fue un fallo de esta misma prueba.
    """
    if not os.path.exists(SNAPSHOT):
        pytest.skip("snapshot no disponible")
    import hashlib
    import json
    import shutil

    copia = str(tmp_path / "snapshot_copia.db")
    shutil.copyfile(SNAPSHOT, copia)
    antes = hashlib.sha256(open(SNAPSHOT, "rb").read()).hexdigest()

    casos = [json.loads(l) for l in open(os.path.join(RAIZ, "scripts", "casos_qa_baseline_v1.jsonl"),
                                         encoding="utf-8") if l.strip()]
    from core.memory_store import SQLiteMemoryBioRAG

    db = SQLiteMemoryBioRAG(db_path=copia)
    # Se pasa None porque es la misma base: el código lo trata igual.
    marcas = EQ.clasificar_casos_sinonimo(db, casos, None)
    assert sum(1 for m in marcas.values() if m["obsoleta"]) == 0

    # Y el original sigue intacto.
    despues = hashlib.sha256(open(SNAPSHOT, "rb").read()).hexdigest()
    assert antes == despues, "el snapshot no se toca: se trabaja sobre copias"


# ── Regla 3: umbral por métrica ───────────────────────────────────────────

def test_umbral_r5_cinco_o_menos_no_se_aparta(tmp_path):
    nodos = [(f"nodo_{i}", "perfil") for i in range(5)]
    db, _ = _db(tmp_path, "cinco.db", nodos)
    m = EQ.clasificar_casos_sinonimo(db, [_caso("1", "perfil", "nodo_0")])
    assert m["1"]["n_reclamantes"] == 5
    assert m["1"]["ambigua_r5"] is False, "con 5 o menos todos caben en el top-5"
    assert m["1"]["ambigua_r1"] is True, "para R@1 solo uno puede ser el primero"


def test_umbral_r5_seis_o_mas_si_se_aparta(tmp_path):
    nodos = [(f"nodo_{i}", "perfil") for i in range(6)]
    db, _ = _db(tmp_path, "seis.db", nodos)
    m = EQ.clasificar_casos_sinonimo(db, [_caso("1", "perfil", "nodo_0")])
    assert m["1"]["n_reclamantes"] == 6
    assert m["1"]["ambigua_r5"] is True
    assert m["1"]["ambigua_r1"] is True


def test_un_solo_reclamante_no_es_ambigua(tmp_path):
    db, _ = _db(tmp_path, "uno.db", [("unico", "palabra"), ("otro", "distinta")])
    m = EQ.clasificar_casos_sinonimo(db, [_caso("1", "palabra", "unico")])
    assert m["1"]["n_reclamantes"] == 1
    assert m["1"]["ambigua_r5"] is False
    assert m["1"]["ambigua_r1"] is False


# ── La tabla honesta, por métrica ─────────────────────────────────────────

def _reg(id_, cat, hit5, hit1, rr, ap5, ap1):
    return {"id": id_, "categoria": cat, "hit5": hit5, "hit1": hit1, "rr": rr,
            "apartado_r5": ap5, "apartado_r1": ap1}


def test_una_pregunta_puede_contar_para_r5_y_no_para_r1():
    registros = [
        # 4 reclamantes: cuenta para R@5, se aparta para R@1
        _reg("a", "sinonimo", True, False, 0.5, ap5=False, ap1=True),
        _reg("b", "sinonimo", True, True, 1.0, ap5=False, ap1=False),
    ]
    t5 = EQ._tabla_honesta(registros, "r5")
    t1 = EQ._tabla_honesta(registros, "r1")
    assert t5["sinonimo"]["n"] == 2, "para R@5 el caso 'a' sigue contando"
    assert t1["sinonimo"]["n"] == 1, "para R@1 el caso 'a' se aparta"
    assert t5["sinonimo"]["h5"] == 2
    assert t1["sinonimo"]["h1"] == 1


def test_apartar_una_que_pasa_no_entra_en_la_tabla():
    registros = [_reg("pasa", "sinonimo", True, True, 1.0, ap5=True, ap1=True),
                 _reg("queda", "sinonimo", True, True, 1.0, ap5=False, ap1=False)]
    for metrica in ("r5", "r1"):
        t = EQ._tabla_honesta(registros, metrica)
        assert t["sinonimo"]["n"] == 1


# ── El informe lo dice ────────────────────────────────────────────────────

def test_el_informe_declara_que_el_umbral_se_decidio_despues():
    fuente = open(os.path.join(RAIZ, "scripts", "evaluar_qa.py"), encoding="utf-8").read()
    assert "UMBRAL_AMBIGUA_R5 = 5" in fuente
    assert "UMBRAL_AMBIGUA_R1 = 2" in fuente
    assert "ese umbral se decidió DESPUÉS de ver la primera medición" in fuente


# ── Menores de la revisión de E1b ─────────────────────────────────────────

def test_json_usa_no_top1_y_no_llama_fallos_al_puesto():
    """El JSON no debe llamar 'fallos' a lo que es 'no llegó al primer puesto'."""
    fuente = open(os.path.join(RAIZ, "scripts", "evaluar_qa.py"), encoding="utf-8").read()
    bloque = fuente[fuente.index('"global_r1"'):fuente.index('"categorias"', fuente.index('"global_r1"'))]
    assert '"no_top1"' in bloque
    assert '"fallos"' not in bloque


def test_la_referencia_se_abre_inmutable_si_no_hay_wal():
    """Abrir el snapshot sin immutable puede crearle -wal y cambiarle el sha256.

    Se usa immutable=1 SOLO si no hay sidecar -wal: con immutable, SQLite ignora
    un -wal existente y una base recién escrita se leería vacía (lo detectó el
    propio test de la regla 1 al fallar).
    """
    fuente = open(os.path.join(RAIZ, "scripts", "evaluar_qa.py"), encoding="utf-8").read()
    assert '"&immutable=1"' in fuente
    assert 'os.path.exists(str(ruta_referencia) + "-wal")' in fuente


# ── Higiene E2b-C: la QA no debe tocar la base que mide ───────────────────

def _base_con_filas(ruta, wal=False):
    import sqlite3
    con = sqlite3.connect(ruta)
    if wal:
        con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE t (x TEXT)")
    con.executemany("INSERT INTO t VALUES (?)", [("a",), ("b",)])
    con.commit()
    con.close()


def test_copia_no_toca_la_base_limpia(tmp_path):
    """Sin -wal: se abre immutable, el original no se toca y no aparecen sidecars."""
    import hashlib

    origen = tmp_path / "origen.db"
    _base_con_filas(str(origen))
    for ext in ("-wal", "-shm"):
        if (str(origen) + ext) and os.path.exists(str(origen) + ext):
            os.remove(str(origen) + ext)
    sha = hashlib.sha256(origen.read_bytes()).hexdigest()

    destino = tmp_path / "copia.db"
    info = EQ._copiar_base_para_qa(origen, destino)

    assert "immutable=1" in info["modo"]
    assert info["sha_antes"] == info["sha_despues"] == sha
    assert not os.path.exists(str(origen) + "-wal")
    assert not os.path.exists(str(origen) + "-shm")

    import sqlite3
    con = sqlite3.connect(destino)
    assert con.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 2
    con.close()


def test_copia_con_wal_no_pierde_datos_ni_deja_basura(tmp_path):
    """Con -wal vivo: hay que leerlo (mode=ro) y borrar solo lo que aparezca."""
    origen = tmp_path / "origen_wal.db"
    con = sqlite3.connect(origen)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE t (x TEXT)")
    con.execute("INSERT INTO t VALUES ('wal_vivo')")
    con.commit()
    # se deja ABIERTA: la fila vive en el -wal, no en el .db
    assert os.path.exists(str(origen) + "-wal")

    destino = tmp_path / "copia_wal.db"
    info = EQ._copiar_base_para_qa(origen, destino)
    con.close()

    assert "immutable" not in info["modo"], "con -wal vivo, immutable perdería las filas"
    ver = sqlite3.connect(destino)
    assert ver.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    ver.close()


# ── E2b: banderas de diagnóstico (apagadas por defecto) ───────────────────

def test_la_palabra_de_ruido_solo_entra_en_la_busqueda():
    """El ruido no debe tocar `query`: el control de ambiguas y los informes
    siguen leyendo la consulta original."""
    fuente = open(os.path.join(RAIZ, "scripts", "evaluar_qa.py"), encoding="utf-8").read()
    assert 'RUIDO = os.environ.get("BIORAG_QA_RUIDO", "").strip()' in fuente
    # las dos búsquedas del arnés pasan por el envoltorio
    assert fuente.count("_consulta_buscada(query)") == 2
    # y ninguna búsqueda usa `query` a pelo
    assert "buscar_por_frase(query," not in fuente.replace("buscar_por_frase(query, profundidad", "")


def test_el_censo_del_tematico_esta_apagado_por_defecto():
    """El censo envuelve el score; solo si se pide explícitamente."""
    fuente = open(os.path.join(RAIZ, "scripts", "evaluar_qa.py"), encoding="utf-8").read()
    assert 'CENSO_TEMATICO = os.environ.get("BIORAG_QA_TEMATICO_CENSO", "") == "1"' in fuente
    # el espía devuelve el MISMO valor que el cálculo original
    assert "return _hibrido_original(self, **kw)" in fuente
