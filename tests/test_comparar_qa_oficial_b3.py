import json
import sys

from scripts import comparar_qa_oficial_b3 as oficial


def test_fuente_absoluta_y_relativa_son_la_misma_solo_si_resuelven_al_mismo_archivo(tmp_path):
    assert oficial.misma_fuente(str(tmp_path / "snapshots/base.db"), "snapshots/base.db", tmp_path)
    assert not oficial.misma_fuente(str(tmp_path / "viva.db"), "snapshots/base.db", tmp_path)


def test_oficial_b3_incompleta_no_da_veredicto(tmp_path, monkeypatch):
    monkeypatch.setattr(oficial, "DOCS", tmp_path)
    salida = tmp_path / "comparacion.json"
    tabla = tmp_path / "tabla.md"
    monkeypatch.setattr(sys, "argv", ["comparar", "--salida", str(salida), "--tabla", str(tabla)])
    assert oficial.main() == 2
    resultado = json.loads(salida.read_text(encoding="utf-8"))
    assert not resultado["comparacion_completa"]
    assert not resultado["metricas_cumplen"]
    assert len(resultado["pendientes"]) == 4
    assert not tabla.exists()


def test_tabla_muestra_snapshot_y_viva_con_etiquetas_b2_b3():
    escenario = {
        "categorias_honestas": {"literal": {"r5": {"antes": 9, "despues": 9, "total": 10},
                                               "r1": {"antes": 8, "despues": 8, "total": 10}}},
        "r5_antes": {"queries": 10, "fallos": 1}, "r5_b3": {"queries": 10, "fallos": 1},
        "r1_antes": {"queries": 10, "no_top1": 2}, "r1_b3": {"queries": 10, "no_top1": 2},
        "fp_antes": [0, 40], "fp_b3": [0, 40],
        "fallos_honestos_nuevos": [], "fallos_honestos_recuperados": [],
    }
    tabla = oficial.tabla_categoria({nombre: escenario for nombre in
                                     ("snapshot_normal", "snapshot_ruido", "viva_normal", "viva_ruido")})
    assert "B2 → B3" in tabla
    assert "Snapshot R@5" in tabla and "Viva R@5" in tabla
    assert "9/10 → 9/10" in tabla
    assert "0/40 → 0/40" in tabla

    sin_categoria = {**escenario, "categorias_honestas": {}}
    tabla_incompleta = oficial.tabla_categoria({"snapshot_normal": escenario, "snapshot_ruido": escenario,
                                               "viva_normal": sin_categoria, "viva_ruido": sin_categoria})
    assert "| literal | 9/10 → 9/10 | 8/10 → 8/10 | — | — |" in tabla_incompleta
