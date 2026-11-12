"""Prueba con descargas reales y directorios temporales, sin usar la DB del usuario.

La activa CI con BIORAG_TEST_RUNTIME_REAL=1; requiere acceso a PyPI y a los
artefactos de python-build-standalone en GitHub. No es una simulación de SQLite.
"""
import os
from pathlib import Path
import subprocess

import pytest

import install


@pytest.mark.skipif(os.environ.get('BIORAG_TEST_RUNTIME_REAL') != '1', reason='requiere red y descarga real')
def test_descarga_python_y_crea_entorno_con_dependencias(tmp_path):
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    python = install._descargar_python_privado(raiz)
    assert install._comprobar_python_sqlite(python) >= (3, 51, 3)
    entorno = install._crear_entorno_privado(python, raiz, Path('requirements.txt'))
    assert install._comprobar_python_sqlite(entorno) >= (3, 51, 3)
    result = subprocess.run(
        [entorno, '-I', '-c', 'import sqlite3,numpy,nltk,mcp,pydantic,fastapi; print(sqlite3.sqlite_version)'],
        env=install._entorno_runtime(), capture_output=True, text=True, timeout=60, check=True,
    )
    print(f'SQLite efectivo en entorno privado: {result.stdout.strip()}')
