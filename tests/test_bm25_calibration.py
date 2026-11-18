"""Contrato matemático del normalizador experimental de BM25.

relative_top1 elimina la dependencia del extremo inferior del pool y es
invariante ante un reescalado multiplicativo uniforme. No afirma que los scores
crudos de FTS5 sean invariantes frente a cambios de N, df o longitud media.
"""
import math

import pytest

from core.memory.bm25_calibration import normalizar_mapa_bm25, modo_normalizacion_bm25


ENV_MODO = "BIORAG_BM25_NORM_MODE"


def test_modo_por_defecto_conserva_minmax_legacy(monkeypatch):
    monkeypatch.delenv(ENV_MODO, raising=False)
    scores, bounds = normalizar_mapa_bm25({"fuerte": -3.5, "medio": -1.5, "debil": -0.5})

    assert scores == {"fuerte": 1.0, "medio": 1.0 / 3.0, "debil": 0.0}
    assert bounds == (0.5, 3.5, 1.0)
    assert modo_normalizacion_bm25() == "minmax"


def test_minmax_conserva_caso_unico_y_cero():
    fuerte, bounds = normalizar_mapa_bm25({"fuerte": -4.0}, mode="minmax")
    cero, _ = normalizar_mapa_bm25({"cero": 0.0}, mode="minmax")
    vacio, bounds_vacio = normalizar_mapa_bm25({}, mode="minmax")

    assert fuerte == {"fuerte": 1.0}
    assert bounds == (4.0, 4.0, 1.0)
    assert cero == {"cero": 0.0}
    assert vacio == {}
    assert bounds_vacio is None


def test_minmax_reproduce_formula_legacy_en_varios_pools():
    cases = [
        {"a": -0.2, "b": -0.8, "c": -1.5},
        {"a": -1.0, "b": -1.0},
        {"a": -2.0, "b": -4.0},
        {"a": -4.0},
        {"a": -0.2},
    ]
    for raw in cases:
        values = [abs(value) for value in raw.values()]
        lo, hi = min(values), max(values)
        span = hi - lo if hi > lo else 1.0
        scale = min(1.0, hi) if hi > 0 else 1.0
        if hi > lo:
            expected = {key: ((abs(value) - lo) / span) * scale for key, value in raw.items()}
        elif len(raw) == 1 and hi >= 3.0:
            expected = {key: scale for key in raw}
        else:
            expected = {key: 0.0 for key in raw}

        actual, _ = normalizar_mapa_bm25(raw, mode="minmax")
        assert actual == expected


def test_relative_top1_no_depende_del_candidato_mas_debil():
    base = {"fuerte": -4.0, "medio": -1.0}
    crecida = {**base, "ruido_debil": -0.2}

    normal_base, _ = normalizar_mapa_bm25(base, mode="relative_top1")
    normal_crecida, _ = normalizar_mapa_bm25(crecida, mode="relative_top1")

    assert normal_base == {"fuerte": 1.0, "medio": 0.25}
    assert normal_crecida["fuerte"] == normal_base["fuerte"]
    assert normal_crecida["medio"] == normal_base["medio"]
    assert normal_crecida["ruido_debil"] == 0.05


def test_relative_top1_es_invariante_a_escala_multiplicativa_uniforme():
    scores_a, _ = normalizar_mapa_bm25(
        {"a": -4.0, "b": -2.0, "c": -0.5}, mode="relative_top1"
    )
    scores_b, _ = normalizar_mapa_bm25(
        {"a": -40.0, "b": -20.0, "c": -5.0}, mode="relative_top1"
    )

    assert scores_a == scores_b == {"a": 1.0, "b": 0.5, "c": 0.125}


def test_relative_top1_es_monotono_y_acotado():
    scores, _ = normalizar_mapa_bm25(
        {"mejor": -8.0, "medio": -3.0, "debil": -0.1}, mode="relative_top1"
    )

    assert all(0.0 <= value <= 1.0 for value in scores.values())
    assert scores["mejor"] > scores["medio"] > scores["debil"]


def test_relative_top1_comparte_el_maximo_de_la_busqueda_previa():
    scores, bounds = normalizar_mapa_bm25(
        {"rafaga": -8.0, "otro": -4.0},
        mode="relative_top1",
        base_bounds=(1.0, 6.0, 1.0),
    )

    assert scores == {"rafaga": 1.0, "otro": 0.5}
    assert bounds == (1.0, 8.0, 1.0)


def test_minmax_comparte_limites_legacy_con_busqueda_previa():
    scores, bounds = normalizar_mapa_bm25(
        {"rafaga": -4.0, "otro": -2.0},
        mode="minmax",
        base_bounds=(1.0, 6.0, 1.0),
    )

    assert scores == {"rafaga": 0.6, "otro": 0.2}
    assert bounds == (1.0, 6.0, 1.0)


def test_relative_top1_reescala_si_aparece_un_candidato_mejor():
    base, _ = normalizar_mapa_bm25({"a": -4.0, "b": -2.0}, mode="relative_top1")
    con_candidato_relevante, _ = normalizar_mapa_bm25(
        {"a": -4.0, "b": -2.0, "nuevo": -8.0}, mode="relative_top1"
    )

    assert base == {"a": 1.0, "b": 0.5}
    assert con_candidato_relevante == {"a": 0.5, "b": 0.25, "nuevo": 1.0}


def test_environment_variable_activa_el_modo_experimental(monkeypatch):
    monkeypatch.setenv(ENV_MODO, "relative_top1")
    scores, _ = normalizar_mapa_bm25({"a": -4.0, "b": -1.0})

    assert modo_normalizacion_bm25() == "relative_top1"
    assert scores == {"a": 1.0, "b": 0.25}


def test_modo_explicito_desconocido_falla_rapido():
    with pytest.raises(ValueError, match="no soportado"):
        normalizar_mapa_bm25({"a": -1.0}, mode="sigmoide_inventado")


def test_valores_no_finitos_no_envenenan_la_escala():
    scores, _ = normalizar_mapa_bm25(
        {"fuerte": -2.0, "nan": math.nan, "inf": -math.inf},
        mode="relative_top1",
    )

    assert scores == {"fuerte": 1.0, "nan": 0.0, "inf": 0.0}
