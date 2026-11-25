"""
Cambio 1 (auditoría 25-11): las reglas automáticas que crean o refuerzan sinapsis
no tocan los enlaces del agente (`manual`, `manual_v7`), en ninguno de los dos sentidos.

`test_enlaces_del_agente_intocables.py` ya cubre el desgaste, la poda y la hormiguita.
Faltaba cubrir el camino de NACIMIENTO, que antes de este cambio modificaba los manuales:
  - B1–B4 `auto_vincular` y B5 `vincular_por_sinonimos`: ON CONFLICT → peso = MAX(...) y ultimo_uso;
  - B6 co-ocurrencia de sesión: +0.1 y ultimo_uso, solo en el sentido c1→c2;
  - B7 co-ocurrencia en comunicaciones: +0.05 y ultimo_uso;
  - B10 refuerzo de ráfaga: +0.1 en los dos sentidos.
Ver docs/ALGORITMO_NACIMIENTO_SINAPSIS.md §4 (P6).

Cada test lleva un CONTROL con un enlace automático, que debe seguir cambiando como antes.
Así se demuestra que el camino se ejecutó de verdad y que el cambio solo excluye a los manuales.
"""

import time

import pytest

VIEJO = time.time() - 30 * 86400


@pytest.fixture()
def cerebro(tmp_path):
    from core.memory_store import SQLiteMemoryBioRAG
    c = SQLiteMemoryBioRAG(str(tmp_path / "manual_nacimiento.db"))
    # El DMN corre al abrir y en cada sueño, pero nunca pisa un par existente
    # (NOT EXISTS / DO NOTHING), así que no interfiere con los pares medidos.
    yield c
    try:
        c.cerrar_sistema()
    except Exception:
        pass


def _percibir(c, concepto, contenido, sinonimos=""):
    c.percibir_corto_plazo(concepto, contenido, sinonimos, "General", [])


def _arista(c, o, d, peso, tipo, ultimo_uso=VIEJO, ambos=True):
    pares = ((o, d), (d, o)) if ambos else ((o, d),)
    for a, b in pares:
        c.cursor.execute(
            "INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en, ultimo_uso) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (a, b, peso, tipo, VIEJO, ultimo_uso),
        )
    c.conn.commit()


def _fila(c, o, d):
    c.cursor.execute("SELECT peso, tipo, ultimo_uso FROM sinapsis WHERE origen = ? AND destino = ?", (o, d))
    return c.cursor.fetchone()


def _manual_intacto(c, a, b, peso=0.5, tipo="manual"):
    for o, d in ((a, b), (b, a)):
        fila = _fila(c, o, d)
        assert fila is not None, f"{o}->{d} desapareció"
        assert fila[0] == pytest.approx(peso), f"{o}->{d}: peso {fila[0]} != {peso}"
        assert fila[1] == tipo, f"{o}->{d}: tipo {fila[1]} != {tipo}"
        assert fila[2] == pytest.approx(VIEJO), f"{o}->{d}: ultimo_uso cambió"


TXT_SALSA = "Salsa de tomate maduro con ajo albahaca aceite cocinar veinte minutos."
TXT_PASTA = "Pasta con salsa de tomate maduro, ajo, albahaca y aceite de oliva."
TXT_PIZZA = "Pizza con salsa de tomate maduro, ajo, albahaca y aceite al horno."


def _tres_recetas_consolidadas(c):
    _percibir(c, "receta_salsa_tomate", TXT_SALSA, "tomate, salsa")
    _percibir(c, "receta_pasta_tomate", TXT_PASTA, "tomate, pasta")
    _percibir(c, "receta_pizza_tomate", TXT_PIZZA, "tomate, pizza")
    c.ciclo_sueno_consolidacion()
    c.cursor.execute("DELETE FROM sinapsis")
    c.conn.commit()


@pytest.mark.parametrize("tipo", ["manual", "manual_v7"])
def test_auto_vincular_no_toca_manual(cerebro, tipo):
    from core.sinapsis import auto_vincular
    _tres_recetas_consolidadas(cerebro)
    _arista(cerebro, "receta_pasta_tomate", "receta_salsa_tomate", 0.5, tipo)
    _arista(cerebro, "receta_pasta_tomate", "receta_pizza_tomate", 0.10, "co_ocurrencia", ambos=False)
    auto_vincular(cerebro, "receta_pasta_tomate", TXT_PASTA)
    _manual_intacto(cerebro, "receta_pasta_tomate", "receta_salsa_tomate", tipo=tipo)
    # Control: el automático sí se refuerza (MAX con la similitud nueva)
    assert _fila(cerebro, "receta_pasta_tomate", "receta_pizza_tomate")[0] > 0.10


