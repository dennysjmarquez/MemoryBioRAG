#!/usr/bin/env python3
"""Rebuild isolated stdlib-vs-pysqlite3 full-test comparison with synthetic DBs.

Copies tracked source into temporary worktrees, excludes every SQLite database,
creates a new synthetic schema/fixture with stdlib SQLite, substitutes sqlite3
imports only in the candidate copy, and runs tests/ in separate processes.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE: Path
PYTHON: Path
PYSQ_TARGET: Path
SNAP_REL = Path('snapshots/qa_escape_qcr_20260811.db')
LIVE_REL = Path('MemoryBioRAG_Data/memory_biorag.db')
DB_SUFFIXES = {'.db', '.sqlite', '.sqlite3', '.db-wal', '.db-shm', '.sqlite-wal', '.sqlite-shm'}


def is_database_path(rel: str) -> bool:
    low = rel.lower()
    name = Path(low).name
    return any(name.endswith(suffix) for suffix in DB_SUFFIXES) or name.endswith(('-wal', '-shm', '-journal'))


def copy_tracked_repo(destination: Path, candidate: bool) -> tuple[int, int, list[str]]:
    files = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).split(b'\0')
    count = substitutions = 0
    skipped = []
    for raw in files:
        if not raw:
            continue
        rel = raw.decode('utf-8', 'surrogateescape')
        source = ROOT / rel
        if is_database_path(rel):
            skipped.append(rel)
            continue
        if not source.is_file():
            continue
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if candidate and source.suffix.lower() == '.py':
            changed, n = re.subn(rb'\bimport sqlite3\b', b'import pysqlite3 as sqlite3', data)
            data = changed
            substitutions += n
        target.write_bytes(data)
        count += 1
    return count, substitutions, skipped


def make_synthetic_seed(repo: Path, path: Path) -> dict:
    sys.path.insert(0, str(repo))
    from core.memory_store import SQLiteMemoryBioRAG, normalizar_sustantivos_clave, normalizar_sustantivos_clave_exacto
    from core.memory import consolidation
    memory = SQLiteMemoryBioRAG(str(path))
    try:
        category = memory._resolver_categoria_id('General')
        exact = normalizar_sustantivos_clave_exacto('fixture,synthetic')
        folded = normalizar_sustantivos_clave(exact)
        nodes = [
            ('synthetic_sqlite_alpha', 'Synthetic runtime fixture for alpha lookup, exception compatibility, and stable rows.'),
            ('synthetic_sqlite_beta', 'Synthetic runtime fixture with beta, a distinct row, and Unicode café data.'),
            ('synthetic_sqlite_gamma', 'Synthetic runtime fixture for numeric ordering, NULL handling, and transaction probes.'),
        ]
        for concept, content in nodes:
            consolidation.fusionar_en_largo_plazo(memory, concept, content, '', category, 0.0, folded, exact)
        memory.conn.commit()
        memory.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        tables = [row[0] for row in memory.conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        rows = memory.conn.execute('SELECT COUNT(*) FROM largo_plazo').fetchone()[0]
    finally:
        memory.cerrar_sistema()
    payload = path.read_bytes()
    return {'fixture': 'synthetic_only', 'nodes': [n[0] for n in nodes], 'largo_plazo_rows': rows,
            'table_names': tables, 'database_bytes': len(payload),
            'database_sha256': hashlib.sha256(payload).hexdigest()}


def junit_summary(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == 'testsuite' else list(root.iter('testsuite'))
    cases = list(root.iter('testcase'))
    failures = []
    errors = []
    skipped = []
    for case in cases:
        nodeid = f"{case.attrib.get('classname', '')}::{case.attrib.get('name', '')}"
        failure = case.find('failure')
        error = case.find('error')
        skip = case.find('skipped')
        item = {'nodeid': nodeid}
        if failure is not None:
            item.update({'message': failure.attrib.get('message', ''), 'detail': (failure.text or '')[:6000]})
            failures.append(item)
        if error is not None:
            item.update({'message': error.attrib.get('message', ''), 'detail': (error.text or '')[:6000]})
            errors.append(item)
        if skip is not None:
            skipped.append(nodeid)
    totals = {
        key: sum(float(s.attrib.get(key, 0)) for s in suites) if key == 'time'
        else sum(int(s.attrib.get(key, 0)) for s in suites)
        for key in ('tests', 'failures', 'errors', 'skipped', 'time')
    }
    return {'totals': totals, 'failure_ids': [f['nodeid'] for f in failures],
            'failures': failures, 'error_ids': [e['nodeid'] for e in errors], 'errors': errors,
            'skipped_ids': skipped}


def run_suite(label: str, repo: Path, out: Path, candidate: bool) -> dict:
    junit = out / 'junit.xml'
    log_out = out / 'pytest.stdout.txt'
    log_err = out / 'pytest.stderr.txt'
    env = os.environ.copy()
    for key in list(env):
        if key.startswith('BIORAG_') or key == 'PYTHONPATH':
            env.pop(key, None)
    env['PYTHONHASHSEED'] = '0'
    if candidate:
        env['PYTHONPATH'] = str(PYSQ_TARGET)
    cmd = [str(PYTHON), '-m', 'pytest', '-q', '--tb=short', f'--junitxml={junit}', 'tests']
    start = time.time()
    proc = subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True, timeout=2400)
    duration = time.time() - start
    log_out.write_text(proc.stdout, encoding='utf-8')
    log_err.write_text(proc.stderr, encoding='utf-8')
    result = {'runtime': label, 'command': cmd, 'cwd_label': label, 'exit_code': proc.returncode,
              'duration_seconds': round(duration, 3), 'stdout_tail': proc.stdout[-12000:],
              'stderr_tail': proc.stderr[-5000:], 'junit': None}
    if junit.exists():
        result['junit'] = junit_summary(junit)
    return result


def main() -> None:
    global ROOT, EVIDENCE, PYTHON, PYSQ_TARGET
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT,
                        help='Git checkout of the exact BioRAG source revision under test')
    parser.add_argument('--python', type=Path, default=Path(sys.executable),
                        help='Python environment containing pytest and the project test dependencies')
    parser.add_argument('--pysqlite3-path', type=Path, required=True,
                        help='Isolated --target directory containing pysqlite3 0.6.1')
    parser.add_argument('--output', type=Path, default=None,
                        help='Private output directory for logs/JUnit; default is a fresh directory in the system temp area')
    args = parser.parse_args()
    ROOT = args.source_root.resolve()
    PYTHON = args.python.resolve()
    PYSQ_TARGET = args.pysqlite3_path.resolve()
    if not (ROOT / '.git').exists() and not (ROOT / '.git').is_file():
        raise SystemExit(f'--source-root must be a Git checkout: {ROOT}')
    if not PYTHON.exists() or not PYSQ_TARGET.exists():
        raise SystemExit('Missing test interpreter or isolated pysqlite3 target')
    if args.output is None:
        EVIDENCE = Path(tempfile.mkdtemp(prefix='biorag_sqlite_ab_run_'))
    else:
        EVIDENCE = args.output.resolve()
        EVIDENCE.mkdir(parents=True, exist_ok=False)
    base_out = EVIDENCE / 'baseline'
    cand_out = EVIDENCE / 'candidate'
    base_out.mkdir(exist_ok=False)
    cand_out.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='biorag_sqlite_ab_') as tmp:
        tmp_root = Path(tmp)
        base_repo = tmp_root / 'baseline_repo'
        cand_repo = tmp_root / 'candidate_repo'
        base_repo.mkdir(); cand_repo.mkdir()
        base_n, base_subs, skipped_a = copy_tracked_repo(base_repo, False)
        cand_n, cand_subs, skipped_b = copy_tracked_repo(cand_repo, True)
        synthetic_path = base_repo / SNAP_REL
        synthetic_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_info = make_synthetic_seed(base_repo, synthetic_path)
        for repo in (base_repo, cand_repo):
            for rel in (SNAP_REL, LIVE_REL):
                target = repo / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if repo == base_repo and target == synthetic_path:
                    continue
                shutil.copyfile(synthetic_path, target)
        # Both runs start from the exact same synthetic DB bytes.
        (EVIDENCE / 'synthetic_fixture_manifest.json').write_text(
            json.dumps(fixture_info, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        diff_lines = []
        for rel in subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).split(b'\0'):
            if not rel:
                continue
            name = rel.decode('utf-8', 'surrogateescape')
            if not name.endswith('.py') or is_database_path(name):
                continue
            a, b = base_repo / name, cand_repo / name
            if a.exists() and b.exists():
                try:
                    aa, bb = a.read_text(encoding='utf-8'), b.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    continue
                if aa != bb:
                    diff_lines.extend(difflib.unified_diff(aa.splitlines(True), bb.splitlines(True),
                        fromfile=f'baseline/{name}', tofile=f'candidate/{name}'))
        (EVIDENCE / 'import_substitution.diff').write_text(''.join(diff_lines), encoding='utf-8')
        meta = {
            'experiment': 'stdlib sqlite3 vs pysqlite3 0.6.1 in isolated tracked-source copies',
            'historical_reference_not_reproduced': {'baseline': {'passed': 802, 'failed': 9, 'skipped': 18, 'subtests': 2},
                'candidate': {'passed': 797, 'failed': 14, 'skipped': 18, 'subtests': 2}},
            'current_source_commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
            'python': sys.version, 'test_python': subprocess.check_output([str(PYTHON), '-c', 'import sys;print(sys.version)'], text=True).strip(),
            'pytest_version': subprocess.check_output([str(PYTHON), '-c', 'import pytest;print(pytest.__version__)'], text=True).strip(),
            'baseline_sqlite': subprocess.check_output([str(PYTHON), '-c', 'import sqlite3;print(sqlite3.sqlite_version)'], text=True).strip(),
            'candidate_sqlite': subprocess.check_output([str(PYTHON), '-c', f'import sys;sys.path.insert(0,{str(PYSQ_TARGET)!r});import pysqlite3;print(pysqlite3.sqlite_version)'], text=True).strip(),
            'baseline_files_copied': base_n, 'candidate_files_copied': cand_n,
            'candidate_sqlite_import_substitutions': cand_subs, 'database_files_skipped': sorted(set(skipped_a + skipped_b)),
            'fixture': fixture_info,
            'pytest_uses': 'same Python executable and installed dependencies; only project-source sqlite3 import substitutions differ',
        }
        (EVIDENCE / 'run_manifest.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
        baseline = run_suite('baseline_stdlib', base_repo, base_out, False)
        (EVIDENCE / 'baseline_results.json').write_text(json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
        candidate = run_suite('candidate_pysqlite3_0.6.1', cand_repo, cand_out, True)
        (EVIDENCE / 'candidate_results.json').write_text(json.dumps(candidate, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
        a = set((baseline.get('junit') or {}).get('failure_ids', []))
        b = set((candidate.get('junit') or {}).get('failure_ids', []))
        comparison = {
            'baseline_failure_count': len(a), 'candidate_failure_count': len(b),
            'same_failure_ids': sorted(a & b), 'candidate_only_failure_ids': sorted(b - a),
            'baseline_only_failure_ids': sorted(a - b),
            'baseline_error_ids': (baseline.get('junit') or {}).get('error_ids', []),
            'candidate_error_ids': (candidate.get('junit') or {}).get('error_ids', []),
            'baseline_totals': (baseline.get('junit') or {}).get('totals'),
            'candidate_totals': (candidate.get('junit') or {}).get('totals'),
        }
        (EVIDENCE / 'comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True)+'\n', encoding='utf-8')
        print(json.dumps({'meta': meta, 'comparison': comparison, 'baseline_exit': baseline['exit_code'],
                          'candidate_exit': candidate['exit_code']}, ensure_ascii=False, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
