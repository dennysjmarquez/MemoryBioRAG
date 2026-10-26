"""E1 — QA HONESTA: obsoletas y ambiguas separadas del examen.

POR QUÉ estas pruebas: en la base viva, 6 de los 7 fallos de la QA venían del
EXAMEN y no del buscador. Cinco eran una palabra suelta que decenas de recuerdos
declaran (`agente`: 110 recuerdos son respuesta válida). Contarlos como fallos del
motor no mide el motor.

Las reglas se fijaron ANTES de medir y no se ajustan después de ver resultados:
  1. OBSOLETA — el recuerdo esperado ya no declara esa palabra como alias.
  2. AMBIGUA  — 2 o más recuerdos reclaman la palabra (alias o nombre).
  3. Se calculan en tiempo de QA contra la base medida; el JSONL no se toca.

Lo que se fija aquí:
  - la normalización (tildes, mayúsculas, `_`/`-`/`,` son el mismo separador);
  - una obsoleta, una ambigua y una normal que NO se aparta;
  - un caso que hoy PASA y aun así se aparta (que el reporte no parezca un truco);
  - que la QA honesta use el resultado final, y que el bloque de métricas exista.
"""
import importlib.util
import os
import sqlite3

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("evaluar_qa", os.path.join(RAIZ, "scripts", "evaluar_qa.py"))
EQ = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(EQ)


def _db_con(tmp_path, nodos):
    """Crea una DB mínima con (concepto, sinonimos) y devuelve el motor abierto."""
    from core.memory_store import SQLiteMemoryBioRAG

    ruta = str(tmp_path / "qa_honesta.db")
    db = SQLiteMemoryBioRAG(ruta)
    for concepto, sinonimos in nodos:
        db.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, sinonimos, estado) VALUES (?,?,?,?)",
            (concepto, f"texto de {concepto}", sinonimos, "activo"),
        )
    db.conn.commit()
    return db


def _caso(id_, query, esperado, categoria="sinonimo"):
    return {"id": id_, "query": query, "concepto_esperado": esperado, "categoria": categoria}


# ── normalización ──────────────────────────────────────────────────────────

def test_separadores_y_tildes_son_lo_mismo():
    assert EQ._clave_texto("pre-validación") == EQ._clave_texto("pre_validacion")
    assert EQ._clave_texto("Filtro, Arquitecto") == "filtro arquitecto"
    assert EQ._clave_texto("  Metodología  ") == "metodologia"
    assert EQ._clave_texto("") == ""


# ── las tres reglas, en una sola DB ────────────────────────────────────────

def test_obsoleta_ambigua_y_normal(tmp_path):
    db = _db_con(tmp_path, [
        # el esperado NO declara la palabra: OBSOLETA
        ("compuerta-pre-validacion", "pre-validacion,compuerta,juicio-accion"),
        # dos nodos reclaman "perfil": AMBIGUA
        ("dennys-identidad-profunda", "perfil,ingeniero"),
        ("dennys_perfil_gustos", "preferencia,perfil_personal"),
        # un solo nodo reclama "juramento": NORMAL, no se aparta
        ("juramento-athena", "juramento,juramento-verdad,verdad"),
    ])
    casos = [
        _caso("0674", "filtro-arquitecto-prolijo", "compuerta-pre-validacion"),
        _caso("0514", "perfil", "dennys-identidad-profunda"),
        _caso("0301", "juramento", "juramento-athena"),
    ]
    marcas = EQ.clasificar_casos_sinonimo(db, casos)

    assert marcas["0674"]["obsoleta"] is True, "el esperado no declara el alias"
    assert marcas["0514"]["ambigua"] is True, "dos nodos reclaman 'perfil'"
    assert marcas["0514"]["n_ambigua"] == 2
    # la normal NO se aparta por ninguna de las dos reglas
    assert marcas["0301"]["obsoleta"] is False
    assert marcas["0301"]["ambigua"] is False

    # el examen no se toca
    assert len(casos) == 3 and casos[0]["query"] == "filtro-arquitecto-prolijo"


def test_ambigua_tambien_cuenta_el_nombre_no_solo_el_alias(tmp_path):
    db = _db_con(tmp_path, [
        ("regla_uno", "norma,regla"),
        ("regla_dos", "otra-cosa"),          # la lleva en el NOMBRE, no en el alias
    ])
    marcas = EQ.clasificar_casos_sinonimo(db, [_caso("0734", "regla", "regla_uno")])
    assert marcas["0734"]["ambigua"] is True
    assert marcas["0734"]["n_ambigua"] == 2


