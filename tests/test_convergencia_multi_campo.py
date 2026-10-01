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
    os.environ["BIORAG_CONVERGENCIA_ACTIVA"] = "0"
    importlib.reload(constants)
    assert constants.CONVERGENCIA_ACTIVA is False

    os.environ["BIORAG_CONVERGENCIA_ACTIVA"] = "1"
    importlib.reload(constants)
    assert constants.CONVERGENCIA_ACTIVA is True

    # Restaurar variables
    os.environ.pop("BIORAG_CONVERGENCIA_ALPHA", None)
    os.environ.pop("BIORAG_CONVERGENCIA_ACTIVA", None)
    importlib.reload(constants)
