import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import comprobar_igualdad_qa_b3 as igualdad


def referencia():
    return {
        "db_src": "/tmp/snapshot.db",
        "casos_file": "gold.jsonl",
        "casos_total": 921,
        "categorias": {"literal": {"total": 10, "recall_at_5": 100.0, "recall_at_1": 90.0, "mrr": 0.95}},
        "qa_honesta": {
            "categorias": {"literal": {"r5": {"total": 10, "recall_at_5": 100.0},
                                         "r1": {"total": 10, "recall_at_1": 90.0}}},
            "global_r5": {"queries": 10, "recall_at_5": 100.0},
            "global_r1": {"queries": 10, "recall_at_1": 90.0, "mrr": 0.95},
        },
        "global": {"queries": 10, "recall_at_5": 100.0, "recall_at_1": 90.0,
                   "mrr": 0.95, "negativos_fp": 0, "negativos_total": 40},
        "e2b": {"censo_tematico": {"candidatos": 50}},
    }


def test_cli_carga_incluso_desde_otra_carpeta(tmp_path):
    script = Path(igualdad.__file__).resolve()
    proceso = subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path,
                             capture_output=True, text=True, check=False)
    assert proceso.returncode == 0, proceso.stderr
    assert "--salida" in proceso.stdout


def test_iguales_aprueba():
    x = referencia()
    assert igualdad.comprobar_escenario(x, copy.deepcopy(x)) == []


@pytest.mark.parametrize("cambio", [
    "categoria_bruta", "categoria_honesta", "global_r1", "global_r5", "fp", "censo", "corpus", "origen",
    "dato_ausente", "mejora_categoria",
])
def test_diferencia_o_dato_faltante_no_cumple_igualdad(cambio):
    a = referencia()
    b = copy.deepcopy(a)
    if cambio == "categoria_bruta":
        b["categorias"]["literal"]["recall_at_1"] = 80.0
    elif cambio == "categoria_honesta":
        b["qa_honesta"]["categorias"]["literal"]["r5"]["recall_at_5"] = 90.0
    elif cambio == "global_r1":
        b["qa_honesta"]["global_r1"]["recall_at_1"] = 80.0
    elif cambio == "global_r5":
        b["global"]["recall_at_5"] = 90.0
    elif cambio == "fp":
        b["global"]["negativos_fp"] = 1
    elif cambio == "censo":
        b["e2b"]["censo_tematico"]["candidatos"] = 49
    elif cambio == "corpus":
        b["casos_total"] = 920
    elif cambio == "origen":
        b["db_src"] = "/tmp/otra.db"
    elif cambio == "dato_ausente":
        del b["qa_honesta"]["global_r1"]
    elif cambio == "mejora_categoria":
        b["categorias"]["literal"]["recall_at_1"] = 100.0
    assert igualdad.comprobar_escenario(a, b)


def test_no_se_publica_si_faltan_escenarios(tmp_path):
    nombre = igualdad.ESCENARIOS[0]
    for version, fecha in (("b2", "20261027"), ("b3", "20261028")):
        (tmp_path / f"e3{version}_{nombre}_{fecha}.json").write_text(json.dumps(referencia()))
    resultado = igualdad.evaluar(tmp_path)
    assert resultado["escenarios"][nombre]["iguales"]
    assert len(resultado["pendientes"]) == 3
    assert not resultado["comparacion_completa"]
    assert not resultado["iguales"]


def test_lectura_corrupta_impide_aprobacion(tmp_path):
    for nombre in igualdad.ESCENARIOS:
        for version, fecha in (("b2", "20261027"), ("b3", "20261028")):
            p = tmp_path / f"e3{version}_{nombre}_{fecha}.json"
            p.write_text("{" if (version == "b3" and nombre == igualdad.ESCENARIOS[1]) else json.dumps(referencia()))
    resultado = igualdad.evaluar(tmp_path)
    assert resultado["comparacion_completa"]
    assert not resultado["iguales"]
    assert "lectura inválida" in resultado["escenarios"][igualdad.ESCENARIOS[1]]["diferencias"][0]
