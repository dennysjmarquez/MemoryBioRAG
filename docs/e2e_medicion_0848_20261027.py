"""E2e: mismas búsquedas 0848 del examen, en copias independientes."""
import json, os, sqlite3, sys, tempfile
from pathlib import Path

ROOT = Path(os.environ['BIORAG_E2E_CODEROOT']).resolve()
sys.path.insert(0, str(ROOT))
from core.memory_store import SQLiteMemoryBioRAG

EXPECTED = 'v13_2_limpieza_tabla_semantica'
BASES = {
    'snapshot': ROOT / 'snapshots/qa_escape_qcr_20260811.db',
    'viva': Path('/tmp/viva_e2c.db'),
}
QUERIES = {
    '0848_sin_ruido': 'semánticas 849 embedding',
    '0848_con_zzqx': 'semánticas 849 embedding zzqx',
}
result = {}
for name, source in BASES.items():
    assert not Path(str(source) + '-wal').exists(), 'No se usa immutable con WAL existente'
    result[name] = {}
    for variant, query in QUERIES.items():
        result[name][variant] = {}
        for limit in (5, 50):
            with tempfile.TemporaryDirectory(prefix='biorag_e2e_0848_') as tmp:
                copy = Path(tmp) / 'copia.db'
                src = sqlite3.connect(source.as_uri() + '?mode=ro&immutable=1', uri=True)
                dst = sqlite3.connect(copy)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
                    src.close()
                db = SQLiteMemoryBioRAG(db_path=str(copy))
                state = db.conn.execute('SELECT estado FROM largo_plazo WHERE concepto=?', (EXPECTED,)).fetchone()
                if state is None:
                    raise RuntimeError(f'{name}: esperado no existe')
                db.conn.execute("UPDATE largo_plazo SET estado='activo' WHERE concepto=?", (EXPECTED,))
                db.conn.commit()
                rows, total = db.buscar_por_frase(query, profundidad='activos', limite=limit, ignore_peso_sinaptico=True)
                concepts = [r[0] for r in rows]
                pos = concepts.index(EXPECTED) + 1 if EXPECTED in concepts else None
                score = next((r[4] for r in rows if r[0] == EXPECTED), None)
                result[name][variant][str(limit)] = {
                    'consulta': query, 'limite': limit, 'estado_original': state[0], 'puesto': pos, 'score': score,
                    'candidatos': total, 'top5': [[r[0], r[4]] for r in rows[:5]],
                }
                print(f'{name:8} {variant:17} limite={limit:2} puesto={str(pos):>4} score={str(score):>6} candidatos={total}', flush=True)
                db.conn.close()
path = sys.argv[1]
with open(path, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(f'Guardado: {path}', flush=True)
