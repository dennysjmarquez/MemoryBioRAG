"""E2E real stdio sobre DB sintética; no usa parser de correcciones ni claims SQL."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(code, corpus, output):
    code=code.resolve()
    if not code.is_relative_to(Path('/tmp')) or (code/'.env.local').exists():
        raise ValueError('Usar código aislado sin configuración privada bajo /tmp')
    with tempfile.TemporaryDirectory(prefix='biorag-structured-mcp-') as directory:
        root=Path(directory);database=root/'synthetic.db'
        env=dict(os.environ,HOME=str(root),BIORAG_PATH=str(database),BIORAG_CORRECTIONS='1',
                 BIORAG_TEMPORAL_PROTOTYPE='1',BIORAG_DAEMON_ENABLED='0',BIORAG_UPDATE_CHECK='0',
                 BIORAG_NLTK_AUTO_DOWNLOAD='0',BIORAG_NLTK_DATA=str(corpus.resolve()),
                 BIORAG_DMN_SINTESIS_ACTIVA='0',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
        env.pop('BIORAG_MAINTENANCE_TOKEN',None)
        seed='''from core.memory_store import SQLiteMemoryBioRAG
m=SQLiteMemoryBioRAG()
m.conn.executemany("INSERT INTO largo_plazo(concepto,contenido,sustantivos_clave,creado_en) VALUES (?,?,?,?)",[
('puerto_servicio_antiguo','El servicio usa el puerto 8080','servicio,puerto',10),
('puerto_servicio_actual','El servicio usa el puerto 8443','servicio,puerto',20)])
m.conn.commit();m.conn.close()
'''
        subprocess.run([sys.executable,'-c',seed],cwd=code,env=env,check=True,capture_output=True,text=True)
        params=StdioServerParameters(command=sys.executable,args=[str(code/'mcp_server.py')],cwd=str(code),env=env)
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                async def call(name,arguments):
                    result=await session.call_tool(name,arguments)
                    if result.isError:raise RuntimeError(str(result.content))
                    data=result.structuredContent
                    if isinstance(data,dict) and not (set(data)=={'result'} and isinstance(data['result'],str)):
                        return data
                    raw=data['result'] if data is not None else result.content[0].text
                    decoder=json.JSONDecoder()
                    for index,char in enumerate(raw):
                        if char=='{':
                            try:return decoder.raw_decode(raw[index:])[0]
                            except ValueError:pass
                    raise ValueError('Respuesta sin JSON')
                query=dict(query='puerto servicio',sustantivos_clave='puerto,servicio',limite=10,asociados=False)
                missing=await call('recordar',query)
                assert missing['codigo']=='CONTEXTO_VIGENCIA_REQUERIDO'
                context=dict(entity='service-ID',attribute='port-ID',scope='prod-ID',at=3)
                unresolved=await call('recordar',dict(query,contexto_vigencia=dict(context,mode='vigente')))
                assert unresolved['competencia_contextual']['status']=='VIGENCIA_NO_RESUELTA'
                registered=await call('registrar_correccion',dict(id='structured-e2e',mensaje='設定を変更しました。',
                    nodo_anterior='puerto_servicio_antiguo',nodo_sucesor='puerto_servicio_actual',observado_en=3,
                    efectivo_desde=2,anterior_desde=1,contexto={k:context[k] for k in ('entity','attribute','scope')},
                    valor_anterior='8080',valor_nuevo='8443'))
                assert registered['confirmed'] is False
                reviewed=await call('revisar_correccion',dict(id='structured-e2e'))
                assert reviewed['evidence']['payload']['spans'] is None
                approval=dict(id='structured-e2e',digest=reviewed['digest'],request_id='structured-r')
                receipt=await call('confirmar_correccion',approval)
                assert await call('confirmar_correccion',approval)==receipt
                modes={}
                for mode in ('relevancia','recientes','antiguos','vigente','historico','ambos'):
                    selected=dict(mode=mode)
                    if mode in ('recientes','antiguos'):selected['time_basis']='registro'
                    if mode in ('vigente','historico','ambos'):selected.update(context)
                    response=await call('recordar',dict(query,contexto_vigencia=selected))
                    nodes=[row['concepto'] for row in response['resultados']]
                    assert {'puerto_servicio_antiguo','puerto_servicio_actual'}<=set(nodes)
                    if mode=='vigente':assert nodes[0]=='puerto_servicio_actual'
                    if mode=='historico':assert nodes[0]=='puerto_servicio_antiguo'
                    modes[mode]=dict(nodes=nodes,decision=response['competencia_contextual'])
        report=dict(status='ok',transport='real MCP stdio',synthetic_database=True,
                    claims_seeded_by_sql=False,language_parser_required=False,
                    missing_mode_rejected=True,no_evidence_unresolved=True,idempotent_confirmation=True,
                    receipt=receipt,modes=modes)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for field in ('code','corpus','output'):parser.add_argument('--'+field,required=True,type=Path)
    args=parser.parse_args();asyncio.run(run(args.code,args.corpus,args.output))
