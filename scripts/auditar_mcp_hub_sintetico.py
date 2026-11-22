import asyncio,json,os,sys,tempfile,pathlib
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from scripts.evaluar_qa_intuicion_asociaciones_e1 import parse_tool_result
R=pathlib.Path.cwd(); evidence=R/'google_drive/auditoria_neuronas/mcp_hub_case.json'; assert not evidence.exists()
bridges=[{'text':'origen nectar','angle':'sinonimo'},{'text':'oscuro sendero','angle':'problema'},{'text':'velero distante','angle':'solucion'},{'text':'calendario urbano','angle':'situacion'},{'text':'semilla alborada','angle':'ingenuo'}]
async def main():
 events=[]
 with tempfile.TemporaryDirectory(prefix='biorag-hub-mcp-') as t:
  path=pathlib.Path(t);db=path/'sintetica.db'; assert not db.exists();env={k:v for k,v in os.environ.items() if not k.startswith('BIORAG_')};env.update({'BIORAG_PATH':str(db),'BIORAG_QA_TEMP_ROOT':str(path),'BIORAG_DMN_ESTADO_PATH':str(path/'dmn.json'),'BIORAG_NEURONA':'0','BIORAG_NO_LOG':'1','BIORAG_AUTOGUARDADO_HEURISTICO':'0','BIORAG_MCP_AUTO_PARAFRASIS':'0','BIORAG_MCP_AUTO_DIMS':'0','BIORAG_WORDNET_ENABLED':'0','BIORAG_PPMI_WEIGHT':'0','BIORAG_DMN_SINTESIS_ACTIVA':'0','BIORAG_HUB_MOTOR':'escala','BIORAG_HUB_ESCALA':'1','PYTHONHASHSEED':'0','NLTK_DATA':str(R/'MemoryBioRAG_Data/nltk_data')})
  params=StdioServerParameters(command=sys.executable,args=[str(R/'scripts/qa_stdio_server_intuicion.py')],env=env,cwd=str(R))
  async with stdio_client(params) as (read,write):
   async with ClientSession(read,write) as client:
    await client.initialize()
    async def call(name,args):
     result=await client.call_tool(name,arguments=args);raw,parsed=parse_tool_result(result); events.append({'tool':name,'args':args,'is_error':bool(result.isError),'parsed':parsed,'raw':raw});
     if result.isError or parsed.get('status') in ('error','mcp_error'): raise RuntimeError('MCP tool failure '+name)
     return parsed
    prior=await call('recordar',{'query':'nodo demo','sustantivos_clave':'nodo,demo','asociados':True,'asociaciones_max':0,'limite':10})
    if prior.get('resultados'): raise RuntimeError('synthetic fixture unexpectedly populated')
    learned=await call('aprender',{'concepto':'nodo_demo','contenido':'Una descripcion inventada sin vocabulario comun.','dimensiones':'{}','cat':'General','bridges':bridges,'sustantivos_clave':'nodo,demo','busqueda_previa':True})
    if learned.get('status')!='ok': raise RuntimeError('learning failed')
    consolidated=await call('consolidar',{})
    if consolidated.get('status')!='ok':raise RuntimeError('consolidation failed')
    hub=await call('concept_hub_buscar',{'query':'alborada'})
    one=await call('recordar',{'query':'alborada','sustantivos_clave':'alborada','asociados':True,'asociaciones_max':0,'limite':10,'deep':False})
    follow=await call('recordar',{'query':'semilla alborada','sustantivos_clave':'semilla,alborada','asociados':True,'asociaciones_max':0,'limite':10,'deep':False})
    print('hub_match',bool(hub.get('match')),'single_count',len(one.get('resultados',[])),'single_target',any(x.get('concepto')=='nodo_demo' for x in one.get('resultados',[])),'follow_count',len(follow.get('resultados',[])),'follow_target',any(x.get('concepto')=='nodo_demo' for x in follow.get('resultados',[])))
    print('channels_one',sorted(one.keys())); print('channels_follow',sorted(follow.keys())); print('events',len(events))
  evidence.write_text(json.dumps({'events':events},ensure_ascii=False,indent=2)+'\n');os.chmod(evidence,0o600)
asyncio.run(main())
