"""Pruebas del arnés MCP E3A; no modifican ni necesitan la base real."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.evaluar_qa_multilingue_e3a import cargar_gold
from scripts.evaluar_qa_multilingue_mcp_e3a import (
    cargar_sustantivos, estadisticas, parsear_mcp, puentes_sinteticos,
)

ROOT = Path(__file__).resolve().parents[1]


def test_sustantivos_cubren_todas_las_preguntas_sin_adivinar_el_gold():
    casos = cargar_gold()
    etiquetas = cargar_sustantivos(casos)
    assert len(etiquetas) == 132
    assert sum(bool(e["sustantivos_guardado"]) for e in etiquetas.values()) == 40
    for caso in casos:
        query = caso["query"].lower()
        assert all(t.lower() in query for t in etiquetas[caso["id"]]["sustantivos_busqueda"].split(","))


def test_parser_mcp_acepta_advertencias_y_rechaza_salida_invalida():
    respuesta = {"total": 1, "resultados": [{"concepto": "ejemplo"}]}
    raw = "advertencia\n\n" + json.dumps(respuesta)
    assert parsear_mcp(raw) == respuesta
    assert parsear_mcp(json.dumps(respuesta)) == respuesta
    with pytest.raises(ValueError):
        parsear_mcp("solo advertencias, sin JSON")


def test_negativos_bloqueados_no_cuentan_como_abstencion_acertada():
    filas = [
        {"esperado": None, "busqueda_ejecutada": False, "error": "FORMATO", "falso_positivo": None},
        {"esperado": None, "busqueda_ejecutada": True, "error": None, "falso_positivo": True},
        {"esperado": "uno", "busqueda_ejecutada": True, "error": None, "rango": 1},
        {"esperado": "dos", "busqueda_ejecutada": False, "error": "FORMATO", "rango": None},
    ]
    s = estadisticas(filas)
    assert s["negativos"] == 2 and s["negativos_ejecutados"] == 1
    assert s["rechazos_negativos"] == 1 and s["falsos_positivos"] == 1
    assert s["positivos"] == 2 and s["aciertos_r5"] == 1 and s["rechazos_positivos"] == 1


def test_los_puentes_sinteticos_cumplen_formato_sin_fingir_validacion_humana():
    from core.concept_hub import validar_bridges

    for caso in cargar_gold():
        if caso["concepto"] and caso["idioma"] in ("en", "es"):
            validos, rechazados = validar_bridges(puentes_sinteticos(caso), caso["concepto"])
            assert len(validos) == 5, (caso["id"], rechazados)


def test_qa_mcp_completa_es_aislada_y_compara_el_orden(tmp_path):
    salida = tmp_path / "mcp.json"
    protegida = tmp_path / "base-real-no-abrir.db"
    env = os.environ.copy()
    env.update({"PYTHONHASHSEED": "0", "BIORAG_NEURONA": "0", "BIORAG_PATH": str(protegida)})
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/evaluar_qa_multilingue_mcp_e3a.py"),
         "--verificar-orden", "--salida", str(salida)],
        text=True, capture_output=True, check=False, env=env, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not protegida.exists()
    data = json.loads(salida.read_text(encoding="utf-8"))
    assert data["base_directa"]["nodos"] == 120
    assert data["base_mcp"]["nodos"] == len(data["base_mcp"]["escrituras"]) == 40
    for name in ("recordar_sobre_base_directa", "recordar_sobre_base_mcp_en_es"):
        brazo = data[name]
        assert len(brazo["casos"]) == 132
        assert brazo["verificacion_orden"]["casos_comparados"] == 132
        assert brazo["verificacion_orden"]["diferentes"] == []
        for caso in brazo["casos"]:
            assert caso["sustantivos_clave"]
            if caso["error"]:
                assert not caso["busqueda_ejecutada"]
                assert caso["falso_positivo"] is None
            else:
                assert caso["busqueda_ejecutada"]


def test_qa_mcp_exige_semilla_y_neurona_apagada(tmp_path):
    env = os.environ.copy()
    env.pop("PYTHONHASHSEED", None)
    env["BIORAG_NEURONA"] = "0"
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts/evaluar_qa_multilingue_mcp_e3a.py"),
         "--salida", str(tmp_path / "no_se_crea.json")],
        env=env, text=True, capture_output=True, check=False, timeout=30,
    )
    assert p.returncode != 0
    assert "PYTHONHASHSEED=0 BIORAG_NEURONA=0" in p.stderr
    assert not (tmp_path / "no_se_crea.json").exists()
