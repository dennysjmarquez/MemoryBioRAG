"""
Cambio 2 (auditoría 25-11): `vincular_por_sinonimos` (B5) compara por coincidencia EXACTA
y no reetiqueta enlaces que ya existían.

Antes de este cambio:
  - buscaba cada sinónimo con LIKE '%término%' en el nombre y en los sinónimos de los demás,
    así que «sal» enlazaba con «salsa» y «番茄» con «番茄酱» (subcadena);
  - si el par ya existía por otra vía (co_nombre, co_ocurrencia…), lo subía a 0.9 y lo
    convertía en `sinonimo_explicito`, un tipo protegido para siempre.
Ver docs/ALGORITMO_NACIMIENTO_SINAPSIS.md §7 (P1, P2).

Ahora (cambio 2a) un sinónimo declarado enlaza con un recuerdo solo si es exactamente su
nombre o exactamente uno de sus sinónimos (lista separada por comas). Ambos lados se normalizan
igual, sin reglas de ningún idioma: identidad Unicode del proyecto (NFC + ancho), casefold,
`_`/`-` como espacio y espacios colapsados.

Fuera de este cambio (2b, pendiente de decisión): si el par ya existía y SÍ comparte un sinónimo
exacto, se mantiene la regla de siempre (MAX y tipo sinonimo_explicito), que fija
test_neurona_asociativa_motor.py::test_guardar_usa_pesos_a_mano_aunque_la_neurona_este_encendida.
"""

import time

import pytest

VIEJO = time.time() - 30 * 86400


@pytest.fixture()
def cerebro(tmp_path):
    from core.memory_store import SQLiteMemoryBioRAG
    c = SQLiteMemoryBioRAG(str(tmp_path / "sinonimos_exactos.db"))
    yield c
    try:
        c.cerrar_sistema()
    except Exception:
        pass


def _consolidar(c, recuerdos):
    for concepto, contenido, sinonimos in recuerdos:
        c.percibir_corto_plazo(concepto, contenido, sinonimos, "General", [])
    c.ciclo_sueno_consolidacion()
    c.cursor.execute("DELETE FROM sinapsis")
    c.conn.commit()


def _fila(c, o, d):
    c.cursor.execute("SELECT peso, tipo, ultimo_uso FROM sinapsis WHERE origen = ? AND destino = ?", (o, d))
    return c.cursor.fetchone()


def test_subcadena_no_enlaza(cerebro):
    from core.sinapsis import vincular_por_sinonimos
    _consolidar(cerebro, [
        ("salsa_casera", "Una salsa casera para la pasta.", "salsa, aderezo"),
        ("sal_marina", "Sal marina gruesa para cocinar.", "sal, sal gruesa"),
    ])
    vincular_por_sinonimos(cerebro, "nota_cocina", "sal")
    assert _fila(cerebro, "nota_cocina", "salsa_casera") is None      # «sal» ⊂ «salsa»: ya no enlaza
    fila = _fila(cerebro, "nota_cocina", "sal_marina")                 # «sal» es un sinónimo exacto
    assert fila is not None and fila[1] == "sinonimo_explicito" and fila[0] == pytest.approx(0.9)


def test_subcadena_no_enlaza_en_cjk(cerebro):
    from core.sinapsis import vincular_por_sinonimos
    _consolidar(cerebro, [
        ("番茄酱", "番茄酱是一种调味品。", "番茄酱, 茄汁"),
        ("番茄", "番茄是一种水果。", "番茄, 西红柿"),
    ])
    vincular_por_sinonimos(cerebro, "笔记", "番茄")
    assert _fila(cerebro, "笔记", "番茄酱") is None
    assert _fila(cerebro, "笔记", "番茄") is not None


def test_coincide_con_el_nombre_exacto_normalizado(cerebro):
    from core.sinapsis import vincular_por_sinonimos
    _consolidar(cerebro, [
        ("luz_roja", "La luz roja del semáforo obliga a detenerse.", ""),
        ("luz_roja_trasera", "Luz roja trasera de la bicicleta.", ""),
    ])
    vincular_por_sinonimos(cerebro, "nota_transito", "Luz Roja")
    assert _fila(cerebro, "nota_transito", "luz_roja") is not None          # mismo nombre normalizado
    assert _fila(cerebro, "nota_transito", "luz_roja_trasera") is None      # solo lo contiene


