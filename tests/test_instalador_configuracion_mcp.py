"""El instalador no debe destruir otras configuraciones de los agentes."""
import json

import pytest

import install


@pytest.fixture
def plataforma(tmp_path, monkeypatch):
    archivo = tmp_path / 'config.jsonc'
    monkeypatch.setattr(install, 'BACKUPS_DIR', tmp_path / 'backups')
    monkeypatch.setattr(install, '_python', lambda: '/runtime privado/python')
    monkeypatch.setattr(install, '_script_path', lambda: tmp_path / 'mcp_server.py')
    return archivo, {'path': archivo, 'key_path': ['mcpServers', 'biorag'],
                     'format': 'stdio', 'label': 'Agente'}


def test_preserva_jsonc_comentarios_cadenas_y_campos_del_servidor(plataforma):
    archivo, info = plataforma
    original = ('{\r\n  // comentario de usuario\r\n  "url": "https://ejemplo.test/a,}",\r\n'
                '  "mcpServers": {\r\n    /* otro servidor */\r\n'
                '    "otro": {"command": "sin cambios"},\r\n'
                '    "biorag": {"command": "viejo", "args": ["antiguo"], '
                '"env": {"BIORAG_PATH": "mi memoria"}}, // comentario final\r\n  },\r\n}\r\n')
    archivo.write_bytes(original.encode('utf-8'))
    assert install._configure_platform('agente', info)
    result = archivo.read_bytes().decode('utf-8')
    assert '// comentario de usuario\r\n' in result
    assert '/* otro servidor */' in result
    assert '// comentario final\r\n' in result
    assert 'https://ejemplo.test/a,}' in result
    assert '\r\n' in result
    datos, _, _ = install._parsear_config_segura(result)
    assert datos['mcpServers']['otro'] == {'command': 'sin cambios'}
    assert datos['mcpServers']['biorag']['env'] == {'BIORAG_PATH': 'mi memoria'}
    assert datos['mcpServers']['biorag']['command'] == '/runtime privado/python'


@pytest.mark.parametrize('original', [
    '{"mcpServers": {"otro":',
    '{"mcpServers": "valor personalizado"}',
    '{"mcpServers": {}, "mcpServers": {}}',
    '{"mcpServers": {"biorag": ["configuracion"]}}',
    '/* comentario sin cerrar',
    '',
])
def test_no_sobrescribe_config_invalida_o_incompatible(plataforma, original):
    archivo, info = plataforma
    archivo.write_text(original, encoding='utf-8')
    assert not install._configure_platform('agente', info)
    assert archivo.read_text(encoding='utf-8') == original


@pytest.mark.parametrize('original', [
    '{}', '{"mcpServers": {}}', '{"mcpServers": {"otro": 1}}',
    '{"mcpServers": {"otro": 1, /* mantener */ }}',
    '{"mcpServers": {"otro": 1 // mantener\n}}',
    '{"mcpServers": {"biorag": null}}',
])
def test_inserta_entrada_sin_perder_otros_valores(plataforma, original):
    archivo, info = plataforma
    archivo.write_text(original, encoding='utf-8')
    assert install._configure_platform('agente', info)
    resultado, _, _ = install._parsear_config_segura(archivo.read_text(encoding='utf-8'))
    assert resultado['mcpServers']['biorag']['command'] == '/runtime privado/python'
    if 'mantener' in original:
        assert 'mantener' in archivo.read_text(encoding='utf-8')
    if 'otro' in original:
        assert resultado['mcpServers']['otro'] == 1


def test_cambio_concurrente_no_se_restura_sobre_terceros(plataforma, monkeypatch):
    archivo, info = plataforma
    original = '{"mcpServers": {}}'
    archivo.write_text(original)
    reemplazo_externo = '{"externo": true}'
    def backup(path):
        path.write_text(reemplazo_externo)
        return None
    monkeypatch.setattr(install, '_backup_file', backup)
    assert not install._configure_platform('agente', info)
    assert archivo.read_text() == reemplazo_externo
    assert not list(archivo.parent.glob('.biorag-config-*.tmp'))


def test_fallo_escritura_no_toca_original(plataforma, monkeypatch):
    archivo, info = plataforma
    original = '{"mcpServers": {}}'
    archivo.write_text(original)
    def fallo(*_):
        raise OSError('disco lleno')
    monkeypatch.setattr(install.os, 'replace', fallo)
    assert not install._configure_platform('agente', info)
    assert archivo.read_text() == original
    assert not list(archivo.parent.glob('.biorag-config-*.tmp'))


def test_config_con_enlace_simbolico_se_preserva(plataforma):
    archivo, info = plataforma
    destino = archivo.parent / 'config-real.json'
    destino.write_text('{"mcpServers": {}}')
    try:
        archivo.symlink_to(destino)
    except (OSError, NotImplementedError):
        pytest.skip('enlaces simbólicos no permitidos en esta plataforma')
    assert not install._configure_platform('agente', info)
    assert archivo.is_symlink()
    assert destino.read_text() == '{"mcpServers": {}}'


def test_opencode_preserva_environment_y_decision_de_desactivar(tmp_path, monkeypatch):
    archivo = tmp_path / 'opencode.jsonc'
    archivo.write_text('{"mcp": {"biorag": {"type": "local", "command": ["viejo", "script"], "enabled": false, "environment": {"BIORAG_PATH": "mi-db"}}}}')
    info = {'path': archivo, 'key_path': ['mcp', 'biorag'], 'format': 'stdio', 'label': 'OpenCode'}
    monkeypatch.setattr(install, 'BACKUPS_DIR', tmp_path / 'backups')
    monkeypatch.setattr(install, '_python', lambda: '/privado/python')
    monkeypatch.setattr(install, '_script_path', lambda: tmp_path / 'mcp_server.py')
    monkeypatch.setattr(install, '_install_opencode_plugin', lambda: True)
    assert install._configure_platform('opencode', info)
    entrada = json.loads(archivo.read_text())['mcp']['biorag']
    assert entrada['command'] == ['/privado/python', str(tmp_path / 'mcp_server.py')]
    assert entrada['environment']['BIORAG_PATH'] == 'mi-db'
    assert entrada['enabled'] is False


def test_instalacion_no_informa_exito_si_configuracion_falla(tmp_path, monkeypatch, capsys):
    proyecto = tmp_path / 'proyecto'
    proyecto.mkdir()
    config = tmp_path / 'invalido.json'
    config.write_text('{"mcpServers":')
    info = {'path': config, 'key_path': ['mcpServers', 'biorag'], 'format': 'stdio', 'label': 'Cliente'}
    monkeypatch.setattr(install, 'INSTALL_DIR', proyecto)
    monkeypatch.setattr(install, '_download_repo', lambda: None)
    monkeypatch.setattr(install, '_preparar_runtime_instalacion', lambda: 'runtime-simulado')
    monkeypatch.setattr(install, '_install_wordnet', lambda: None)
    monkeypatch.setattr(install, '_install_skill', lambda: None)
    monkeypatch.setattr(install, '_checkpoint2', lambda: None)
    monkeypatch.setattr(install, '_verify_final', lambda: pytest.fail('no debe declarar éxito'))
    monkeypatch.setattr(install, '_platform_configs', lambda: {'cliente': info})
    monkeypatch.setattr(install, '_interactive', lambda: False)
    with pytest.raises(SystemExit) as error:
        install.install()
    assert error.value.code == 1
    assert config.read_text() == '{"mcpServers":'
    assert 'Instalación completada' not in capsys.readouterr().out
