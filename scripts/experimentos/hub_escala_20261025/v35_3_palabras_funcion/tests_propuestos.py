

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
