"""E2e: diagnóstico parcial, NO reproduce ráfaga ni paráfrasis desconocidas."""
import json, os, sqlite3, sys, tempfile
from pathlib import Path

root = Path(os.environ['BIORAG_E2E_CODEROOT']).resolve()
source = Path(os.environ['BIORAG_E2E_DB']).resolve()
assert not Path(str(source) + '-wal').exists(), 'No se usa immutable con WAL existente'
sys.path.insert(0, str(root))
with tempfile.TemporaryDirectory(prefix='biorag_e2e_version_') as tmp:
    copy = Path(tmp) / 'copia.db'
    src = sqlite3.connect(source.as_uri() + '?mode=ro&immutable=1', uri=True)
    dst = sqlite3.connect(copy)
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()
    os.environ['BIORAG_PATH'] = str(copy)
    from core.mcp_server.search import _recordar_impl
    params = {
        'query': 'biorag version ultima orden nodos externos',
        'sustantivos_clave': 'biorag,version,nodos,orden',
        'limite': 5,
        'forzar_rafaga': False,
        'rafaga_palabras': None,
        'parafrasis': None,
    }
    raw = _recordar_impl(**params)
    start = raw.find('{')
    if start < 0:
        raise RuntimeError('MCP no devolvió un objeto JSON')
    data = json.loads(raw[start:])
    if data.get('status') == 'error':
        raise RuntimeError(data.get('mensaje', raw))
    rows = data.get('resultados', [])
    if not isinstance(rows, list):
        raise RuntimeError('MCP devolvió resultados no válidos')
    top = [{'concepto': r['concepto'], 'score_hibrido': r.get('score_hibrido')} for r in rows]
    expected = 'version_actual_biorag'
    concepts = [r['concepto'] for r in top]
    out = {
        'aviso': 'Diagnóstico parcial: faltan las 11 palabras de ráfaga y las 4 paráfrasis; NO es la llamada real.',
        'parametros': params,
        'metodo': '_recordar_impl (MCP); profundidad activos y límite 5; la interfaz MCP no expone ignore_peso_sinaptico',
        'puesto_version_actual': concepts.index(expected) + 1 if expected in concepts else None,
        'top5': top,
    }
    with open(sys.argv[1], 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2); f.write('\n')
    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
