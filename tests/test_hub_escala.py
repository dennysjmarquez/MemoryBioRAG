"""v35.2 — Concept hub a escala: funciona igual con 1, 6 o miles de hubs.

Cada prueba cubre un modo de falla real encontrado en la base viva (1086 hubs):
  - una palabra común compartida por muchos hubs ya no fuerza un ganador cualquiera;
  - la palabra exacta y rara manda sobre la misma familia de palabras;
  - dos hubs del mismo recuerdo son aliados, no rivales;
  - el índice en memoria se entera de cualquier cambio en las tablas (sin reiniciar);
  - el tiempo por consulta no crece con la cantidad de hubs;
  - BIORAG_HUB_ESCALA=0 vuelve exactamente al cálculo anterior.
"""
import os
import sqlite3
import time

import pytest

import core.concept_hub as ch


def _base(hubs):
    """hubs: lista de (hub_id, canonical, [(texto, angulo), ...])."""
    conn = sqlite3.connect(":memory:")
    ch.crear_tablas(conn)
    for hub_id, canonical, puentes in hubs:
        conn.execute("INSERT INTO concept_hubs (hub_id, canonical_node, description, created_at) VALUES (?,?,?,0)",
                     (hub_id, canonical, ""))
        conn.execute("INSERT INTO concept_hub_nodes (hub_id, node_concepto, role) VALUES (?,?,'canonical')",
                     (hub_id, canonical))
        for texto, angulo in puentes:
            conn.execute("INSERT INTO concept_hub_bridges (hub_id, bridge_text, angle, weight) VALUES (?,?,?,1.0)",
                         (hub_id, texto, angulo))
    conn.commit()
    return conn


TRABAJO = ("trabajo_previo", "historia_tasajera", [
    ("oficios manuales rurales y empleo previo al desarrollo de software", "sinonimo"),
    ("como sobrevivia economicamente dennys antes de entrar a la tecnologia", "problema"),
    ("fumigador de campo y operario de tasajera en rufino", "solucion"),
    ("vida laboral en el monte antes de aprender programacion e ingenieria", "situacion"),
    ("que hacia dennys para sobrevivir y ganar dinero antes de ser programador", "ingenuo"),
])


def _relleno(n, palabra_comun="regla"):
    """n hubs de recuerdos distintos que comparten una palabra común en su sinónimo."""
    return [(f"hub_r{i}", f"recuerdo_{i}", [
        (f"{palabra_comun} tema{i} asunto{i}", "sinonimo"),
        (f"problema del asunto{i} con detalle{i}", "problema"),
        (f"solucion para tema{i} usando cosa{i}", "solucion"),
        (f"contexto{i} de uso{i}", "situacion"),
        (f"como hago lo del tema{i}", "ingenuo"),
    ]) for i in range(n)]


@pytest.fixture(autouse=True)
def _hub_escala_on(monkeypatch):
    monkeypatch.setenv("BIORAG_HUB_ESCALA", "1")
    ch._INDICE_HUBS.clear()
    yield
    ch._INDICE_HUBS.clear()


def test_un_solo_hub_cruza_el_abismo_lexico():
    conn = _base([TRABAJO])
    r = ch.expandir_query_con_hub("qué hacía antes de ser programador", conn)
    assert r and r["canonical_nodes"][0] == "historia_tasajera"
    assert r["hub_ventaja"] == pytest.approx(1.0)


def test_abismo_lexico_sigue_ganando_entre_cientos_de_hubs():
    conn = _base([TRABAJO] + _relleno(400, palabra_comun="programacion"))
    r = ch.expandir_query_con_hub("qué hacía antes de ser programador", conn)
    assert r and r["canonical_nodes"][0] == "historia_tasajera"


def test_palabra_comun_compartida_no_fuerza_un_ganador():
    conn = _base(_relleno(60, palabra_comun="regla"))
    assert ch.expandir_query_con_hub("regla", conn) is None


