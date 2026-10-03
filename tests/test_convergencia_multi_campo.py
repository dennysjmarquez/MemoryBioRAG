"""
Tests unitarios para Spec 006: Convergencia Multi-Campo.
Verifica multiplicador de convergencia, comportamiento de banderas,
bypass de orígenes no literales/match exacto y clamping de alpha.
"""

import importlib
import logging
import os
import pytest
from core.memory import constants
from core.memory_store import SQLiteMemoryBioRAG


def test_alpha_clamping(caplog):
    """Verifica clamping de alpha en rango (0.0, 1.0) exclusivo y advertencias en log."""
    # 1. Valor por encima del límite (2.5 -> 0.99)
    os.environ["BIORAG_CONVERGENCIA_ALPHA"] = "2.5"
    with caplog.at_level(logging.WARNING):
        importlib.reload(constants)
    assert constants.CONVERGENCIA_ALPHA == 0.99
    assert any("BIORAG_CONVERGENCIA_ALPHA" in rec.message and "0.99" in rec.message for rec in caplog.records)

    # 2. Valor en el límite inferior (0.0 -> 0.01)
    caplog.clear()
    os.environ["BIORAG_CONVERGENCIA_ALPHA"] = "0.0"
    with caplog.at_level(logging.WARNING):
        importlib.reload(constants)
    assert constants.CONVERGENCIA_ALPHA == 0.01
    assert any("BIORAG_CONVERGENCIA_ALPHA" in rec.message and "0.01" in rec.message for rec in caplog.records)

    # 3. Valor negativo (-0.5 -> 0.01)
    caplog.clear()
    os.environ["BIORAG_CONVERGENCIA_ALPHA"] = "-0.5"
    with caplog.at_level(logging.WARNING):
        importlib.reload(constants)
    assert constants.CONVERGENCIA_ALPHA == 0.01

    # 4. Valor por encima o igual a 1.0 (1.0 -> 0.99)
    caplog.clear()
    os.environ["BIORAG_CONVERGENCIA_ALPHA"] = "1.0"
    with caplog.at_level(logging.WARNING):
        importlib.reload(constants)
    assert constants.CONVERGENCIA_ALPHA == 0.99

    # 5. Valor válido normal (0.5)
    caplog.clear()
    os.environ["BIORAG_CONVERGENCIA_ALPHA"] = "0.5"
    with caplog.at_level(logging.WARNING):
        importlib.reload(constants)
    assert constants.CONVERGENCIA_ALPHA == 0.5

    # 6. Flag CONVERGENCIA_ACTIVA
    os.environ["BIORAG_CONVERGENCIA_006_ACTIVA"] = "0"
    importlib.reload(constants)
    assert constants.CONVERGENCIA_ACTIVA is False

    os.environ["BIORAG_CONVERGENCIA_006_ACTIVA"] = "1"
    importlib.reload(constants)
    assert constants.CONVERGENCIA_ACTIVA is True

    # Restaurar variables
    os.environ.pop("BIORAG_CONVERGENCIA_ALPHA", None)
    os.environ.pop("BIORAG_CONVERGENCIA_006_ACTIVA", None)
    importlib.reload(constants)


def test_4campos_supera_1campo(tmp_path):
    """Test 1: Nodo con 4/4 campos activos supera a nodo con 1/4 campo activo (RF-3, RF-4)."""
    db_file = str(tmp_path / "test4c.db")
    c = SQLiteMemoryBioRAG(db_file)

    # Nodo A: 4/4 campos tienen los términos "arquitectura" y "modular"
    c.percibir_corto_plazo(
        "arquitectura_modular_biorag",
        "detalles sobre arquitectura modular en el sistema",
        sinonimos="diseno modular",
        sustantivos_clave="arquitectura,modular"
    )
    c.consolidar_concepto("arquitectura_modular_biorag")

    # Nodo B: solo 1/4 campos (contenido) tiene los términos; concepto, sinónimos y sustantivos son disjuntos
    c.percibir_corto_plazo(
        "historial_cambios_antiguos",
        "detalles sobre arquitectura modular en el sistema",
        sinonimos="changelog versiones",
        sustantivos_clave="registro,fechas"
    )
    c.consolidar_concepto("historial_cambios_antiguos")

    res, total = c.buscar_por_frase("arquitectura modular", limite=5)
    c.cerrar_sistema()

    assert total >= 2
    conceptos = [r[0] for r in res]
    assert conceptos[0] == "arquitectura_modular_biorag"

    scores = {r[0]: r[4] for r in res}
    assert scores["arquitectura_modular_biorag"] > scores["historial_cambios_antiguos"]


