"""E2E del servidor MCP PRODUCTIVO del código aislado, no lab_mcp.

No siembra claims: bootstrap propuesto/revisado/aprobado por las tools reales.
Interacción sintética y snapshot suministrado explícitos; nunca DB viva.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(args):
    code=args.code.resolve();source=args.snapshot.resolve()
    if not code.is_relative_to(Path('/tmp')) or (code/'.env.local').exists() or (code/'.env').exists():
        raise ValueError('Requiere copia de código limpia bajo /tmp')
    initial=hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='core362-e2e-') as temp:
        root=Path(temp);dbpath=root/'copy.db'
        src=sqlite3.connect(source.as_uri()+'?mode=ro&immutable=1',uri=True)
        db=sqlite3.connect(dbpath);src.backup(db);src.close()
        old='version_actual_biorag_v32_4_20261007';new='version_actual_biorag'
        before_node=db.execute('SELECT * FROM largo_plazo WHERE concepto=?',(old,)).fetchone()
        manual=db.execute('SELECT * FROM sinapsis WHERE origen=? AND destino=?',(new,old)).fetchall()
        assert before_node is not None
        db.close()
        env=dict(os.environ,HOME=str(root/'home'),BIORAG_PATH=str(dbpath),
            BIORAG_CORRECTIONS='1',
            BIORAG_DAEMON_ENABLED='0',BIORAG_UPDATE_CHECK='0',BIORAG_DMN_SINTESIS_ACTIVA='0',
            BIORAG_NLTK_AUTO_DOWNLOAD='0',BIORAG_NLTK_DATA=str(args.corpus.resolve()),
            PYTHONHASHSEED='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
        (root/'home').mkdir()
        parameters=StdioServerParameters(command=sys.executable,args=[str(code/'mcp_server.py')],env=env,cwd=str(code))
        async with stdio_client(parameters) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize();tools=await session.list_tools()
                async def call(name,params):
                    result=await session.call_tool(name,params)
                    if result.isError:raise RuntimeError(str(result.content))
                    structured=result.structuredContent
                    if structured is not None and not (set(structured)=={'result'} and isinstance(structured['result'],str)):
                        return structured
                    raw=structured['result'] if structured is not None else result.content[0].text
                    start=raw.rfind('\n\n{')
                    return json.loads(raw[start+2:] if start>=0 else raw)
                query=dict(query='ultima version biorag',sustantivos_clave='ultima,version,biorag',limite=5)
                before=await call('recordar',query)
                db=sqlite3.connect(dbpath)
                before_node=db.execute('SELECT * FROM largo_plazo WHERE concepto=?',(old,)).fetchone()
                manual=db.execute('SELECT * FROM sinapsis WHERE origen=? AND destino=?',(new,old)).fetchall()
                db.close()
                proposal=await call('registrar_correccion',dict(id='core-e2e',
                    mensaje='Actualizo: la versión del proyecto en DEV pasa de 32.4 a 36.1.',
                    nodo_anterior=old,nodo_sucesor=new,observado_en=3,efectivo_desde=2,anterior_desde=1))
                assert proposal['confirmed'] is False
                db=sqlite3.connect(dbpath)
                assert db.execute('SELECT count(*) FROM ctx_claims').fetchone()[0]==0
                db.close()
                review=await call('revisar_correccion',dict(id='core-e2e'))
                assert review['evidence']['bootstrap_predecessor']
                invalid=await session.call_tool('confirmar_correccion',dict(id='core-e2e',digest='invalid',request_id='r'))
                assert invalid.isError
                params=dict(id='core-e2e',digest=review['digest'],request_id='r')
                receipt=await call('confirmar_correccion',params)
                assert await call('confirmar_correccion',params)==receipt
                db=sqlite3.connect(dbpath)
                after_node=db.execute('SELECT * FROM largo_plazo WHERE concepto=?',(old,)).fetchone()
                edges=db.execute('SELECT origen,destino,tipo,scope FROM ctx_synapses').fetchall()
                assert db.execute('SELECT * FROM sinapsis WHERE origen=? AND destino=?',(new,old)).fetchall()==manual
                db.close()
                unchanged=await call('recordar',query)
                context=dict(entity='proyecto',attribute='versión',scope='dev',at=3,intent='current')
                after=await call('recordar',dict(query,contexto_vigencia=context))
                historical=await call('recordar',dict(query,contexto_vigencia=dict(context,intent='historical')))
        if 'competencia_contextual' not in after:
            raise RuntimeError('Respuesta sin decisión contextual: '+json.dumps(after,ensure_ascii=False))
        assert after['competencia_contextual']['status']=='resolved'
        assert after['resultados'][0]['concepto']==new
        projection=lambda data:sorted((r['concepto'],r['score_hibrido']) for r in data['resultados'])
        assert projection(unchanged)==projection(after)
        assert [r['concepto'] for r in unchanged['resultados']]==[r['concepto'] for r in historical['resultados']]
        assert old in [r['concepto'] for r in after['resultados']]
        report=dict(server='core/mcp_server via mcp_server.py',version=(code/'VERSION').read_text().strip(),
            tools=[t.name for t in tools.tools],synthetic_interaction=True,manually_seeded_claims=False,
            proposal=proposal,receipt=receipt,bootstrap_explicitly_reviewed=True,invalid_digest_rejected=True,
            idempotent_receipt=True,old_row_unchanged_by_approval=(before_node==after_node),
            manual_edge_preserved=True,typed_edges=edges,
            before=[dict(node=r['concepto'],score=r['score_hibrido']) for r in before['resultados']],
            after=[dict(node=r['concepto'],score=r['score_hibrido']) for r in after['resultados']],
            contextual_decision=after['competencia_contextual'],candidates_and_scores_preserved=True,
            historical_order_preserved=True,source_sha256=initial,
            source_unchanged=initial==hashlib.sha256(source.read_bytes()).hexdigest())
        assert report['source_unchanged'] and report['old_row_unchanged_by_approval']
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for arg in ('code','snapshot','corpus','output'):parser.add_argument('--'+arg,type=Path,required=True)
    asyncio.run(run(parser.parse_args()))