def test_la_misma_palabra_con_pocos_hubs_si_decide():
    # Con un solo hub que la tiene, la palabra sí identifica al recuerdo.
    conn = _base(_relleno(1, palabra_comun="regla"))
    r = ch.expandir_query_con_hub("regla", conn)
    assert r and r["canonical_nodes"][0] == "recuerdo_0"


def test_palabra_rara_exacta_gana_entre_muchos():
    conn = _base(_relleno(200, palabra_comun="regla"))
    r = ch.expandir_query_con_hub("regla tema137", conn)
    assert r and r["canonical_nodes"][0] == "recuerdo_137"
    assert r["hub_confidence"] >= 0.4


def test_dos_hubs_del_mismo_recuerdo_son_aliados():
    gemelo = ("hub_historia_tasajera", "historia_tasajera", [
        ("empleos de campo antes de ser programador", "sinonimo"),
        ("trabajos duros antes de la informatica", "problema"),
        ("fumigar y cortar en tasajera", "solucion"),
        ("historia de vida antes de programar", "situacion"),
        ("que hacia antes de ser programador", "ingenuo"),
    ])
    conn = _base([TRABAJO, gemelo])
    r = ch.expandir_query_con_hub("qué hacía antes de ser programador", conn)
    assert r and r["canonical_nodes"][0] == "historia_tasajera"
    assert r["hub_ventaja"] == pytest.approx(1.0)


def test_indice_se_entera_de_altas_y_cambios_sin_reiniciar():
    conn = _base(_relleno(3, palabra_comun="regla"))
    assert ch.expandir_query_con_hub("murcielago nocturno", conn) is None
    conn.execute("INSERT INTO concept_hubs (hub_id, canonical_node, description, created_at) VALUES ('h_n','nuevo','',0)")
    conn.execute("INSERT INTO concept_hub_bridges (hub_id, bridge_text, angle, weight) "
                 "VALUES ('h_n','murcielago nocturno de la cueva','problema',1.0)")
    conn.commit()
    r = ch.expandir_query_con_hub("murcielago nocturno", conn)
    assert r and r["canonical_nodes"][0] == "nuevo"
    # Cambio de ángulo del mismo largo (problema → solucion) también invalida el índice.
    antes = ch._firma_hubs(conn)
    conn.execute("UPDATE concept_hub_bridges SET angle='solucion' WHERE hub_id='h_n'")
    conn.commit()
    assert ch._firma_hubs(conn) != antes
    # Cambio del recuerdo canónico también.
    conn.execute("UPDATE concept_hubs SET canonical_node='nuevo2' WHERE hub_id='h_n'")
    conn.commit()
    r = ch.expandir_query_con_hub("murcielago nocturno", conn)
    assert r and r["canonical_nodes"][0] == "nuevo2"


def test_sin_tablas_o_vacio_no_rompe():
    conn = sqlite3.connect(":memory:")
    assert ch.expandir_query_con_hub("lo que sea", conn) is None
    ch.crear_tablas(conn)
    assert ch.expandir_query_con_hub("lo que sea", conn) is None
    assert ch.expandir_query_con_hub("", conn) is None


def test_tiempo_por_consulta_no_crece_con_los_hubs():
    conn = _base(_relleno(3000, palabra_comun="regla"))
    ch.expandir_query_con_hub("calentar indice", conn)
    t = time.perf_counter()
    for _ in range(20):
        ch.expandir_query_con_hub("tema2999 asunto2999", conn)
    ms = (time.perf_counter() - t) / 20 * 1000
    assert ms < 60, f"{ms:.1f} ms por consulta con 3000 hubs"


def test_ablacion_vuelve_al_calculo_anterior(monkeypatch):
    conn = _base([TRABAJO] + _relleno(30, palabra_comun="regla"))
    monkeypatch.setenv("BIORAG_HUB_ESCALA", "0")
    for q in ["qué hacía antes de ser programador", "regla", "regla tema7", "fumigador rufino"]:
        r = ch.expandir_query_con_hub(q, conn)
        assert r is None or "hub_ventaja" not in r  # camino viejo: sin campos nuevos