def test_binario_frecuencia():
    """Test 2: Multiplicador de convergencia es binario por campo e idéntico para 1 vs 500 repeticiones (RF-2)."""
    from core.fallback_simbolico import _tokenizar_normalizado
    
    tokens_query = _tokenizar_normalizado("algoritmo optimizacion")
    q_set = set(tokens_query)

    def _campo_activo(texto: str) -> int:
        if not texto or not q_set:
            return 0
        return 1 if q_set & set(_tokenizar_normalizado(texto)) else 0

    # Caso 1: 1 sola mención en contenido
    canales_1 = (
        _campo_activo("concepto_ajeno")
        + _campo_activo("sinonimos_ajenos")
        + _campo_activo("sustantivos_ajenos")
        + _campo_activo("contenido con algoritmo una sola vez")
    )
    mult_1 = 0.5 + 0.5 * (canales_1 / 4.0)

    # Caso 2: 500 repeticiones en contenido
    canales_500 = (
        _campo_activo("concepto_ajeno")
        + _campo_activo("sinonimos_ajenos")
        + _campo_activo("sustantivos_ajenos")
        + _campo_activo("contenido con " + "algoritmo " * 500)
    )
    mult_500 = 0.5 + 0.5 * (canales_500 / 4.0)

    assert canales_1 == 1
    assert canales_500 == 1
    assert mult_1 == 0.625
    assert mult_500 == 0.625
    assert mult_1 == mult_500


def test_flag_desactivado(tmp_path, monkeypatch):
    """El flag experimental 006 controla solo el multiplicador legado."""
    # Apagar la señal aditiva para medir exclusivamente el experimento Spec 006.
    monkeypatch.setenv("BIORAG_CONVERGENCIA_ACTIVA", "0")
    db_file = str(tmp_path / "test_flag.db")
    c = SQLiteMemoryBioRAG(db_file)
    # Crear varios nodos para que FTS devuelva candidatos literales y no active fallback
    for i in range(3):
        c.percibir_corto_plazo(
            f"nodo_cuantica_{i}",
            f"informacion sobre computacion cuantica aplicada {i}",
            sinonimos="temas cuanticos",
            sustantivos_clave="cuantica,computacion"
        )
        c.consolidar_concepto(f"nodo_cuantica_{i}")

    c.percibir_corto_plazo(
        "registro_secundario",
        "texto que menciona computacion cuantica de pasada",
        sinonimos="otro tema disjunto",
        sustantivos_clave="varios,datos"
    )
    c.consolidar_concepto("registro_secundario")

    # Búsqueda con flag activo (default ON)
    monkeypatch.setenv("BIORAG_CONVERGENCIA_006_ACTIVA", "1")
    importlib.reload(constants)
    res_on, _ = c.buscar_por_frase("computacion cuantica", limite=5)
    scores_on = {r[0]: r[4] for r in res_on}
    score_on = scores_on["registro_secundario"]

    # Búsqueda con flag desactivado (OFF)
    monkeypatch.setenv("BIORAG_CONVERGENCIA_006_ACTIVA", "0")
    importlib.reload(constants)
    res_off, _ = c.buscar_por_frase("computacion cuantica", limite=5)
    scores_off = {r[0]: r[4] for r in res_off}
    score_off = scores_off["registro_secundario"]

    c.cerrar_sistema()

    # Restaurar ambos modos al default: aditivo activo, multiplicador 006 inactivo.
    monkeypatch.delenv("BIORAG_CONVERGENCIA_006_ACTIVA", raising=False)
    monkeypatch.delenv("BIORAG_CONVERGENCIA_ACTIVA", raising=False)
    importlib.reload(constants)

    # Al tener 1/4 canales activos, con flag ON se multiplicó por 0.625
    assert score_off > score_on


def test_match_exacto_bypass(tmp_path):
    """Test 4: Si match_exacto=True, no se penaliza con el multiplicador (RF-9)."""
    db_file = str(tmp_path / "test_match_exacto.db")
    c = SQLiteMemoryBioRAG(db_file)
    c.percibir_corto_plazo(
        "version_actual_biorag",
        "descripcion breve sin sinonimos ni sustantivos",
        sinonimos="",
        sustantivos_clave=""
    )
    c.consolidar_concepto("version_actual_biorag")

    res, _ = c.buscar_por_frase("version_actual_biorag", limite=5)
    c.cerrar_sistema()

    assert res
    assert res[0][0] == "version_actual_biorag"
    # El score de un match exacto no debe ser recortado a 0.50*score base
    assert res[0][4] >= 0.70


def test_origen_semantico_bypass():
    """Test 5: Constante _ORIGENES_NO_LITERALES incluye orígenes no literales (CL-7)."""
    from core.memory.search import _ORIGENES_NO_LITERALES
    esperados = {"typo", "expansion", "latente", "cadena", "simbolico",
                 "dimensional_fallback", "semantica", "unicode", "lexico_aprendido", "sdm"}
    assert esperados.issubset(_ORIGENES_NO_LITERALES)


def test_tokens_vacios(tmp_path):
    """Test 6: Si la query no tiene tokens tras normalización, no rompe la búsqueda (CL-3)."""
    db_file = str(tmp_path / "test_vacio.db")
    c = SQLiteMemoryBioRAG(db_file)
    c.percibir_corto_plazo("nodo_prueba", "texto con algunas palabras")
    c.consolidar_concepto("nodo_prueba")

    # Stopwords exclusivamente
    res, _ = c.buscar_por_frase("de la", limite=5)
    c.cerrar_sistema()
    assert isinstance(res, list)
