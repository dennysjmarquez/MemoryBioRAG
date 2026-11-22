"""Core de correcciones, siempre DB sintética o copia temporal."""
import concurrent.futures
import json
import sqlite3
import pytest
from core.contextual.service import Corrections
from core.contextual.search import reorder
from core.mcp_server.corrections import configured_service


@pytest.fixture(params=['DELETE','WAL'])
def sample(tmp_path,request):
    path=tmp_path/'memory.db';db=sqlite3.connect(path)
    db.execute('PRAGMA journal_mode='+request.param)
    db.executescript('''CREATE TABLE largo_plazo(concepto TEXT PRIMARY KEY,contenido TEXT);
      INSERT INTO largo_plazo VALUES ('old','contenido previo'),('new','contenido nuevo');
      CREATE TABLE sinapsis(origen TEXT,destino TEXT,tipo TEXT);
      INSERT INTO sinapsis VALUES ('new','old','manual');''');db.close()
    service=Corrections(path)
    yield path,service,request.param.lower()
    service.close()


def propose(s,**kw):
    params=dict(proposal_id='p',message='Corrijo: el puerto de servicio en prod es 8443, no 8080.',
                old_node='old',new_node='new',observed_at=3,effective_at=2,previous_from=1)
    params.update(kw)
    return s.register(**params)


def test_bootstrap_is_pending_then_atomic_and_searchable(sample):
    path,s,mode=sample
    before=s.db.execute('SELECT * FROM largo_plazo').fetchall()
    assert propose(s)['confirmed'] is False
    assert s.db.execute('SELECT count(*) FROM ctx_claims').fetchone()[0]==0
    review=s.review('p');assert review['evidence']['bootstrap_predecessor']
    receipt=s.confirm('p',review['digest'],'r')
    assert receipt==s.confirm('p',review['digest'],'r')
    assert propose(s)['status']=='approved'
    assert s.db.execute('PRAGMA journal_mode').fetchone()[0]==mode
    assert s.db.execute('SELECT * FROM largo_plazo').fetchall()==before
    assert s.db.execute('SELECT tipo FROM sinapsis').fetchall()==[('manual',)]
    assert s.db.execute('SELECT tipo FROM ctx_synapses').fetchall()==[('sustituye',)]
    rows=[('old','keep',1,None,.9),('new','keep',1,None,.2)]
    output,info=reorder(s.db,rows,dict(entity='servicio',attribute='puerto',scope='prod',at=3))
    assert info['status']=='resolved' and output==[rows[1],rows[0]]
    historical,status=reorder(s.db,rows,dict(entity='servicio',attribute='puerto',scope='prod',at=3,intent='historical'))
    assert historical==rows and status['status']=='passthrough'


def test_failures_rollback_every_table(sample):
    _,s,_=sample;propose(s);digest=s.review('p')['digest']
    for point in ('after_ledger','after_graph'):
        def fault(p):
            if p==point:raise RuntimeError('injected')
        with pytest.raises(RuntimeError):s.confirm('p',digest,'r',fault=fault)
        for table in ('ctx_claims','ctx_revisions','ctx_synapses','ctx_approvals'):
            assert s.db.execute('SELECT count(*) FROM '+table).fetchone()[0]==0


def test_stale_and_reused_identifiers(sample):
    _,s,_=sample;propose(s);digest=s.review('p')['digest']
    with pytest.raises(ValueError):propose(s,new_node='old')
    s.db.execute("UPDATE largo_plazo SET contenido='modified' WHERE concepto='new'");s.db.commit()
    with pytest.raises(ValueError,match='stale'):s.confirm('p',digest,'r')
    digest=s.review('p')['digest'];s.confirm('p',digest,'r')
    with pytest.raises(ValueError):s.confirm('p','other','r')
    with pytest.raises(ValueError):s.confirm('p',digest,'another')


def test_no_bootstrap_without_explicit_previous_time(sample):
    _,s,_=sample;propose(s,previous_from=None)
    with pytest.raises(ValueError,match='fecha previa'):s.confirm('p',s.review('p')['digest'],'r')
    assert s.db.execute('SELECT count(*) FROM ctx_claims').fetchone()[0]==0


def test_growth_10000_does_not_change_review_or_decision(sample):
    _,s,_=sample;propose(s);digest=s.review('p')['digest']
    s.db.executemany('INSERT INTO ctx_claims VALUES (?,?,?,?,?,?,?,?,?,?)',
       [(str(i),str(i),'entity'+str(i),'other','other','X','fixture',0,None,0) for i in range(10000)])
    s.db.commit();assert s.review('p')['digest']==digest
    s.confirm('p',digest,'r')


def test_concurrent_confirmation_exactly_once(sample):
    path,s,_=sample;propose(s);digest=s.review('p')['digest']
    def run(_):
        service=Corrections(path)
        try:return service.confirm('p',digest,'r')
        finally:service.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        receipts=list(pool.map(run,range(2)))
    assert receipts[0]==receipts[1]
    assert s.db.execute('SELECT count(*) FROM ctx_synapses').fetchone()[0]==1


def test_process_death_before_and_after_commit(sample):
    import os
    import subprocess
    import sys
    from pathlib import Path
    path,s,_=sample;propose(s);digest=s.review('p')['digest']
    script='''import os,sys
from core.contextual.service import Corrections
s=Corrections(sys.argv[1])
s.confirm('p',sys.argv[2],'r',fault=lambda p:os._exit(72) if p=='after_graph' else None)
'''
    env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result=subprocess.run([sys.executable,'-c',script,str(path),digest],env=env)
    assert result.returncode==72
    assert s.db.execute('SELECT count(*) FROM ctx_claims').fetchone()[0]==0
    assert s.db.execute('SELECT count(*) FROM ctx_synapses').fetchone()[0]==0
    script=script.replace(",fault=lambda p:os._exit(72) if p=='after_graph' else None",'')+'os._exit(73)\n'
    result=subprocess.run([sys.executable,'-c',script,str(path),digest],env=env)
    assert result.returncode==73
    assert s.confirm('p',digest,'r')['status']=='approved'
    assert s.db.execute('SELECT count(*) FROM ctx_synapses').fetchone()[0]==1


def test_permissions_default_off_and_no_sse(monkeypatch):
    monkeypatch.setenv('BIORAG_CORRECTIONS','0')
    with pytest.raises(PermissionError):configured_service(stdio=True)
    monkeypatch.setenv('BIORAG_CORRECTIONS','1')
    with pytest.raises(PermissionError):configured_service(stdio=False)



def test_real_mcp_schema_exposes_object_context_and_guarded_tools():
    from core.mcp_server.server import _build_server
    server=_build_server()
    tools={tool.name:tool for tool in server._tool_manager.list_tools()}
    assert {'registrar_correccion','revisar_correccion','confirmar_correccion'}<=tools.keys()
    for name in ('recordar','buscar'):
        schema=tools[name].parameters['properties']['contexto_vigencia']
        assert any(item.get('type')=='object' for item in schema['anyOf'])


def test_no_ddl_on_search_and_visible_invalid_context():
    db=sqlite3.connect(':memory:');rows=[('old','',1,None,.9)]
    before=db.total_changes
    output,status=reorder(db,rows,dict(entity='x',attribute='y',scope='z',at=3))
    assert output==rows and status['status']=='unknown'
    assert db.total_changes==before and db.execute('SELECT name FROM sqlite_master').fetchall()==[]
    output,status=reorder(db,rows,'invalid-json')
    assert output==rows and status['status']=='fallback_error'
    db.close()
