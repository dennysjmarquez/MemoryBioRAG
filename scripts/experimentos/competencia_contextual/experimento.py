"""Benchmark controlado y replay del diagnóstico. No entrena ni importa el motor."""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import tempfile
from ledger import Claim, Ledger
from selector import Candidate, Query, select

ROOT = Path(__file__).resolve().parents[3]


def synthetic():
    db = sqlite3.connect(':memory:')
    ledger = Ledger(db)
    rng = random.Random(42)
    counts = dict(cases=0, before_current_at_1=0, after_current_at_1=0,
                  history_passthrough=0, identifier_passthrough=0,
                  conflicts_detected=0, neighbors_preserved=0)
    # Cinco dominios SOLO en el generador, nunca en selector/ledger.
    domains = ('release', 'configuration', 'decision', 'address', 'procedure')
    for domain in domains:
        for i in range(20):
            entity = f'{domain}:{i}'
            a, b = f'{entity}:a', f'{entity}:b'
            old = Claim(a, a, entity, 'value', 'scope', 'old-value', 'fixture:old', 1, confirmed=True)
            new = replace(old, id=b, node=b, value='new-value', source='fixture:correction', valid_from=2)
            ledger.add(old)
            ledger.add(new)
            ledger.supersede(b, a, 'fixture:explicit revision')
            q = Query(entity, 'value', 'scope', 3)
            candidates = (Candidate(a, rng.uniform(.8, 1)), Candidate(entity+':neighbor', .7),
                          Candidate(b, rng.uniform(.1, .6)))
            d = select(ledger, q, candidates)
            counts['cases'] += 1
            counts['before_current_at_1'] += candidates[0].node == b
            counts['after_current_at_1'] += d.winner == b and d.candidates[0].node == b
            counts['neighbors_preserved'] += set(d.candidates) == set(candidates)
            for intent, key in [('historical', 'history_passthrough'), ('identifier', 'identifier_passthrough')]:
                counts[key] += select(ledger, replace(q, intent=intent), candidates).candidates == candidates
            # Nueva afirmación confirmada incompatible, sin relación de sustitución.
            ledger.add(replace(new, id=entity+':c', node=entity+':c', value='unresolved'))
            counts['conflicts_detected'] += select(ledger, q, candidates).status == 'conflict'
    db.close()
    return counts


def replay(snapshot=None):
    fixture = json.loads((ROOT/'docs/diagnosticos/v36_2/resultados_resumidos.json').read_text())
    # Mapeo de CASO DE PRUEBA, no lógica del selector.
    current = 'version_actual_biorag'
    former = 'version_actual_biorag_v32_4_20261007'
    obsolete = 'ultima_version_biorag'
    snapshot_check = None
    if snapshot:
        source = Path(snapshot).resolve()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix='biorag-context-snapshot-') as temp:
            src = sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)
            dst = sqlite3.connect(str(Path(temp)/'copy.db'))
            try:
                src.backup(dst)
                check = dst.execute('PRAGMA quick_check').fetchone()[0]
                if check != 'ok':
                    raise ValueError('Snapshot no íntegro: '+check)
                found = dst.execute('''SELECT concepto FROM largo_plazo
                    WHERE concepto IN (?,?,?)''', (current, former, obsolete)).fetchall()
                if {r[0] for r in found} != {current, former, obsolete}:
                    raise ValueError('Snapshot no contiene los tres nodos del caso')
            finally:
                dst.close()
                src.close()
        unchanged = digest == hashlib.sha256(source.read_bytes()).hexdigest()
        if not unchanged:
            raise ValueError('El origen cambió durante la comprobación')
        if digest != fixture['baseline']['source_sha256']:
            raise ValueError('El replay no corresponde al hash de este snapshot')
        snapshot_check = dict(quick_check=check, sha256=digest, source_unchanged=unchanged)
    db = sqlite3.connect(':memory:')
    ledger = Ledger(db)
    for id_, value, since in [(former, '32.4', 1), (obsolete, '32.3', 1), (current, '36.1', 2)]:
        ledger.add(Claim(id_, id_, 'fixture-project', 'release', 'DEV', value,
                         'fixture:diagnostico revisado; no extracción automática', since, confirmed=True))
    ledger.supersede(current, former, 'fixture:actualización DEV confirmada para el ensayo')
    ledger.supersede(current, obsolete, 'fixture:obsoleto remite al canónico; ensayo explícito')
    q = Query('fixture-project', 'release', 'DEV', 3)
    results = {}
    for variant in ('baseline', 'dormido'):
        rows = tuple(Candidate(r['concepto'], r['score_hibrido'])
                     for r in fixture[variant]['calls'][0]['results'])
        d = select(ledger, q, rows)
        assert len(d.candidates) == len(rows) and set(d.candidates) == set(rows)
        assert d.winner == current
        results[variant] = dict(before=[asdict(r) for r in rows], after=asdict(d))
    db.close()
    return dict(mode='replay de ranking capturado; NO nuevo E2E',
                metadata='sustituciones añadidas explícitamente SOLO al ledger de prueba',
                snapshot=snapshot_check, variants=results)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = dict(synthetic=synthetic(), incident=replay(args.snapshot))
    data = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(data+'\n')
    print(data)


if __name__ == '__main__':
    main()
