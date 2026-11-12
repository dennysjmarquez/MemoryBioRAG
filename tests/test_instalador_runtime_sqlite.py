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
    monkeypatch.setattr(install, '_descargar_uv_sin_pip', lambda _: '/uv-simulado')
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


def test_recurre_a_bootstrap_sin_pip(tmp_path, monkeypatch):
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    candidato = raiz / 'python'
    candidato.write_text('solo simulación')
    llamadas = []
    def ejecutar(args, **kwargs):
        llamadas.append(args)
        if len(llamadas) == 1:
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, str(candidato) if 'find' in args else '', '')
    monkeypatch.setattr(install.subprocess, 'run', ejecutar)
    monkeypatch.setattr(install, '_descargar_uv_sin_pip', lambda _: '/uv-simulado')
    monkeypatch.setattr(install, '_comprobar_python_sqlite', lambda _: (3, 51, 3))
    assert install._descargar_python_privado(raiz) == str(candidato)
    assert llamadas[1][0] == '/uv-simulado'


@pytest.mark.parametrize(('plataforma', 'fragmento'), [
    ('win-amd64', 'win_amd64.whl'),
    ('win-arm64', 'win_arm64.whl'),
    ('macosx-11.0-arm64', 'macosx_11_0_arm64.whl'),
    ('macosx-10.13-x86_64', 'macosx_10_12_x86_64.whl'),
])
def test_ruedas_para_sistemas_conocidos(monkeypatch, plataforma, fragmento):
    monkeypatch.setattr(install.sysconfig, 'get_platform', lambda: plataforma)
    assert install._rueda_uv_plataforma().endswith(fragmento)


def test_rueda_rechaza_plataforma_desconocida(monkeypatch):
    monkeypatch.setattr(install.sysconfig, 'get_platform', lambda: 'desconocida')
    with pytest.raises(RuntimeError, match='Plataforma'):
        install._rueda_uv_plataforma()


def test_publica_solo_despues_de_preparar_y_validar(tmp_path, monkeypatch):
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    anterior = raiz / 'anterior'
    anterior.write_text('conservado')
    req = tmp_path / 'requirements.txt'
    req.write_text('')
    nueva = raiz / 'entorno-nuevo' / 'python'
    nueva.parent.mkdir()
    nueva.write_text('simulado')
    marcador = raiz / 'actual.json'
    marcador.write_text(json.dumps({'version': 1, 'python': str(anterior)}))
    monkeypatch.setattr(install, '_descargar_python_privado', lambda _: 'base')
    def crear(base, directorio, requisitos):
        assert json.loads(marcador.read_text())['python'] == str(anterior)
        return str(nueva)
    monkeypatch.setattr(install, '_crear_entorno_privado', crear)
    monkeypatch.setattr(install, '_comprobar_python_sqlite', lambda _: (3, 51, 3))
    assert install._publicar_entorno_privado(raiz, req) == str(nueva)
    assert install._leer_entorno_publicado(raiz) == str(nueva)
    assert anterior.read_text() == 'conservado'
    assert not list(raiz.glob('.runtime-*.tmp'))


def test_publicacion_fallida_conserva_marcador_previo(tmp_path, monkeypatch):
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    marcador = raiz / 'actual.json'
    marcador.write_text('marcador anterior')
    monkeypatch.setattr(install, '_descargar_python_privado', lambda _: 'base')
    def falla(*args):
        raise RuntimeError('sin red')
    monkeypatch.setattr(install, '_crear_entorno_privado', falla)
    with pytest.raises(RuntimeError, match='sin red'):
        install._publicar_entorno_privado(raiz, tmp_path / 'req')
    assert marcador.read_text() == 'marcador anterior'


def test_marcador_no_puede_apuntar_fuera_de_raiz(tmp_path, monkeypatch):
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    fuera = tmp_path / 'python'
    fuera.write_text('no ejecutar')
    (raiz / 'actual.json').write_text(json.dumps({'version': 1, 'python': str(fuera)}))
    monkeypatch.setattr(install, '_comprobar_python_sqlite', lambda _: pytest.fail('no debe ejecutarse'))
    with pytest.raises(RuntimeError, match='fuera'):
        install._leer_entorno_publicado(raiz)


