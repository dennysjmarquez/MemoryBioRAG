import copy
import json
from pathlib import Path

import pytest

from scripts.evaluar_qa_guardado_y_busqueda_b3 import (
    _termino_valido,
    comparar_guardados_referencia,
    consultas_de_caso,
)


CASOS = Path(__file__).resolve().parents[1] / "scripts" / "casos_qa_guardado_nativo_e3b2.jsonl"


def _casos():
    return [json.loads(line) for line in CASOS.read_text(encoding="utf-8").splitlines() if line]


def test_las_tres_consultas_de_los_80_casos_no_fingen_que_el_puente_omite_nombre():
    casos = _casos()
    assert len(casos) == 80
    for caso in casos:
        consultas = consultas_de_caso(caso)
        assert set(consultas) == {"nombre", "puente_completo", "fragmento_sin_nombre"}
        assert consultas["nombre"]["query"] == caso["concepto"]
        assert caso["concepto"] in consultas["puente_completo"]["query"]
        fragmento = consultas["fragmento_sin_nombre"]
        assert caso["concepto"].lower() not in fragmento["query"].lower()
        assert fragmento["query"] in fragmento["fragmento_completo"]
        for consulta in consultas.values():
            for termino in consulta["sustantivos_clave"].split(","):
                assert _termino_valido(termino)
                assert termino.lower() in consulta["query"].lower()


def test_fragmentos_genericos_se_reconocen_como_identicos_por_idioma():
    por_idioma = {}
    for caso in _casos():
        q = consultas_de_caso(caso)["fragmento_sin_nombre"]["query"]
        por_idioma.setdefault(caso["idioma"], set()).add(q)
    assert all(len(consultas) == 1 for consultas in por_idioma.values())


def test_no_acepta_silenciosamente_un_puente_sin_el_nombre():
    caso = copy.deepcopy(_casos()[0])
    caso["bridges"][0]["text"] = "puente con otra palabra"
    with pytest.raises(ValueError, match="exactamente una vez"):
        consultas_de_caso(caso)


def test_control_de_80_guardados_detecta_una_regresion_individual():
    campos = {
        "busqueda_previa_ejecutada": True, "busqueda_previa_confirmada": True,
        "primer_rechazo": None, "guardado_en_db": True, "confirmado_por_mcp": True,
        "consolidado": True, "puentes_guardados": 5,
    }
    referencia = {"casos": [{"id": str(i), **campos} for i in range(80)]}
    actual = copy.deepcopy(referencia)
    comparar_guardados_referencia(actual, referencia)
    actual["casos"][5]["guardado_en_db"] = False
    with pytest.raises(RuntimeError, match="5:guardado_en_db"):
        comparar_guardados_referencia(actual, referencia)
