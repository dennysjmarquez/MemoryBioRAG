"""Regresiones del comparador B2: no permitir un falso CUMPLE."""
from copy import deepcopy
import sys

from scripts import comparar_qa_multilingue_b2 as multilingue
from scripts import comparar_qa_oficial_b2 as oficial


def test_multilingue_b2_resultados_congelados():
    resultado = multilingue.comparar()
    assert resultado["cumple_multilingue_y_guardado"]
    assert not resultado["directa_diferentes"]
    assert not resultado["mcp_a_diferentes"]
    assert len(resultado["pendiente_hueco_1"]) == 14
    assert {idioma: d["guardados_b2"] for idioma, d in resultado["guardado"].items()} == {
        "zh": 0, "ja": 0, "ko": 16, "ru": 20,
    }


def alterar(monkeypatch, archivo, mutar):
    leer_original = multilingue.leer

    def leer(nombre):
        valor = deepcopy(leer_original(nombre))
        if nombre == archivo:
            mutar(valor)
        return valor

    monkeypatch.setattr(multilingue, "leer", leer)


def test_multilingue_detecta_cambio_en_la_directa(monkeypatch):
    alterar(monkeypatch, "e3b2_directa_20261027.json", lambda d: d["casos"][0].update({"esperado": "otro"}))
    resultado = multilingue.comparar()
    assert not resultado["cumple_multilingue_y_guardado"]
    assert resultado["directa_diferentes"]


def test_multilingue_detecta_cambio_en_hueco_1(monkeypatch):
    def mutar(d):
        casos = d["recordar_sobre_base_directa"]["casos"]
        next(c for c in casos if c.get("marca_auditoria") == "pendiente hueco 1")["marca_auditoria"] = None
    alterar(monkeypatch, "e3b2_mcp_brazo_a_20261027.json", mutar)
    resultado = multilingue.comparar()
    assert not resultado["cumple_multilingue_y_guardado"]
    assert len(resultado["pendiente_hueco_1"]) == 13


def test_multilingue_detecta_guardado_sin_persistencia_correcta(monkeypatch):
    def mutar(d):
        next(c for c in d["casos"] if c["guardado_en_db"])["sustantivos_en_db"] = "falso"
    alterar(monkeypatch, "e3b2_guardado_nativo_20261027.json", mutar)
    resultado = multilingue.comparar()
    assert not resultado["cumple_multilingue_y_guardado"]
    assert any("persistencia B2" in p for p in resultado["problemas"])


def test_comparador_oficial_incompleto_no_da_veredicto(tmp_path, monkeypatch):
    monkeypatch.setattr(oficial, "DOCS", tmp_path)
    salida = tmp_path / "comparacion.json"
    monkeypatch.setattr(sys, "argv", ["comparar", "--salida", str(salida)])
    assert oficial.main() == 2
    import json
    resultado = json.loads(salida.read_text())
    assert not resultado["comparacion_completa"]
    assert not resultado["metricas_cumplen"]
    assert len(resultado["pendientes"]) == 4