def test_publicacion_atomica_fallida_conserva_anterior(tmp_path, monkeypatch):
    raiz = tmp_path / 'runtime'
    raiz.mkdir(mode=0o700)
    marcador = raiz / 'actual.json'
    marcador.write_text('anterior')
    nuevo = raiz / 'nuevo'
    nuevo.write_text('simulado')
    monkeypatch.setattr(install, '_descargar_python_privado', lambda _: 'base')
    monkeypatch.setattr(install, '_crear_entorno_privado', lambda *args: str(nuevo))
    monkeypatch.setattr(install, '_comprobar_python_sqlite', lambda _: (3, 51, 3))
    monkeypatch.setattr(install.os, 'replace', lambda *args: (_ for _ in ()).throw(OSError('disco lleno')))
    with pytest.raises(OSError, match='disco lleno'):
        install._publicar_entorno_privado(raiz, tmp_path / 'req')
    assert marcador.read_text() == 'anterior'
    assert not list(raiz.glob('.runtime-*.tmp'))


@pytest.mark.parametrize('formato', ['standard', 'opencode'])
def test_config_existente_debe_coincidir_en_interprete_y_script(tmp_path, monkeypatch, formato):
    python = str(tmp_path / 'python-privado')
    anterior = str(tmp_path / 'python-viejo')
    script = str(tmp_path / 'mcp_server.py')
    monkeypatch.setattr(install, '_python', lambda: python)
    monkeypatch.setattr(install, '_script_path', lambda: tmp_path / 'mcp_server.py')
    config = tmp_path / 'config.json'
    def guardar(comando):
        entrada = {'command': [comando, script]} if formato == 'opencode' else {'command': comando, 'args': [script]}
        config.write_text(json.dumps({'mcp': {'biorag': entrada}}))
    info = {'path': config, 'key_path': ['mcp', 'biorag'], 'format': 'stdio'}
    guardar(anterior)
    assert not install._biorag_already_configured(info)
    guardar(python)
    assert install._biorag_already_configured(info)


def test_escapado_systemd_no_interpreta_rutas():
    assert install._systemd_argumento('/tmp/a %"\\x') == '"/tmp/a %%\\"\\\\x"'
    with pytest.raises(ValueError):
        install._systemd_argumento('/tmp/a\nExecStart=malicioso')


@pytest.mark.skipif(sys.platform != 'linux', reason='servicio Linux')
def test_servicio_usuario_usa_runtime_sin_sudo(tmp_path, monkeypatch):
    monkeypatch.setattr(install.Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(install, '_python', lambda: str(tmp_path / 'Python privado' / 'python'))
    monkeypatch.setattr(install, '_script_path', lambda: tmp_path / 'codigo' / 'mcp_server.py')
    comandos = []
    def ejecutar(args, **kwargs):
        comandos.append(args)
        return subprocess.CompletedProcess(args, 0, '', '')
    monkeypatch.setattr(install.subprocess, 'run', ejecutar)
    assert install._install_systemd(8080)
    unidad = (tmp_path / '.config/systemd/user/biorag-mcp.service').read_text()
    assert f'ExecStart="{tmp_path}/Python privado/python"' in unidad
    assert 'UnsetEnvironment=LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME' in unidad
    assert comandos == [['systemctl', '--user', 'daemon-reload']]
    assert not list((tmp_path / '.config/systemd/user').glob('.biorag-*.tmp'))


@pytest.mark.parametrize(('arquitectura', 'rueda'), [
    ('arm64', 'macosx_11_0_arm64.whl'),
    ('x86_64', 'macosx_10_12_x86_64.whl'),
])
def test_macos_universal2_usa_arquitectura_activa(monkeypatch, arquitectura, rueda):
    monkeypatch.setattr(install.sysconfig, 'get_platform', lambda: 'macosx-10.13-universal2')
    monkeypatch.setattr(install.platform, 'machine', lambda: arquitectura)
    assert install._rueda_uv_plataforma().endswith(rueda)