def test_puente_por_rasgo_compartido_sigue_naciendo(cerebro):
    """Los puentes son válidos (decisión 25-11): si dos recuerdos declaran el mismo rasgo
    como sinónimo exacto, el enlace sigue naciendo, aunque los temas sean distintos."""
    from core.sinapsis import vincular_por_sinonimos
    _consolidar(cerebro, [
        ("receta_salsa_tomate", "Salsa de tomate rojo con ajo.", "salsa, tomate, rojo"),
        ("semaforo_transito", "El semáforo en rojo obliga a detenerse.", "semáforo, rojo"),
    ])
    vincular_por_sinonimos(cerebro, "sangre_donacion", "sangre, rojo")
    assert _fila(cerebro, "sangre_donacion", "receta_salsa_tomate") is not None
    assert _fila(cerebro, "sangre_donacion", "semaforo_transito") is not None


def test_no_reetiqueta_por_subcadena_del_nombre(cerebro):
    """El caso de la traza (P1): «tomate» no es el nombre ni un sinónimo de
    `receta_salsa_tomate` (solo forma parte de su nombre), así que su enlace co_nombre previo
    ya no se convierte en sinonimo_explicito 0.9."""
    from core.sinapsis import vincular_por_sinonimos
    _consolidar(cerebro, [("receta_salsa_tomate", "Salsa de tomate con ajo.", "salsa, receta")])
    cerebro.cursor.execute(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en, ultimo_uso) VALUES (?, ?, ?, ?, ?, ?)",
        ("receta_pasta_tomate", "receta_salsa_tomate", 0.75, "co_nombre", VIEJO, None),
    )
    cerebro.conn.commit()
    vincular_por_sinonimos(cerebro, "receta_pasta_tomate", "tomate")
    assert _fila(cerebro, "receta_pasta_tomate", "receta_salsa_tomate") == (0.75, "co_nombre", None)


def test_no_toca_manual(cerebro):
    from core.sinapsis import vincular_por_sinonimos
    _consolidar(cerebro, [("receta_salsa_tomate", "Salsa de tomate con ajo.", "salsa, tomate")])
    for o, d in (("receta_pasta_tomate", "receta_salsa_tomate"), ("receta_salsa_tomate", "receta_pasta_tomate")):
        cerebro.cursor.execute(
            "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en, ultimo_uso) VALUES (?, ?, ?, ?, ?, ?)",
            (o, d, 0.5, "manual", VIEJO, VIEJO),
        )
    cerebro.conn.commit()
    vincular_por_sinonimos(cerebro, "receta_pasta_tomate", "tomate")
    for o, d in (("receta_pasta_tomate", "receta_salsa_tomate"), ("receta_salsa_tomate", "receta_pasta_tomate")):
        peso, tipo, uso = _fila(cerebro, o, d)
        assert (peso, tipo) == (pytest.approx(0.5), "manual") and uso == pytest.approx(VIEJO)


def test_sinonimo_real_nuevo_sigue_naciendo_igual(cerebro):
    """Lo que debe seguir igual: un sinónimo exacto sin enlace previo nace con
    sinonimo_explicito y 0.9, sin ultimo_uso, y el espejo `asociaciones` se sincroniza."""
    from core.sinapsis import vincular_por_sinonimos
    _consolidar(cerebro, [("automovil", "Vehículo de cuatro ruedas.", "coche, carro")])
    res = vincular_por_sinonimos(cerebro, "nota_taller", "coche")
    assert res == [("automovil", 0.9)]
    assert _fila(cerebro, "nota_taller", "automovil") == (pytest.approx(0.9), "sinonimo_explicito", None)
    cerebro.cursor.execute("SELECT asociaciones FROM largo_plazo WHERE concepto = 'automovil'")
    assert "nota_taller" in (cerebro.cursor.fetchone()[0] or "")
