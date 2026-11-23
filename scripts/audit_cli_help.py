"""Capture and lint all public CLI help without opening memory or using the network.

Run: python scripts/audit_cli_help.py [output-directory]
Language scan reuses release_manifest.toml markers; it is a heuristic, not a
proof that every possible Spanish word has been detected. Review captures too.
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.cli import GROUPS, ALIASES

# Only public identifiers and previously published illustrative keys, not prose.
ALLOWLIST = {
    *[name for _, entries in GROUPS for name, _ in entries], *ALIASES,
    'registrar', 'revisar', 'confirmar', 'todos', 'recordar',
    'contexto_vigencia', 'vigente', 'historico', 'ambos',
    'sustantivos clave', 'cambio-puerto-001', 'aprobacion-001',
    'servicio_puerto_anterior', 'servicio_puerto_actual',
    '--sustantivos-clave', '--sustantivos', '--pagina', '--todos', '--modo',
    '--frase', '--completo', '--asociados', '--no-leidos', '--ultimos', '--para',
    '--mensaje', '--nodo-anterior', '--nodo-sucesor', '--entidad', '--atributo',
    '--ambito', '--valor-anterior', '--valor-nuevo', '--observado-en',
    '--efectivo-desde', '--anterior-desde',
}


def language_hits(text, markers):
    for identifier in sorted(ALLOWLIST, key=len, reverse=True):
        text = re.sub(r'(?<![\w-])' + re.escape(identifier) + r'(?![\w-])', '', text, flags=re.I)
    return [marker for marker in markers if re.search(
        re.escape(marker) if len(marker) == 1 else r'(?<!\w)' + re.escape(marker) + r'(?!\w)',
        text, re.I)]


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'docs/cli_help_audit/completed'
    output.mkdir(parents=True, exist_ok=True)
    markers = tomllib.loads((ROOT / 'release_manifest.toml').read_text())['language']['spanish_markers']
    requests = [[]] + [[name] for _, entries in GROUPS for name, _ in entries]
    requests += [['correcciones', name] for name in ('registrar', 'revisar', 'confirmar')]
    results = {}
    for args in requests:
        result = subprocess.run([sys.executable, '-S', 'biorag.py', *args, '--help'],
                                cwd=ROOT, capture_output=True, text=True, timeout=15)
        text = result.stdout + result.stderr
        key = '__'.join(args) or 'root'
        (output / (key + '.txt')).write_text(text)
        sections = ['usage:', 'summary:', 'what is it for?', 'options:', 'examples:', 'expected output:', 'see also:']
        positions = [text.lower().find(section) for section in sections]
        # argparse may place positional arguments before its options block.
        results[key] = dict(returncode=result.returncode, language_hits=language_hits(text, markers),
                            ordered_sections=all(p >= 0 for p in positions) and positions == sorted(positions),
                            internal_names=re.findall(r'athena|artemis|hermes|\bOEC\b', text, re.I))
    (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    (output / 'allowlist.json').write_text(json.dumps(sorted(ALLOWLIST), indent=2) + '\n')
    failed = {key: row for key, row in results.items() if row['returncode'] or row['language_hits']
              or not row['ordered_sections'] or row['internal_names']}
    print(json.dumps(failed or {'passed': len(results)}, indent=2))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
