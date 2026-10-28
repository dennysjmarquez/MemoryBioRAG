"""Pruebas de guardas de la comparación oficial B1."""
from copy import deepcopy
import json
from pathlib import Path

from scripts.comparar_qa_oficial_b1 import comparar, fallos_honestos

ROOT = Path(__file__).resolve().parents[1]


def _base():
    return json.loads((ROOT / "docs/e2e_base_snapshot_normal_20261027.json").read_text(encoding="utf-8"))


def test_cuando_la_misma_medicion_se_compara_no_inventa_regresion():
    anterior = _base()
    _, problemas = comparar("snapshot_normal", anterior, deepcopy(anterior), False)
    assert problemas == []


def test_detecta_caida_honesta_por_categoria_en_r1_y_r5():
    anterior = _base()
    candidato = deepcopy(anterior)
    categoria = candidato["qa_honesta"]["categorias"]["literal"]
    categoria["r1"]["recall_at_1"] -= 1
    categoria["r5"]["recall_at_5"] -= 1
    _, problemas = comparar("snapshot_normal", anterior, candidato, False)
    assert any("literal r1" in problema for problema in problemas)
    assert any("literal r5" in problema for problema in problemas)


def test_fallos_honestos_baseline_se_pueden_conciliar():
    anterior = _base()
    path = ROOT / "docs/e2e_base_snapshot_normal_fallos_20261027.jsonl"
    assert fallos_honestos(path, anterior) == set()


def test_detecta_fp_y_cambio_de_modo():
    anterior = _base()
    candidato = deepcopy(anterior)
    candidato["global"]["negativos_fp"] = 1
    candidato["e2b"]["ruido"] = "zzqx"
    _, problemas = comparar("snapshot_normal", anterior, candidato, False)
    assert any("FP" in problema for problema in problemas)
    assert any("ruido distinto" in problema for problema in problemas)
