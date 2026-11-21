"""Cliente MCP stdio real contra servidor separado + motor BioRAG en copia.
Mensajes y antecedentes son fixtures explícitos. No autenticación humana remota.
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
from approval import Approval
from ledger import Claim
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(args):
    source=args.snapshot.resolve()
    initial=hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='biorag-approval-e2e-') as temp:
        root=Path(temp); (root/'LAB_ONLY').touch()
        src=sqlite3.connect(source.as_uri()+'?mode=ro&immutable=1',uri=True)
        graph=sqlite3.connect(str(root/'graph.db')); src.backup(graph);src.close()
        old='version_actual_biorag_v32_4_20261007'; new='version_actual_biorag'
        before_node=graph.execute('SELECT * FROM largo_plazo WHERE concepto=?',(old,)).fetchone()
        if before_node is None:
            raise ValueError('Fixture ausente')
        old_content=graph.execute('SELECT contenido FROM largo_plazo WHERE concepto=?',(old,)).fetchone()
        manual_before=graph.execute('SELECT * FROM sinapsis WHERE origen=? AND destino=?',(new,old)).fetchall()
        graph.close()
        service=Approval(root,'fixture-owner',[('proyecto','versión','dev')])
        service.ledger.add(Claim('release-before',old,'proyecto','versión','dev','32.4',
                                 'fixture:antecedente confirmado',1,confirmed=True))
        service.close()
        env=dict(os.environ,LAB_ROOT=str(root),LAB_PRINCIPAL='fixture-owner',
                 LAB_GRANTS=json.dumps([['proyecto','versión','dev']]),LAB_CODE=str(args.code.resolve()),
                 HOME=str(root/'home'),BIORAG_NLTK_AUTO_DOWNLOAD='0',BIORAG_UPDATE_CHECK='0',
                 BIORAG_DMN_SINTESIS_ACTIVA='0',BIORAG_NLTK_DATA=str(args.corpus.resolve()),PYTHONHASHSEED='1')
        (root/'home').mkdir()
        parameters=StdioServerParameters(command=sys.executable,
            args=[str(Path(__file__).with_name('lab_mcp.py').resolve())],env=env)
        async with stdio_client(parameters) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                tools=await session.list_tools()
                async def call(name,params):
                    result=await session.call_tool(name,params)
                    if result.isError:
                        raise RuntimeError(str(result.content))
                    if result.structuredContent is not None:
                        return result.structuredContent
                    return json.loads(result.content[0].text)
                query=dict(consulta='ultima version biorag',entidad='proyecto',atributo='versión',alcance='dev',instante=3)
                before=await call('buscar_contextual',query)
                proposal=await call('registrar_correccion',dict(id='e2e-1',
                    mensaje='Actualizo: la versión del proyecto en DEV pasa de 32.4 a 36.1.',
                    observado_en=3,efectivo_desde=2))
                review=await call('revisar_correccion',dict(id='e2e-1',nodo_sucesor=new))
                params=dict(id='e2e-1',nodo_sucesor=new,digest=review['digest'],request_id='e2e-confirm-1')
                denied=await session.call_tool('confirmar_correccion',dict(params,digest='stale-digest'))
                assert denied.isError, 'El MCP debe rechazar digest inválido'
                receipt=await call('confirmar_correccion',params)
                repeated=await call('confirmar_correccion',params)
                reregister=await call('registrar_correccion',dict(id='e2e-1',
                    mensaje='Actualizo: la versión del proyecto en DEV pasa de 32.4 a 36.1.',
                    observado_en=3,efectivo_desde=2))
                assert reregister['status']=='approved_projected' and reregister['confirmed']
                assert reregister['approval']==receipt
                graph=sqlite3.connect(str(root/'graph.db'))
                # Compare immediately after approval, before the next search can reinforce nodes.
                after_node=graph.execute('SELECT * FROM largo_plazo WHERE concepto=?',(old,)).fetchone()
                content_now=graph.execute('SELECT contenido FROM largo_plazo WHERE concepto=?',(old,)).fetchone()
                edges=graph.execute('SELECT origen,destino,tipo,scope FROM sinapsis_sustitucion').fetchall()
                manual_after=graph.execute('SELECT * FROM sinapsis WHERE origen=? AND destino=?',(new,old)).fetchall()
                graph.close()
                after=await call('buscar_contextual',query)
        trace=after['trace'][0]
        assert proposal['status']=='pending_confirmation'
        assert receipt==repeated
        assert edges==[(new,old,'sustituye','dev')]
        assert manual_before==manual_after
        assert old_content==content_now
        assert trace['status']=='resolved' and trace['proposed_winner']==new
        assert after['resultados'][0]['concepto']==new
        assert sorted(trace['before'])==sorted(trace['after'])
        assert old in [r['concepto'] for r in after['resultados']]
        # Engine searches may reinforce state; this does not imply approval altered old row.
        report=dict(mode='real MCP stdio + real engine on supplied snapshot copy',
            seeded_predecessor=True,synthetic_message=True,context_explicit=True,
            tools=[t.name for t in tools.tools],proposal_status=proposal['status'],receipt=receipt,
            before=before,after=after,typed_edges=edges,legacy_edge_preserved=True,
            old_content_preserved=True,old_row_equal_to_pre_search=(before_node==after_node),
            idempotent_receipt=True,reregister_reports_approved=True,
            stale_digest_rejected_by_mcp=True,candidates_and_scores_preserved=True,
            source_sha256=initial,source_unchanged=initial==hashlib.sha256(source.read_bytes()).hexdigest())
        assert report['source_unchanged']
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--snapshot',required=True,type=Path)
    parser.add_argument('--code',required=True,type=Path)
    parser.add_argument('--corpus',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    asyncio.run(run(parser.parse_args()))
