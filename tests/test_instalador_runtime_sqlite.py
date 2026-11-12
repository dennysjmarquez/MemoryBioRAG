"""Sondeo aislado del runtime: nunca abre la base ni sus archivos auxiliares."""
import json
import subprocess
import sys

import pytest

import install


def test_sondeo_efectivo_con_fts5():
    assert install._comprobar_python_sqlite(sys.executable) == __import__('sqlite3').sqlite_version_info


def test_sondeo_rechaza_fts5_inoperante(monkeypatch):
    def fallo(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, '', 'FTS5 unavailable')
    monkeypatch.setattr(install.subprocess, 'run', fallo)
    with pytest.raises(RuntimeError, match='FTS5'):
        install._comprobar_python_sqlite('python')


def test_sondeo_rechaza_respuesta_invalida(monkeypatch):
    def respuesta(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, json.dumps([3, True, 1]), '')
    monkeypatch.setattr(install.subprocess, 'run', respuesta)
    with pytest.raises(RuntimeError, match='versión'):
        install._comprobar_python_sqlite('python')


def test_sondeo_aísla_variables_que_alteran_runtime(monkeypatch):
    for k in ('UV_PYTHON_DOWNLOADS_JSON_URL', 'PIP_INDEX_URL', 'PYTHONPATH', 'LD_PRELOAD', 'DYLD_INSERT_LIBRARIES'):
        monkeypatch.setenv(k, 'no-confiable')
    env = install._entorno_runtime()
    for k in ('UV_PYTHON_DOWNLOADS_JSON_URL', 'PIP_INDEX_URL', 'PYTHONPATH', 'LD_PRELOAD', 'DYLD_INSERT_LIBRARIES'):
        assert k not in env


def test_crea_generacion_privada_sin_publicar_y_conserva_la_anterior(tmp_path, monkeypatch):
    # El entorno es real; se simula la versión para ejercitar el flujo en el
    # Python del CI, que puede tener SQLite vulnerable. No prueba una descarga.
    monkeypatch.setattr(install, '_comprobar_python_sqlite', lambda _: (3, 51, 3))
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    anterior = raiz / 'entorno-anterior'
    anterior.mkdir()
    (anterior / 'en-uso').write_text('intacto')
    requisitos = tmp_path / 'requirements.txt'
    requisitos.write_text('')
    python = install._crear_entorno_privado(sys.executable, raiz, requisitos)
    result = subprocess.run([python, '-I', '-c', 'import sys; print(sys.prefix)'],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip().startswith(str(raiz))
    assert (anterior / 'en-uso').read_text() == 'intacto'
    assert python != sys.executable


def test_no_instala_con_sqlite_vulnerable(tmp_path, monkeypatch):
    monkeypatch.setattr(install, '_comprobar_python_sqlite', lambda _: (3, 51, 2))
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    req = tmp_path / 'requirements.txt'
    req.write_text('')
    with pytest.raises(RuntimeError, match='SQLite'):
        install._crear_entorno_privado(sys.executable, raiz, req)
    assert list(raiz.iterdir()) == []


def test_fallo_instalacion_solo_elimina_generacion_nueva(tmp_path, monkeypatch):
    monkeypatch.setattr(install, '_comprobar_python_sqlite', lambda _: (3, 51, 3))
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    anterior = raiz / 'entorno-anterior'
    anterior.mkdir()
    req = tmp_path / 'requirements.txt'
    req.write_text('')
    def fallo(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)
    monkeypatch.setattr(install.subprocess, 'run', fallo)
    with pytest.raises(subprocess.CalledProcessError):
        install._crear_entorno_privado(sys.executable, raiz, req)
    assert list(raiz.iterdir()) == [anterior]


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX permissions')
def test_rechaza_raiz_compartida(tmp_path, monkeypatch):
    monkeypatch.setattr(install, '_comprobar_python_sqlite', lambda _: (3, 51, 3))
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o755)
    raiz.chmod(0o755)
    req = tmp_path / 'requirements.txt'
    req.write_text('')
    with pytest.raises(RuntimeError, match='exclusiva'):
        install._crear_entorno_privado(sys.executable, raiz, req)


def test_descarga_rechaza_interprete_fuera_de_raiz(tmp_path, monkeypatch):
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    fuera = tmp_path / 'python'
    fuera.write_text('no ejecutar')
    comandos = []
    def simular(args, **kwargs):
        comandos.append(args)
        return subprocess.CompletedProcess(args, 0, str(fuera) if 'find' in args else '', '')
    monkeypatch.setattr(install.subprocess, 'run', simular)
    with pytest.raises(RuntimeError, match='fuera'):
        install._descargar_python_privado(raiz)
    assert '--require-hashes' in comandos[0]
    assert '--no-registry' in comandos[1]
    assert '--managed-python' in comandos[2]


def test_descarga_falla_sin_activar_python(tmp_path, monkeypatch):
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    def fallo(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr='fallo de red')
    monkeypatch.setattr(install.subprocess, 'run', fallo)
    with pytest.raises(RuntimeError, match='descargar'):
        install._descargar_python_privado(raiz)
    assert not list(raiz.iterdir())


def test_verifica_de_nuevo_tras_instalar_dependencias(tmp_path, monkeypatch):
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    req = tmp_path / 'requirements.txt'
    req.write_text('')
    versiones = iter([(3, 51, 3), (3, 51, 3), (3, 51, 2)])
    monkeypatch.setattr(install, '_comprobar_python_sqlite', lambda _: next(versiones))
    monkeypatch.setattr(install.subprocess, 'run', lambda args, **kwargs: subprocess.CompletedProcess(args, 0, '', ''))
    with pytest.raises(RuntimeError, match='cambió'):
        install._crear_entorno_privado(sys.executable, raiz, req)
    assert not list(raiz.iterdir())


def test_pip_ignora_configuracion_global_heredada(tmp_path, monkeypatch):
    import os
    configuracion = tmp_path / 'xdg' / 'pip'
    configuracion.mkdir(parents=True)
    (configuracion / 'pip.conf').write_text('[global]\nindex-url = https://ejemplo.invalid/simple\n')
    monkeypatch.setenv('XDG_CONFIG_DIRS', str(configuracion.parent))
    env = install._entorno_runtime()
    assert env['PIP_CONFIG_FILE'] == os.devnull
    result = subprocess.run([sys.executable, '-I', '-m', 'pip', '--isolated', 'config', 'list'],
                            env=env, text=True, capture_output=True, check=True)
    assert 'ejemplo.invalid' not in result.stdout