def test_puente_diminuto_con_palabra_comun_no_gana_al_que_explica_la_rara():
    # Caso real 0666: "algo no tiene identidad" (una sola palabra con contenido, común)
    # le ganaba con confianza alta a "autonomia identidad cooperacion respeto".
    relleno = [(f"hub_i{i}", f"ident_{i}", [(f"identidad tema{i}", "situacion")]) for i in range(60)]
    diminuto = ("hub_alguien", "alguien_vs_algo", [("algo no tiene identidad", "sinonimo")])
    correcto = ("hub_respeto", "identidad_y_respeto", [("autonomia identidad cooperacion respeto", "sinonimo")])
    conn = _base(relleno + [diminuto, correcto])
    r = ch.expandir_query_con_hub("identidad ys respeto oec", conn, threshold=0.0)
    assert r and r["canonical_nodes"][0] == "identidad_y_respeto"


# Palabras como "antes", "hacía", "cuando" o "no" están en la lista de palabras vacías de la
# búsqueda por texto, pero en una paráfrasis cambian el sentido. Caso real (base viva,
# 1087 hubs): "qué hacía antes de ser programador" quedaba en {ser, programador} y
# cualquier puente con "programador" empataba con el correcto; el hub no decidía.
RIVALES_PROGRAMADOR = [
    ("hub_blog", "perfil_blog", [("blog tecnico de un programador frontend y seguridad", "situacion")]),
    ("hub_ddd", "reglas_dominio", [("acuerdos previos entre programador y dueno del negocio", "situacion")]),
    ("hub_cv", "cv_secciones", [("experiencia del programador en cada tecnologia", "situacion")]),
]


def _relleno_realista(n):
    """Hubs con las palabras de función de una base real: "de", "que", "ser" en muchos,
    "antes" en pocos."""
    hubs = []
    for i in range(n):
        puentes = [(f"que hago con el tema{i} de asunto{i}", "ingenuo"),
                   (f"solucion de tema{i} usando cosa{i}", "solucion")]
        if i % 4 == 0:
            puentes.append((f"puede ser el detalle{i} del contexto{i}", "situacion"))
        if i % 25 == 0:
            puentes.append((f"revisar antes el asunto{i}", "problema"))
        hubs.append((f"hub_f{i}", f"recuerdo_f{i}", puentes))
    return hubs


def test_palabras_de_funcion_que_cambian_el_sentido_cuentan():
    conn = _base([TRABAJO] + RIVALES_PROGRAMADOR + _relleno_realista(400))
    r = ch.expandir_query_con_hub("qué hacía antes de ser programador", conn)
    assert r is not None and r["hub_id"] == "trabajo_previo"
    assert r["hub_confidence"] >= 0.40


def test_palabras_que_estan_en_casi_todos_los_puentes_no_deciden_solas():
    conn = _base([TRABAJO] + RIVALES_PROGRAMADOR + _relleno_realista(400))
    assert ch.expandir_query_con_hub("que de", conn) is None


def test_el_tipo_de_puente_no_hace_ganar_a_un_puente_que_explica_menos():
    # Caso real (base viva, 1087 hubs): los rivales eran puentes "sinónimo" (×1.5)
    # que solo compartían "programador"; el correcto, "ingenuo" (antes ×0.85), contenía la
    # pregunta entera. Con ingenuo ×0.85 el hub no decidía.
    rivales_sinonimo = [(h, c, [(t, "sinonimo") for t, _ in p]) for h, c, p in RIVALES_PROGRAMADOR]
    conn = _base([TRABAJO] + rivales_sinonimo + _relleno_realista(400))
    r = ch.expandir_query_con_hub("qué hacía antes de ser programador", conn)
    assert r is not None and r["hub_id"] == "trabajo_previo"
    assert r["hub_confidence"] >= 0.40
