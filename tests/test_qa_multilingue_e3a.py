"""Pruebas del arnés E3 A, no expectativas de que el motor ya sea multilingüe."""
import json
import os
from collections import Counter
from pathlib import Path
import subprocess
import sys
import unicodedata
from unittest.mock import patch

import pytest

from scripts.evaluar_qa_multilingue_e3a import (
    GOLD, IDIOMAS, RELOJ_FIJO, buscar_caso, cargar_gold, crear_base, metricas, sha256,
)


def test_gold_cubierto_y_sin_ambiguedades_de_id():
    casos = cargar_gold()
    assert len(casos) == 132
    for idioma in IDIOMAS:
        positivos = [c for c in casos if c["idioma"] == idioma and c["concepto"]]
        negativos = [c for c in casos if c["idioma"] == idioma and c["tipo"] == "negativo"]
        assert len(positivos) == 20
        assert len(negativos) == 2
        assert Counter(c["tipo"] for c in positivos)["fragmento"] == 5
    assert len({c["id"] for c in casos}) == 132
    assert len({c["concepto"] for c in casos if c["concepto"]}) == 120


def test_gold_incluye_contraste_japones_real():
    pares = {c["id"]: c for c in cargar_gold()}
    a, b = pares["ja-19"], pares["ja-20"]
    assert a["query"] == a["concepto"] == "ガラス"
    assert b["query"] == b["concepto"] == "カラス"
    assert a["concepto"] != b["concepto"]
    def sin_marcas(s):
        return "".join(ch for ch in unicodedata.normalize("NFKD", s)
                       if not unicodedata.combining(ch))
    assert sin_marcas(a["concepto"]) == sin_marcas(b["concepto"])


def test_rechaza_ids_y_golds_duplicados(tmp_path):
    caso = cargar_gold()[0]
    path = tmp_path / "duplicado.jsonl"
    path.write_text((json.dumps(caso, ensure_ascii=False) + "\n") * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="repetidos"):
        cargar_gold(path)


def test_resumen_incluye_misses_y_controles_negativos():
    casos = [
        {"idioma": "zh", "tipo": "literal", "esperado": "a", "rango": 1,
         "resultados": [{"concepto": "a"}], "falso_positivo": None},
        {"idioma": "zh", "tipo": "pregunta", "esperado": "b", "rango": None,
         "resultados": [], "falso_positivo": None},
        {"idioma": "zh", "tipo": "negativo", "esperado": None, "rango": None,
         "resultados": [{"concepto": "a"}], "falso_positivo": True},
    ]
    m = metricas(casos)["por_idioma"]["zh"]
    assert (m["positivos"], m["aciertos_r1"], m["aciertos_r5"]) == (2, 1, 1)
    assert (m["r1_pct"], m["r5_pct"], m["mrr_at_5"]) == (50.0, 50.0, 0.5)
    assert (m["negativos"], m["falsos_positivos"], m["sin_resultados_positivos"]) == (1, 1, 1)


def test_base_nueva_y_copias_por_consulta_no_alteran_el_original(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    casos = [c for c in cargar_gold() if c["id"] in ("ja-19", "ja-20", "es-01")]
    db = tmp_path / "base.db"
    with patch("time.time", return_value=RELOJ_FIJO):
        meta = crear_base(db, casos)
        assert meta["nodos"] == 3 and meta["integridad"] == "ok"
        antes = sha256(db)
        a = buscar_caso(db, casos[0], tmp_path)
        b = buscar_caso(db, casos[0], tmp_path)
        assert a == b
        assert len(a["resultados"]) <= 5
        assert sha256(db) == antes
        with pytest.raises(FileExistsError):
            crear_base(db, casos)


def test_qa_completa_compara_orden_sobre_la_misma_base(tmp_path):
    script = GOLD.parent / "evaluar_qa_multilingue_e3a.py"
    salida = tmp_path / "resultado.json"
    env = os.environ.copy()
    env.update({"PYTHONHASHSEED": "0", "BIORAG_NEURONA": "0"})
    p = subprocess.run([sys.executable, str(script), "--verificar-orden", "--salida", str(salida)],
                       env=env, text=True, capture_output=True, check=False, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    resultado = json.loads(salida.read_text(encoding="utf-8"))
    comprobacion = resultado["verificacion_orden_misma_base"]
    assert comprobacion["casos_comparados"] == 132
    assert comprobacion["diferentes"] == []
    assert resultado["base"]["nodos"] == 120
    assert resultado["metricas"]["global"]["positivos"] == 120
    assert resultado["metricas"]["global"]["negativos"] == 12


def test_ejecucion_exige_semilla_y_neurona_apagada(tmp_path):
    script = GOLD.parent / "evaluar_qa_multilingue_e3a.py"
    env = os.environ.copy()
    env.update({"PYTHONHASHSEED": "1", "BIORAG_NEURONA": "0"})
    p = subprocess.run([sys.executable, str(script), "--salida", str(tmp_path / "no.json")],
                       env=env, text=True, capture_output=True, check=False)
    assert p.returncode != 0
    assert "PYTHONHASHSEED=0 BIORAG_NEURONA=0" in p.stderr
    assert not (tmp_path / "no.json").exists()
