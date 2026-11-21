"""MCP stdio aislado. NO registrar en core/mcp_server ni apuntar a DB viva.
LAB_ROOT bajo /tmp con LAB_ONLY; LAB_PRINCIPAL y LAB_GRANTS son delegación
explícita del anfitrión local que lanza este proceso, no identidad remota.
"""
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import sys
from approval import Approval
from observation import Observer
from selector import Query
from search_adapter import wrap_search
from mcp.server.fastmcp import FastMCP

root = Path(os.environ['LAB_ROOT']).resolve()
principal = os.environ['LAB_PRINCIPAL']
grants = json.loads(os.environ['LAB_GRANTS'])
server = FastMCP('BioRAG contextual corrections — LAB ONLY')


def service():
    return Approval(root, principal, grants)


@server.tool()
def registrar_correccion(id: str, mensaje: str, observado_en: float, efectivo_desde: float) -> dict:
    """Registrar propuesta de acto directo. No aprobar ni escribir recuerdos."""
    s = service()
    db = sqlite3.connect(str(root/'observations.db'))
    try:
        observer = Observer(db)
        result = observer.observe(s.ledger, event_id=id, actor=principal, role='user',
                                  message=mensaje, observed_at=observado_en, effective_at=efectivo_desde)
        if result['status'] == 'pending_confirmation':
            s.register(observer, id)
            approved = s.db.execute('SELECT receipt FROM approvals WHERE proposal_id=?', (id,)).fetchone()
            if approved:
                return dict(result, status='approved_projected', confirmed=True,
                            approval=json.loads(approved[0]), lab_action='approved_projected')
        return result
    finally:
        db.close()
        s.close()


@server.tool()
def revisar_correccion(id: str, nodo_sucesor: str) -> dict:
    """Ver evidencia y digest para aprobar exactamente esta propuesta/nodo/contexto."""
    s = service()
    try:
        return s.review(id, nodo_sucesor)
    finally:
        s.close()


@server.tool()
def confirmar_correccion(id: str, nodo_sucesor: str, digest: str, request_id: str) -> dict:
    """Aprobar por delegación del host; atomicidad local ledger+grafo de ensayo."""
    s = service()
    try:
        return s.confirm(id, nodo_sucesor, digest, request_id)
    finally:
        s.close()


@server.tool()
def buscar_contextual(consulta: str, entidad: str, atributo: str, alcance: str,
                      instante: float, intencion: str = 'current') -> dict:
    """Búsqueda BioRAG real en copia con selector. Contexto explícito, no inferido."""
    code = Path(os.environ['LAB_CODE']).resolve()
    if not code.is_relative_to(Path('/tmp')) or (code/'.env.local').exists():
        raise ValueError('Requiere copia del código sin .env.local')
    sys.path.insert(0, str(code))
    from core.memory_store import SQLiteMemoryBioRAG
    s = service()
    brain = None
    try:
        brain = SQLiteMemoryBioRAG(str(root/'graph.db'))
        events = []
        query = Query(entidad, atributo, alcance, instante, intencion)
        search = wrap_search(brain.buscar_por_frase, s.ledger, lambda a, kw: query,
                             events.append, shadow=False)
        rows, total = search(consulta, profundidad='activos', limite=5)
        return dict(resultados=[dict(concepto=r[0],score=r[4]) for r in rows],
                    total=total,trace=events)
    finally:
        if brain is not None:
            brain.conn.close()
        s.close()


if __name__ == '__main__':
    # Validate confinement at startup, not just when the first tool runs.
    s = service()
    s.close()
    server.run(transport='stdio')
