"""
Los enlaces que decide el agente (vincular_con en aprender y la herramienta
vincular → tipo 'manual'; históricos 'manual_v7') son intocables para los
procesos automáticos. Decisión de Dennys (2026-10-24): "esas nunca deberán ser
borradas".

Antes de este cambio, en la copia del snapshot de Dennys:
  - el desgaste de consolidación ya había bajado 9 enlaces manuales de 0.5 y
    4 por debajo de 0.2 (a 0.05 se borran);
  - la hormiguita (Gemini) había borrado 15 enlaces manuales, 10 sin volver.

Se protegen de: desgaste, poda < 0.05, LTD guiado y hormiguita (borrar,
cuarentena y re-pesar). Solo el agente puede quitarlos a propósito con
desvincular (la herramienta sigue en el MCP).
"""

import time

import pytest

VIEJO = time.time() - 30 * 86400  # sin uso hace 30 días → el desgaste aplica


@pytest.fixture()
def cerebro(tmp_path):
    from core.memory_store import SQLiteMemoryBioRAG
    c = SQLiteMemoryBioRAG(str(tmp_path / "intocables.db"))
    yield c
    try:
        c.cerrar_sistema()
    except Exception:
        pass


def _arista(c, a, b, peso, tipo, ultimo_uso=VIEJO):
    for o, d in ((a, b), (b, a)):
        c.cursor.execute(
            "INSERT OR REPLACE INTO sinapsis (origen, destino, peso, tipo, creado_en, ultimo_uso) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (o, d, peso, tipo, VIEJO, ultimo_uso),
        )
    c.conn.commit()


def _peso(c, a, b):
    c.cursor.execute("SELECT peso FROM sinapsis WHERE origen = ? AND destino = ?", (a, b))
    fila = c.cursor.fetchone()
    return None if fila is None else fila[0]


def test_constante_unica():
    from core.memory.constants import TIPOS_SINAPSIS_AGENTE, SQL_NO_ES_DEL_AGENTE
    assert TIPOS_SINAPSIS_AGENTE == ("manual", "manual_v7")
    for t in TIPOS_SINAPSIS_AGENTE:
        assert f"'{t}'" in SQL_NO_ES_DEL_AGENTE


def test_vincular_crea_enlace_del_agente(cerebro):
    from core.memory.constants import TIPOS_SINAPSIS_AGENTE
    cerebro.establecer_asociacion("nodo_a", "nodo_b")
    cerebro.cursor.execute("SELECT tipo FROM sinapsis WHERE origen='nodo_a' AND destino='nodo_b'")
    assert cerebro.cursor.fetchone()[0] in TIPOS_SINAPSIS_AGENTE


def test_consolidacion_no_desgasta_ni_poda_enlaces_del_agente(cerebro):
    _arista(cerebro, "m1", "m2", 0.06, "manual")
    _arista(cerebro, "v1", "v2", 0.04, "manual_v7")
    _arista(cerebro, "a1", "a2", 0.06, "co_ocurrencia")
    _arista(cerebro, "b1", "b2", 0.04, "pmi_hebbiano")
    cerebro.ciclo_sueno_consolidacion()
    # Del agente: intactos (ni desgaste ni poda, aunque estén bajo 0.05)
    assert _peso(cerebro, "m1", "m2") == pytest.approx(0.06)
    assert _peso(cerebro, "v1", "v2") == pytest.approx(0.04)
    # Automáticos: el desgaste y la poda siguen igual que antes
    assert _peso(cerebro, "a1", "a2") == pytest.approx(0.057)
    assert _peso(cerebro, "b1", "b2") is None


def test_ltd_guiado_no_poda_enlaces_del_agente(cerebro):
    from core.dmn_engine import podar_ltd_guiado
    _arista(cerebro, "m1", "m2", 0.01, "manual")
    _arista(cerebro, "a1", "a2", 0.01, "co_nombre")
    podar_ltd_guiado(cerebro)
    cerebro.conn.commit()
    assert _peso(cerebro, "m1", "m2") == pytest.approx(0.01)
    assert _peso(cerebro, "m2", "m1") == pytest.approx(0.01)


def test_hormiguita_prefiltro_no_manda_enlaces_del_agente_a_gemini():
    from core.dmn_reflexion import _pre_filtrar_conexiones
    directas = [
        {"destino": "x", "tipo": "manual", "peso": 0.10, "contenido_destino": "nada que ver"},
        {"destino": "y", "tipo": "manual_v7", "peso": 0.30, "contenido_destino": "otra cosa"},
    ]
    cand, _, cortadas, _, mantenidas, _ = _pre_filtrar_conexiones("semilla distinta", directas, [])
    assert cand == [] and cortadas == []
    assert [s["destino"] for s in mantenidas] == ["x", "y"]


def test_hormiguita_cuarentena_se_niega(cerebro):
    from core.dmn_reflexion import _mover_a_cuarentena
    _arista(cerebro, "m1", "m2", 0.5, "manual")
    _arista(cerebro, "a1", "a2", 0.5, "co_ocurrencia")
    assert _mover_a_cuarentena("m1", "m2", "sinapsis", cerebro, "espuria", 0.9) is False
    assert _peso(cerebro, "m1", "m2") == pytest.approx(0.5)
    assert _mover_a_cuarentena("a1", "a2", "sinapsis", cerebro, "espuria", 0.9) is True
    assert _peso(cerebro, "a1", "a2") is None


def test_hormiguita_veredicto_nodo_no_borra_ni_repesa(cerebro):
    from core.dmn_reflexion import _aplicar_veredicto_nodo
    _arista(cerebro, "m1", "m2", 0.5, "manual")
    borrar = {"capa": "sinapsis_directa", "ref": "m2", "accion": "eliminar", "confianza": 0.99}
    repesar = {"capa": "sinapsis_directa", "ref": "m2", "accion": "reponderar",
               "confianza": 0.99, "peso_sugerido": 0.1}
    assert _aplicar_veredicto_nodo("m1", borrar, cerebro) is False
    assert _aplicar_veredicto_nodo("m1", repesar, cerebro) is False
    assert _peso(cerebro, "m1", "m2") == pytest.approx(0.5)


def test_hormiguita_veredicto_viejo_no_borra_ni_repesa(cerebro):
    from core.dmn_reflexion import _aplicar_veredicto
    _arista(cerebro, "m1", "m2", 0.5, "manual")
    assert _aplicar_veredicto(cerebro, {"id": "sinapsis_directa:m1->m2", "accion": "eliminar",
                                        "confianza": 0.99}) is False
    assert _aplicar_veredicto(cerebro, {"id": "sinapsis_directa:m1->m2", "accion": "reponderar",
                                        "confianza": 0.99, "peso_sugerido": 0.1}) is False
    assert _peso(cerebro, "m1", "m2") == pytest.approx(0.5)


def test_el_agente_si_puede_desvincular_a_proposito(cerebro):
    from core.sinapsis import desvincular
    _arista(cerebro, "m1", "m2", 0.5, "manual")
    desvincular(cerebro, "m1", "m2")
    cerebro.conn.commit()
    assert _peso(cerebro, "m1", "m2") is None
    assert _peso(cerebro, "m2", "m1") is None
