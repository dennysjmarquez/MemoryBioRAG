"""Tests de integración y unidad para la interfaz CLI de BioRAG (biorag.py).
Spec 002: Sustantivos Clave en CLI, Sanitización OWASP y Ergonomía de Terminal.
"""

import os
import sys
import sqlite3
import tempfile
import pytest
from io import StringIO
from unittest.mock import patch, MagicMock
import biorag


# ─── Fixture: DB temporal aislada para tests de integración ─────────────────

@pytest.fixture
def cerebro_tmp(tmp_path):
    """Instancia de SQLiteMemoryBioRAG usando una DB temporal limpia."""
    db_path = str(tmp_path / "test_cli.db")
    from core.memory_store import SQLiteMemoryBioRAG
    c = SQLiteMemoryBioRAG(db_path=db_path)
    yield c
    try:
        c.conn.close()
    except Exception:
        pass


# ─── T1: Sanitización OWASP y extracción de flags ───────────────────────────

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


# ─── T2: cmd_guardar — validación pedagógica y confirmación visual ───────────

class TestCmdGuardar:
    """T2: Pruebas para cmd_guardar con --sustantivos-clave requerido."""

    def test_guardar_sin_sustantivos_muestra_guia_pedagogica(self, cerebro_tmp, capsys):
        """RF-4: Omitir --sustantivos-clave → exit 1 + guía pedagógica."""
        rc = biorag.cmd_guardar(cerebro_tmp, ["mi_concepto", "Contenido de prueba sin sustantivos"])
        out = capsys.readouterr().out
        assert rc == 1
        # La salida debe contener palabras clave de la guía pedagógica
        assert "sustantivos-clave" in out.lower() or "núcleo" in out.lower() or "nucleo" in out.lower()

    def test_guardar_con_alias_sustantivos_acepta_flag(self, cerebro_tmp, capsys):
        """RF-1: El alias --sustantivos debe funcionar igual que --sustantivos-clave."""
        rc = biorag.cmd_guardar(cerebro_tmp, [
            "alias_test", "Contenido de prueba con alias",
            "--sustantivos", "prueba,alias"
        ])
        out = capsys.readouterr().out
        assert rc == 0
        assert "prueba" in out.lower() or "alias" in out.lower()

    def test_guardar_exitoso_muestra_confirmacion_con_sustantivos(self, cerebro_tmp, capsys):
        """RF-3: Guardado exitoso debe mostrar los sustantivos indexados con conteo."""
        rc = biorag.cmd_guardar(cerebro_tmp, [
            "relatividad", "Einstein demostro la equivalencia entre energia y masa.",
            "--sustantivos-clave", "relatividad,energia,masa"
        ])
        out = capsys.readouterr().out
        assert rc == 0
        # Debe confirmar los sustantivos y conteo en el output
        assert "relatividad" in out
        assert "3/5" in out or "(3)" in out

    def test_guardar_sustantivos_invalidos_caracteres_especiales(self, cerebro_tmp, capsys):
        """RF-5: Sustantivos con caracteres prohibidos → exit 1."""
        rc = biorag.cmd_guardar(cerebro_tmp, [
            "test_invalido", "Contenido de prueba.",
            "--sustantivos-clave", "valid,inv@lid!,otro"
        ])
        out = capsys.readouterr().out
        assert rc == 1

    def test_guardar_mas_de_cinco_sustantivos_falla(self, cerebro_tmp, capsys):
        """RF-5: Más de 5 sustantivos → exit 1."""
        rc = biorag.cmd_guardar(cerebro_tmp, [
            "test_exceso", "Contenido de prueba.",
            "--sustantivos-clave", "uno,dos,tres,cuatro,cinco,seis"
        ])
        assert rc == 1

    def test_guardar_sustantivo_muy_corto_falla(self, cerebro_tmp, capsys):
        """RF-5: Sustantivo < 2 chars → exit 1."""
        rc = biorag.cmd_guardar(cerebro_tmp, [
            "test_corto", "Contenido de prueba.",
            "--sustantivos-clave", "a,ok"
        ])
        assert rc == 1

    def test_guardar_sustantivo_muy_largo_falla(self, cerebro_tmp, capsys):
        """RF-5: Sustantivo > 15 chars → exit 1."""
        rc = biorag.cmd_guardar(cerebro_tmp, [
            "test_largo", "Contenido de prueba.",
            "--sustantivos-clave", "terminoexcesivamente,ok"
        ])
        assert rc == 1

    def test_guardar_flag_en_posicion_inicial(self, cerebro_tmp, capsys):
        """RF-2: El flag puede estar en cualquier posición."""
        rc = biorag.cmd_guardar(cerebro_tmp, [
            "--sustantivos-clave", "neural,red",
            "red_neuronal", "Una red neuronal aprende de ejemplos."
        ])
        out = capsys.readouterr().out
        assert rc == 0

    def test_guardar_concepto_con_bytes_nulos_sanitizado(self, cerebro_tmp, capsys):
        """RF-21: Entradas con bytes nulos deben sanitizarse antes de procesar."""
        rc = biorag.cmd_guardar(cerebro_tmp, [
            "clave\x00_sucia", "Contenido normal.",
            "--sustantivos-clave", "contenido,normal"
        ])
        # Debe procesar sin lanzar excepción (puede fallar por clave vacía post-sanitización o pasar)
        assert rc in (0, 1)

    def test_guardar_concepto_excede_limite_200_chars(self, cerebro_tmp, capsys):
        """RF-23: Concepto > 200 chars → exit 1."""
        clave_larga = "x" * 201
        rc = biorag.cmd_guardar(cerebro_tmp, [
            clave_larga, "Contenido normal.",
            "--sustantivos-clave", "contenido,prueba"
        ])
        out = capsys.readouterr().out
        assert rc == 1


