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
    entorno = install._publicar_entorno_privado(raiz, Path('requirements.txt'))
    assert install._leer_entorno_publicado(raiz) == entorno
    assert install._comprobar_python_sqlite(entorno) >= (3, 51, 3)
    result = subprocess.run(
        [entorno, '-I', '-c', 'import sqlite3,numpy,nltk,mcp,pydantic,fastapi; print(sqlite3.sqlite_version)'],
        env=install._entorno_runtime(), capture_output=True, text=True, timeout=60, check=True,
    )
    print(f'SQLite efectivo en entorno privado: {result.stdout.strip()}')


@pytest.mark.skipif(os.environ.get('BIORAG_TEST_RUNTIME_REAL') != '1', reason='requiere red y descarga real')
def test_descarga_uv_sin_pip_global(tmp_path):
    binario = install._descargar_uv_sin_pip(tmp_path)
    result = subprocess.run([binario, '--version'], env=install._entorno_runtime(),
                            capture_output=True, text=True, timeout=30, check=True)
    assert result.stdout.startswith('uv ' + install._UV_VERSION)


@pytest.mark.skipif(os.environ.get('BIORAG_TEST_RUNTIME_REAL') != '1', reason='requiere red y descarga real')
def test_instalacion_configura_mcp_con_runtime_real_sin_tocar_base(tmp_path, monkeypatch):
    import json
    import shutil
    proyecto = tmp_path / 'proyecto'
    proyecto.mkdir()
    shutil.copy(Path('requirements.txt'), proyecto / 'requirements.txt')
    (proyecto / 'mcp_server.py').write_text('# servidor de prueba\n')
    db = proyecto / 'MemoryBioRAG_Data' / 'memory_biorag.db'
    db.parent.mkdir()
    db.write_bytes(b'datos originales que no deben abrirse')
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    config = tmp_path / 'mcp.json'
    config.write_text(json.dumps({'mcpServers': {'biorag': {'command': 'python-antiguo', 'args': [str(proyecto / 'mcp_server.py')]}}}))
    info = {'path': config, 'key_path': ['mcpServers', 'biorag'], 'format': 'stdio', 'label': 'Cliente de prueba'}
    monkeypatch.setattr(install, 'INSTALL_DIR', proyecto)
    monkeypatch.setattr(install, 'BACKUPS_DIR', tmp_path / 'backups')
    monkeypatch.setattr(install, '_RUNTIME_PYTHON', None)
    monkeypatch.setattr(install, '_raiz_runtime_instalacion', lambda: raiz)
    monkeypatch.setattr(install, '_download_repo', lambda: None)
    monkeypatch.setattr(install, '_install_wordnet', lambda: None)
    monkeypatch.setattr(install, '_install_skill', lambda: None)
    monkeypatch.setattr(install, '_platform_configs', lambda: {'prueba': info})
    monkeypatch.setattr(install, '_interactive', lambda: False)
    install.install()
    entrada = json.loads(config.read_text())['mcpServers']['biorag']
    assert entrada['command'] == install._leer_entorno_publicado(raiz)
    assert entrada['args'] == [str(proyecto / 'mcp_server.py')]
    assert db.read_bytes() == b'datos originales que no deben abrirse'


@pytest.mark.skipif(os.environ.get('BIORAG_TEST_RUNTIME_REAL') != '1', reason='requiere red y entorno temporal de pip')
def test_pip_instala_paquete_con_freeze_en_entorno_temporal(tmp_path):
    import json
    import shutil
    import sys
    import tomllib
    proyecto = tmp_path / 'paquete'
    proyecto.mkdir()
    for archivo in ('pyproject.toml', 'README.md', 'biorag.py', 'mcp_server.py', 'install.py'):
        shutil.copy(Path(archivo), proyecto / archivo)
    shutil.copytree('core', proyecto / 'core', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    entorno = tmp_path / 'venv'
    subprocess.run([sys.executable, '-m', 'venv', str(entorno)], check=True, timeout=180)
    python = entorno / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    subprocess.run([str(python), '-I', '-m', 'pip', '--isolated', 'install', '--no-deps', str(proyecto)],
                   env=install._entorno_runtime(), check=True, capture_output=True, text=True, timeout=300)
    script = "import json,importlib.metadata as m; print(json.dumps(m.requires('memory-biorag')))"
    salida = subprocess.run([str(python), '-I', '-c', script], cwd=tmp_path,
                            env=install._entorno_runtime(), check=True, capture_output=True, text=True, timeout=30)
    obtenidas = {req.split(';', 1)[0].strip() for req in json.loads(salida.stdout)}
    metadata = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']
    assert obtenidas == set(metadata['dependencies'] + metadata['optional-dependencies']['dev'])