def test_vincular_por_sinonimos_no_toca_manual(cerebro):
    from core.sinapsis import vincular_por_sinonimos
    _tres_recetas_consolidadas(cerebro)
    _arista(cerebro, "receta_pasta_tomate", "receta_salsa_tomate", 0.5, "manual")
    vincular_por_sinonimos(cerebro, "receta_pasta_tomate", "tomate")
    _manual_intacto(cerebro, "receta_pasta_tomate", "receta_salsa_tomate")
    # Control: el sinónimo sí enlaza con quien no tenía enlace previo
    fila = _fila(cerebro, "receta_pasta_tomate", "receta_pizza_tomate")
    assert fila is not None and fila[1] == "sinonimo_explicito"


def test_co_ocurrencia_de_sesion_no_toca_manual(cerebro):
    _percibir(cerebro, "receta_salsa_tomate", TXT_SALSA)
    _percibir(cerebro, "receta_pasta_tomate", TXT_PASTA)
    _percibir(cerebro, "receta_pizza_tomate", TXT_PIZZA)
    _arista(cerebro, "receta_salsa_tomate", "receta_pasta_tomate", 0.5, "manual")
    _arista(cerebro, "receta_salsa_tomate", "receta_pizza_tomate", 0.20, "co_ocurrencia", ambos=False)
    cerebro.ciclo_sueno_consolidacion()
    _manual_intacto(cerebro, "receta_salsa_tomate", "receta_pasta_tomate")
    # Control: el automático sí sube
    assert _fila(cerebro, "receta_salsa_tomate", "receta_pizza_tomate")[0] > 0.20


def test_co_ocurrencia_en_comunicaciones_no_toca_manual(cerebro):
    _tres_recetas_consolidadas(cerebro)
    _arista(cerebro, "receta_salsa_tomate", "receta_pasta_tomate", 0.5, "manual")
    _arista(cerebro, "receta_salsa_tomate", "receta_pizza_tomate", 0.20, "co_ocurrencia")
    cerebro.cursor.execute(
        "INSERT INTO comunicaciones (origen, destino, contenido, timestamp) VALUES (?, ?, ?, ?)",
        ("agente", "todos",
         "Hoy cocinamos salsa de tomate maduro, pasta con ajo y albahaca, y pizza al horno con aceite.",
         time.time()),
    )
    cerebro.conn.commit()
    # Hace falta algo en corto plazo para que corra el sueño.
    _percibir(cerebro, "nota_sin_relacion", "Revisar el calendario de vacunas del perro.")
    cerebro.ciclo_sueno_consolidacion()
    _manual_intacto(cerebro, "receta_salsa_tomate", "receta_pasta_tomate")
    a = _fila(cerebro, "receta_salsa_tomate", "receta_pizza_tomate")[0]
    b = _fila(cerebro, "receta_pizza_tomate", "receta_salsa_tomate")[0]
    # Control: el automático sí sube en al menos un sentido
    assert max(a, b) > 0.20


def test_refuerzo_de_rafaga_no_toca_manual(cerebro):
    # La ráfaga solo crea o refuerza si la palabra de la consulta es el NOMBRE de un recuerdo
    # y el otro recuerdo puntúa >= 0.5 (en la práctica, coincidencia exacta del nombre
    # normalizado: «el_tomate» se normaliza a {tomate}).
    _percibir(cerebro, "tomate", "El tomate es una fruta roja.")
    _percibir(cerebro, "el_tomate", "Sobre el tomate en la cocina.")
    _percibir(cerebro, "un_tomate", "Un tomate pesa unos cien gramos.")
    cerebro.ciclo_sueno_consolidacion()
    cerebro.cursor.execute("DELETE FROM sinapsis")
    cerebro.conn.commit()
    _arista(cerebro, "tomate", "el_tomate", 0.5, "manual")
    _arista(cerebro, "tomate", "un_tomate", 0.30, "co_ocurrencia")
    cerebro.buscar_por_rafaga("tomate", ["tomate"])
    _manual_intacto(cerebro, "tomate", "el_tomate")
    # Control: el automático sí se refuerza (+0.1)
    assert _fila(cerebro, "tomate", "un_tomate")[0] == pytest.approx(0.40)
