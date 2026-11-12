"""Contratos de instalación: código y datos del clon no se sustituyen."""
from pathlib import Path

import install


def test_instalador_lanzado_desde_clon_usa_ese_clon(tmp_path, monkeypatch):
    repo = tmp_path / 'mi repositorio'
    repo.mkdir()
    (repo / 'mcp_server.py').write_text('# fixture')
    (repo / 'core').mkdir()
    (repo / 'install.py').write_text('# fixture')
    (repo / 'MemoryBioRAG_Data').mkdir()
    db = repo / 'MemoryBioRAG_Data' / 'memory_biorag.db'
    db.write_bytes(b'memoria original')
    monkeypatch.setattr(install, '__file__', str(repo / 'install.py'))
    monkeypatch.setattr(install.Path, 'home', lambda: tmp_path)
    assert install._resolve_install_dir() == repo.resolve()
    monkeypatch.setattr(install, 'INSTALL_DIR', install._resolve_install_dir())
    monkeypatch.setattr(install, '_RUNTIME_PYTHON', str(tmp_path / 'entorno' / 'python'))
    config = install._build_stdio_entry()
    assert config['command'] == str(tmp_path / 'entorno' / 'python')
    assert config['args'] == [str(repo.resolve() / 'mcp_server.py')]
    assert install._db_path() == db.resolve()
    assert db.read_bytes() == b'memoria original'


def test_clones_distintos_tienen_raices_de_runtime_distintas(tmp_path, monkeypatch):
    monkeypatch.setattr(install.Path, 'home', lambda: tmp_path)
    repos = [tmp_path / 'proyecto-a', tmp_path / 'proyecto-b']
    for repo in repos:
        repo.mkdir()
    monkeypatch.setattr(install, 'INSTALL_DIR', repos[0])
    primero = install._raiz_runtime_instalacion()
    monkeypatch.setattr(install, 'INSTALL_DIR', repos[1])
    segundo = install._raiz_runtime_instalacion()
    assert primero != segundo
    assert primero.is_dir() and segundo.is_dir()
    assert primero.parent == segundo.parent == tmp_path / '.biorag' / 'runtimes'
    assert all(not (repo / 'MemoryBioRAG_Data').exists() for repo in repos)


def test_instalador_fuera_de_un_clon_elige_carpeta_de_usuario(tmp_path, monkeypatch):
    suelto = tmp_path / 'descarga' / 'install.py'
    suelto.parent.mkdir()
    suelto.write_text('# fixture')
    monkeypatch.setattr(install, '__file__', str(suelto))
    monkeypatch.setattr(install.Path, 'home', lambda: tmp_path)
    assert install._resolve_install_dir() == tmp_path / 'biorag'
