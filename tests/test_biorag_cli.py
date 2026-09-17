"""Tests de integración y unidad para la interfaz CLI de BioRAG (biorag.py).
Spec 002: Sustantivos Clave en CLI, Sanitización OWASP y Ergonomía de Terminal.
"""

import os
import sys
import pytest
from unittest.mock import patch
import biorag


class TestCLISanitizacionYFlags:
    """T1: Pruebas para _sanitizar_entrada_cli y _extraer_flag_valor."""

    def test_sanitizar_entrada_limpia_bytes_nulos_y_control(self):
        # Bytes nulos y caracteres de control ASCII
        entrada_sucia = "concepto\x00_prueba\x07\x1b con espacios   "
        limpio = biorag._sanitizar_entrada_cli(entrada_sucia, max_len=100)
        assert "\x00" not in limpio
        assert "\x07" not in limpio
        assert "\x1b" not in limpio
        assert limpio == "concepto_prueba con espacios"

    def test_sanitizar_entrada_excede_limite_lanza_value_error(self):
        # Longitud mayor a max_len
        entrada_larga = "a" * 205
        with pytest.raises(ValueError, match="excede el límite"):
            biorag._sanitizar_entrada_cli(entrada_larga, max_len=200, nombre_campo="concepto")

    def test_extraer_flag_valor_al_final(self):
        args = ["mi_clave", "mi contenido", "--sustantivos-clave", "ia,red"]
        flags = ["--sustantivos-clave", "--sustantivos"]
        valor, restantes = biorag._extraer_flag_valor(args, flags)
        assert valor == "ia,red"
        assert restantes == ["mi_clave", "mi contenido"]

    def test_extraer_flag_valor_al_inicio(self):
        args = ["--sustantivos-clave", "ia,red", "mi_clave", "mi contenido"]
        flags = ["--sustantivos-clave", "--sustantivos"]
        valor, restantes = biorag._extraer_flag_valor(args, flags)
        assert valor == "ia,red"
        assert restantes == ["mi_clave", "mi contenido"]

    def test_extraer_flag_valor_en_medio(self):
        args = ["mi_clave", "--sustantivos-clave", "ia,red", "mi contenido"]
        flags = ["--sustantivos-clave", "--sustantivos"]
        valor, restantes = biorag._extraer_flag_valor(args, flags)
        assert valor == "ia,red"
        assert restantes == ["mi_clave", "mi contenido"]

    def test_extraer_flag_sin_valor_lanza_error(self):
        args = ["mi_clave", "mi contenido", "--sustantivos-clave"]
        flags = ["--sustantivos-clave", "--sustantivos"]
        with pytest.raises(ValueError, match="requiere un valor"):
            biorag._extraer_flag_valor(args, flags)

    def test_extraer_flag_seguido_de_otro_flag_lanza_error(self):
        args = ["mi_clave", "--sustantivos-clave", "--cat", "proyecto"]
        flags = ["--sustantivos-clave", "--sustantivos"]
        with pytest.raises(ValueError, match="requiere un valor"):
            biorag._extraer_flag_valor(args, flags)
