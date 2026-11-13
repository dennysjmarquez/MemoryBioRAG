"""La instalación del paquete y el freeze deben fijar las mismas dependencias.

Evita que `pip install .` se desvíe silenciosamente de las versiones medidas
con `pip install -r requirements.txt`. No comprueba SQLite ni ejecuta el instalador.
"""
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_paquete_y_requirements_comparten_freeze():
    proyecto = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    declaradas = proyecto['dependencies'] + proyecto['optional-dependencies']['dev']
    requirements = [line.strip() for line in (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines()
                    if line.strip() and not line.lstrip().startswith('#')]
    assert all('==' in requisito for requisito in declaradas)
    assert sorted(declaradas) == sorted(requirements)


def test_metadatos_versionados_no_contradicen_el_freeze():
    import email
    proyecto = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    metadata = email.message_from_string((ROOT / 'memory_biorag.egg-info/PKG-INFO').read_text(encoding='utf-8'))
    requisitos = {line.split(';', 1)[0].strip() for line in metadata.get_all('Requires-Dist', [])}
    assert requisitos == set(proyecto['dependencies'] + proyecto['optional-dependencies']['dev'])
    assert metadata['Requires-Python'] == proyecto['requires-python']
    egg_requirements = {line.strip() for line in (ROOT / 'memory_biorag.egg-info/requires.txt').read_text(encoding='utf-8').splitlines()
                        if line.strip() and not line.startswith('[')}
    assert egg_requirements == requisitos
