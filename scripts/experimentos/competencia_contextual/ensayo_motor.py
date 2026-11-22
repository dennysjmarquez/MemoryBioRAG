"""Búsqueda MCP real + selector lateral sobre copias temporales; NO integración.

Uso: python ensayo_motor.py --snapshot BACKUP --code COPIA_CODIGO
     --corpus RUTA_NLTK --output RESULTADOS.json
Las relaciones del caso se siembran explícitamente, no se extraen del lenguaje.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from ledger import Claim, Ledger
from selector import Candidate, Query, select


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--snapshot', required=True, type=Path)
    p.add_argument('--code', required=True, type=Path)
    p.add_argument('--corpus', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    source, code, corpus, output = (x.resolve() for x in (args.snapshot, args.code, args.corpus, args.output))
    if not source.is_file() or not code.is_dir() or not corpus.is_dir():
        raise ValueError('Falta snapshot, código aislado o corpus')
    if (code/'.env.local').exists():
        raise ValueError('No importar configuración privada heredada')
    initial = hashlib.sha256(source.read_bytes()).hexdigest()
    if initial != '07a77c801eaa56750627e1c831de91a65e6448da25e4803b86d3ae4e2446c55e':
        raise ValueError('Este fixture requiere el snapshot diagnosticado')
    with tempfile.TemporaryDirectory(prefix='biorag-context-engine-') as temp:
        os.environ.update(HOME=temp, BIORAG_NLTK_AUTO_DOWNLOAD='0', BIORAG_NLTK_DATA=str(corpus),
                          BIORAG_UPDATE_CHECK='0', BIORAG_DMN_SINTESIS_ACTIVA='0')
        sys.path.insert(0, str(code))
        from core.memory_store import SQLiteMemoryBioRAG
        from core.memory import neurona
        from core.mcp_server import search as mcp
        report = dict(mode='handler MCP real + selector EXTERNO, metadatos de fixture explícitos',
                      source_sha256=initial, variants={})
        current = 'version_actual_biorag'
        former = 'version_actual_biorag_v32_4_20261007'
        obsolete = 'ultima_version_biorag'
        ledger_db = sqlite3.connect(':memory:')
        ledger = Ledger(ledger_db)
        for name, value, since in ((former, '32.4', 1), (obsolete, '32.3', 1), (current, '36.1', 2)):
            ledger.add(Claim(name, name, 'fixture-project', 'release', 'DEV', value,
                             'fixture:diagnóstico revisado', since, confirmed=True))
        for old in (former, obsolete):
            ledger.supersede(current, old, 'fixture:revisión confirmada para ensayo')
        for variant in ('activo', 'dormido'):
            path = Path(temp)/(variant+'.db')
            src = sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)
            dst = sqlite3.connect(str(path))
            src.backup(dst)
            src.close()
            dst.close()
            b = SQLiteMemoryBioRAG(str(path))
            b._persistente = True
            if variant == 'dormido':
                b.cursor.execute("UPDATE largo_plazo SET estado='dormido',peso_sinaptico=0.05 WHERE concepto=?", (obsolete,))
                b.conn.commit()
            mcp._get_cerebro = lambda: b
            champ = neurona.estado(b)
            raw = mcp._recordar_impl(query='ultima version biorag', sustantivos_clave='ultima,version,biorag',
                    parafrasis='cual es la ultima version de biorag,ultimo release publicado', limite=5, asociados=True)
            start = raw.rfind('\n\n{')
            data = json.loads(raw[start+2:] if start >= 0 else raw)
            rows = tuple(Candidate(r['concepto'], r['score_hibrido']) for r in data['resultados'])
            before_changes = ledger_db.total_changes
            decision = select(ledger, Query('fixture-project', 'release', 'DEV', 3), rows)
            assert decision.winner == current
            assert len(decision.candidates) == len(rows) and set(decision.candidates) == set(rows)
            assert ledger_db.total_changes == before_changes
            report['variants'][variant] = dict(before=[asdict(r) for r in rows], after=asdict(decision),
                    fingerprint=neurona.huella_motor(b), champion=champ.campeon is not None,
                    candidates_preserved=True, ledger_read_only=True)
            b.conn.close()
        ledger_db.close()
    report['source_unchanged'] = initial == hashlib.sha256(source.read_bytes()).hexdigest()
    assert report['source_unchanged']
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