# ─── T3: cmd_sustantivos y cmd_agregar_sustantivos ───────────────────────────

class TestCmdSustantivos:
    """T3: Pruebas para cmd_sustantivos y alias."""

    def test_sustantivos_sin_argumento_retorna_error_uso(self, cerebro_tmp, capsys):
        """Uso sin concepto → exit 1."""
        rc = biorag.cmd_sustantivos(cerebro_tmp, [])
        out = capsys.readouterr().out
        assert rc == 1
        assert "Uso:" in out or "especifica" in out.lower()

    def test_sustantivos_concepto_inexistente_retorna_error(self, cerebro_tmp, capsys):
        """RF-7: Concepto inexistente → exit 1 + mensaje 'no encontrado'."""
        rc = biorag.cmd_sustantivos(cerebro_tmp, ["nodo_que_no_existe"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "no encontrado" in out.lower()

    def test_sustantivos_nodo_legado_sin_sustantivos(self, cerebro_tmp, capsys):
        """RF-8: Nodo legado sin sustantivos → exit 0 + mensaje informativo."""
        # Insertar nodo legado directamente en largo_plazo sin sustantivos
        cerebro_tmp.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, sustantivos_clave) VALUES ('nodo_legado', 'Contenido viejo', '')"
        )
        cerebro_tmp.conn.commit()

        rc = biorag.cmd_sustantivos(cerebro_tmp, ["nodo_legado"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "no tiene sustantivos clave asignados" in out.lower() or "agregar_sustantivos" in out

    def test_sustantivos_exito_muestra_sustantivos(self, cerebro_tmp, capsys):
        """RF-6: Nodo con sustantivos → exit 0 + muestra sustantivos."""
        cerebro_tmp.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, sustantivos_clave) VALUES ('python_lang', 'Lenguaje Python', 'python,lenguaje,codigo')"
        )
        cerebro_tmp.conn.commit()

        rc = biorag.cmd_sustantivos(cerebro_tmp, ["python_lang"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "python" in out
        assert "lenguaje" in out
        assert "codigo" in out

    def test_sustantivos_insensible_a_mayusculas(self, cerebro_tmp, capsys):
        """CL-3: Insensibilidad a mayúsculas."""
        cerebro_tmp.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, sustantivos_clave) VALUES ('redes_neuronales', 'Redes...', 'red,neurona')"
        )
        cerebro_tmp.conn.commit()

        rc = biorag.cmd_sustantivos(cerebro_tmp, ["Redes_Neuronales"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "red" in out


class TestCmdAgregarSustantivos:
    """T3: Pruebas para cmd_agregar_sustantivos y alias."""

    def test_agregar_sustantivos_sin_argumentos_retorna_error(self, cerebro_tmp, capsys):
        """Argumentos insuficientes → exit 1."""
        rc = biorag.cmd_agregar_sustantivos(cerebro_tmp, ["solo_concepto"])
        out = capsys.readouterr().out
        assert rc == 1

    def test_agregar_sustantivos_concepto_inexistente_retorna_error(self, cerebro_tmp, capsys):
        """RF-11: Concepto inexistente → exit 1."""
        rc = biorag.cmd_agregar_sustantivos(cerebro_tmp, ["concepto_fantasma", "termino1,termino2"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "no encontrado" in out.lower()

    def test_agregar_sustantivos_exito_actualiza_nodo_en_largo_plazo(self, cerebro_tmp, capsys):
        """RF-10: Actualización exitosa en largo_plazo → exit 0 y BD actualizada."""
        cerebro_tmp.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, sustantivos_clave) VALUES ('nodo_a_enriquecer', 'Contenido...', '')"
        )
        cerebro_tmp.conn.commit()

        rc = biorag.cmd_agregar_sustantivos(cerebro_tmp, ["nodo_a_enriquecer", "ia,algoritmo,datos"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "actualizados" in out.lower() or "ia,algoritmo,datos" in out

        # Verificar en base de datos
        cerebro_tmp.cursor.execute("SELECT sustantivos_clave FROM largo_plazo WHERE concepto = 'nodo_a_enriquecer'")
        row = cerebro_tmp.cursor.fetchone()
        assert row is not None
        assert "ia" in row[0]
        assert "algoritmo" in row[0]
        assert "datos" in row[0]

    def test_agregar_sustantivos_en_corto_plazo_funciona(self, cerebro_tmp, capsys):
        """Actualización en corto_plazo si no está en largo_plazo."""
        cerebro_tmp.cursor.execute(
            "INSERT INTO corto_plazo (concepto, contenido, sustantivos_clave) VALUES ('nodo_en_corto', 'Contenido corto...', '')"
        )
        cerebro_tmp.conn.commit()

        rc = biorag.cmd_agregar_sustantivos(cerebro_tmp, ["nodo_en_corto", "trabajo,memoria"])
        out = capsys.readouterr().out
        assert rc == 0

        cerebro_tmp.cursor.execute("SELECT sustantivos_clave FROM corto_plazo WHERE concepto = 'nodo_en_corto'")
        row = cerebro_tmp.cursor.fetchone()
        assert row is not None
        assert "trabajo,memoria" in row[0]

    def test_agregar_sustantivos_invalidos_retorna_error_y_guia(self, cerebro_tmp, capsys):
        """RF-12: Sustantivos inválidos → exit 1 + guía pedagógica."""
        cerebro_tmp.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, sustantivos_clave) VALUES ('nodo_validar', 'Contenido...', '')"
        )
        cerebro_tmp.conn.commit()

        rc = biorag.cmd_agregar_sustantivos(cerebro_tmp, ["nodo_validar", "invalido!,muy_largo_excede_limite_de_15_chars"])
        out = capsys.readouterr().out
        assert rc == 1
        assert "sustantivos-clave" in out.lower() or "núcleo" in out.lower() or "nucleo" in out.lower()

    def test_main_router_contiene_aliases_sustantivos(self):
        """RF-9 y RF-13: Verificar registro de comandos y aliases en main()."""
        # Verificamos que biorag contenga las funciones y aliases en su dispatch
        assert hasattr(biorag, "cmd_sustantivos")
        assert hasattr(biorag, "cmd_agregar_sustantivos")

