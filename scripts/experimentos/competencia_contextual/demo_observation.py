"""Primera interacción reproducible en sombra. Todos los mensajes son fixtures.
No consulta un agente externo ni interpreta libremente una conversación completa.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from ledger import Claim, Ledger
from observation import Observer
from selector import Candidate, Query


def scenario(message, old, new_node, candidates):
    ledger_db = sqlite3.connect(':memory:')
    event_db = sqlite3.connect(':memory:')
    try:
        ledger = Ledger(ledger_db)
        ledger.add(old)  # Antecedente confirmado de fixture, NO extraído de la DB.
        observer = Observer(event_db)
        before = '\n'.join(ledger_db.iterdump())
        proposal = observer.observe(ledger, event_id='demo-correction-1', actor='fixture-user',
            role='user', message=message, observed_at=3, effective_at=2)
        query = Query(old.entity, old.attribute, old.scope, 3)
        decision = observer.simulate(ledger, 'demo-correction-1', new_node=new_node,
                                     query=query, candidates=candidates)
        assert proposal['status'] == 'pending_confirmation'
        assert decision['would_if_confirmed']['winner'] == new_node
        assert '\n'.join(ledger_db.iterdump()) == before
        return dict(message=message, simulated_message=True, observed_at=3, effective_at=2,
                    proposal=proposal, observation=decision, ledger_unchanged=True,
                    production_ranking_unchanged=True,
                    production_candidates=[asdict(c) for c in candidates])
    finally:
        ledger_db.close()
        event_db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = dict(mode='observation_only', effective_time='instantes lógicos de fixture, no fechas inferidas')
    report['configuration'] = scenario(
        'Corrijo: el puerto del servicio alfa en producción es 8443, no 8080.',
        Claim('port-before', 'port-old', 'servicio alfa', 'puerto', 'producción', '8080',
              'fixture:antecedente confirmado', 1, confirmed=True),
        'port-new', (Candidate('port-old', .99), Candidate('neighbor', .8), Candidate('port-new', .2)))
    if args.snapshot:
        source = args.snapshot.resolve()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != '07a77c801eaa56750627e1c831de91a65e6448da25e4803b86d3ae4e2446c55e':
            raise ValueError('El snapshot no corresponde al fixture diagnosticado')
        with tempfile.TemporaryDirectory(prefix='biorag-interaction-copy-') as temp:
            src = sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)
            dst = sqlite3.connect(str(Path(temp)/'copy.db'))
            try:
                src.backup(dst)
                assert dst.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
                names = ('version_actual_biorag', 'version_actual_biorag_v32_4_20261007')
                count = dst.execute('SELECT count(*) FROM largo_plazo WHERE concepto IN (?,?)', names).fetchone()[0]
                if count != 2:
                    raise ValueError('Faltan nodos del fixture')
                before = dst.total_changes
                fixture = json.loads((Path(__file__).parent/'resultados_motor.json').read_text())
                rows = tuple(Candidate(**r) for r in fixture['variants']['dormido']['before'])
                report['snapshot_case'] = scenario(
                    'Actualizo: la versión del proyecto en DEV pasa de 32.4 a 36.1.',
                    Claim('release-before', names[1], 'proyecto', 'versión', 'dev', '32.4',
                          'fixture:antecedente explícito del caso auditado', 1, confirmed=True), names[0], rows)
                assert dst.total_changes == before
            finally:
                dst.close()
                src.close()
        report['source_sha256'] = digest
        report['source_unchanged'] = digest == hashlib.sha256(source.read_bytes()).hexdigest()
        assert report['source_unchanged']
        report['snapshot_mode'] = 'backup verificado; candidatos de traza previa, NO búsqueda nueva'
    data = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
    if args.output:
        args.output.write_text(data)
    print(data)


if __name__ == '__main__':
    main()