def test_la_palabra_no_declarada_por_nadie_es_obsoleta_no_ambigua(tmp_path):
    """`prolijo` no existe en la base: no hay ambigüedad, hay un puente que falta."""
    db = _db_con(tmp_path, [("compuerta-pre-validacion", "pre-validacion,compuerta")])
    marcas = EQ.clasificar_casos_sinonimo(db, [_caso("0674", "filtro-arquitecto-prolijo",
                                                     "compuerta-pre-validacion")])
    assert marcas["0674"]["obsoleta"] is True
    assert marcas["0674"]["ambigua"] is False
    assert marcas["0674"]["n_ambigua"] == 0


def test_solo_mira_casos_sinonimo(tmp_path):
    db = _db_con(tmp_path, [("nodo", "alias,cosa")])
    marcas = EQ.clasificar_casos_sinonimo(db, [
        _caso("0001", "lo que sea", "nodo", categoria="literal"),
        _caso("0002", "lo que sea", "nodo", categoria="negativo"),
    ])
    assert marcas == {}, "otras categorías no se apartan nunca"


def test_esperado_inexistente_no_rompe(tmp_path):
    db = _db_con(tmp_path, [("nodo", "alias")])
    marcas = EQ.clasificar_casos_sinonimo(db, [_caso("9999", "alias", "nod_que_no_existe")])
    assert marcas["9999"]["obsoleta"] is True


# ── la tabla honesta usa el resultado FINAL del caso ───────────────────────

def test_tabla_honesta_excluye_apartados_e_incluye_el_resto():
    registros = [
        {"id": "a", "categoria": "sinonimo", "hit5": True, "hit1": True, "rr": 1.0, "apartado": False},
        {"id": "b", "categoria": "sinonimo", "hit5": False, "hit1": False, "rr": 0.0, "apartado": False},
        {"id": "c", "categoria": "sinonimo", "hit5": False, "hit1": False, "rr": 0.0, "apartado": True},
        {"id": "d", "categoria": "literal", "hit5": True, "hit1": True, "rr": 1.0, "apartado": False},
    ]
    tabla = EQ._tabla_honesta(registros)
    assert tabla["sinonimo"] == {"n": 2, "h5": 1, "h1": 1, "rr": 1.0}
    assert tabla["literal"] == {"n": 1, "h5": 1, "h1": 1, "rr": 1.0}


def test_apartar_una_que_pasa_subiria_el_numero_y_por_eso_se_lista():
    """El registro de una que PASA y se aparta no entra en la tabla honesta.

    Es el riesgo real de esta etapa: si solo se listaran las que fallan, apartar
    casos podría maquillar el resultado. Por eso el reporte imprime también las que
    pasan (ver la columna 'pasan hoy' del bloque OBSOLETAS/AMBIGUAS).
    """
    registros = [
        {"id": "pasa_y_se_aparta", "categoria": "sinonimo", "hit5": True, "hit1": False,
         "rr": 0.5, "apartado": True},
        {"id": "queda", "categoria": "sinonimo", "hit5": True, "hit1": True, "rr": 1.0,
         "apartado": False},
    ]
    tabla = EQ._tabla_honesta(registros)
    assert tabla["sinonimo"]["n"] == 1
    assert tabla["sinonimo"]["h5"] == 1


# ── el reporte y las métricas ──────────────────────────────────────────────

def test_el_reporte_sale_con_las_dos_columnas():
    """La sección existe en el código y nombra las dos QA (texto del informe)."""
    fuente = open(os.path.join(RAIZ, "scripts", "evaluar_qa.py"), encoding="utf-8").read()
    assert "QA HONESTA (E1)" in fuente
    assert "CLÁSICA n" in fuente and "HONESTA n" in fuente
    assert "La GATE sigue usando la CLÁSICA" in fuente


def test_las_metricas_llevan_el_bloque_honesto():
    fuente = open(os.path.join(RAIZ, "scripts", "evaluar_qa.py"), encoding="utf-8").read()
    assert 'metrics["qa_honesta"]' in fuente
    for clave in ("obsoletas", "ambiguas", "casos_apartados", "pasa_hoy"):
        assert clave in fuente
