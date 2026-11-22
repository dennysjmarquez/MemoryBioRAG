"""Contrato experimental: ninguna prueba abre DB viva ni modifica casos QA."""
import json
import sqlite3
import pytest
from core.contextual.perspective import apply, validate, PerspectiveError, MODES
from core.contextual.service import Corrections


@pytest.mark.parametrize('context',[None,{},'auto',{'intent':'current'},{'mode':'auto'},{'mode':'vigente'},{'mode':'recientes'},{'mode':'relevancia','at':1}])
def test_invalid_contract(context):
    with pytest.raises(PerspectiveError):validate(context)


@pytest.mark.parametrize('mode',MODES)
def test_explicit_modes(mode):
    context={'mode':mode}
    if mode in ('recientes','antiguos'):context['time_basis']='registro'
    if mode in ('vigente','historico','ambos'):context.update(entity='servicio',attribute='puerto',scope='prod',at=3)
    assert validate(context)==context


@pytest.fixture(params=['WAL','DELETE'])
def memory(tmp_path,request):
    path=tmp_path/'copy.db';db=sqlite3.connect(path)
    db.execute('PRAGMA journal_mode='+request.param)
    db.executescript('''CREATE TABLE largo_plazo(concepto TEXT PRIMARY KEY,contenido TEXT,creado_en REAL);
      INSERT INTO largo_plazo VALUES ('old','8080',30),('new','8443',10),('other','otro',0);''')
    db.close();s=Corrections(path)
    rows=[('old','8080',0,None,.99),('other','otro',0,None,.8),('new','8443',0,None,.6)]
    yield s,rows
    s.close()


def ctx(mode):return dict(mode=mode,entity='servicio',attribute='puerto',scope='prod',at=3)


def approve(s):
    s.register('p','Corrijo: el puerto de servicio en prod es 8443, no 8080.','old','new',3,2,1)
    s.confirm('p',s.review('p')['digest'],'r')


def test_no_evidence_never_claims_current(memory):
    s,rows=memory
    for mode,code in [('vigente','VIGENCIA_NO_RESUELTA'),('ambos','VIGENCIA_NO_RESUELTA'),('historico','HISTORIA_NO_RESUELTA')]:
        result,info=apply(s.db,rows,ctx(mode))
        assert result==rows and info['status']==code and info['winner'] is None


def test_registered_time_is_not_validity(memory):
    s,rows=memory;approve(s)
    recent,info=apply(s.db,rows,dict(mode='recientes',time_basis='registro'))
    assert recent[0][0]=='old' and info['unknown_dates']==['other']
    oldest,_=apply(s.db,rows,dict(mode='antiguos',time_basis='registro'))
    assert oldest[0][0]=='new'
    current,info=apply(s.db,rows,ctx('vigente'))
    assert current[0][0]=='new' and info['winner']=='new'
    historical,info=apply(s.db,current,ctx('historico'))
    assert historical[0][0]=='old' and info['groups']['old']=='historico'
    both,info=apply(s.db,rows,ctx('ambos'))
    assert [r[0] for r in both]==['new','old','other']
    assert sorted(both)==sorted(rows)
    unchanged,_=apply(s.db,rows,dict(mode='relevancia'))
    assert unchanged==rows


def test_asof_gap_wrong_scope_and_no_write(memory):
    s,rows=memory;approve(s);changes=s.db.total_changes
    assert apply(s.db,rows,dict(ctx('vigente'),at=1))[1]['winner']=='old'
    assert apply(s.db,rows,dict(ctx('vigente'),scope='otro'))[1]['status']=='VIGENCIA_NO_RESUELTA'
    assert apply(s.db,rows[:1],ctx('vigente'))[1]['reason']=='retrieval_gap'
    assert s.db.total_changes==changes


def test_mcp_rejects_omission_before_opening_db(monkeypatch):
    from core.mcp_server import search
    monkeypatch.setenv('BIORAG_TEMPORAL_PROTOTYPE','1')
    def forbidden():raise AssertionError('DB no debe abrirse')
    monkeypatch.setattr(search,'_get_cerebro',forbidden)
    for context in (None,{},dict(mode='vigente')):
        output=json.loads(search._recordar_impl(query='ultima version biorag',sustantivos_clave='version,biorag',contexto_vigencia=context))
        assert output['error'] in ('CONTEXTO_VIGENCIA_REQUERIDO','CONTEXTO_REQUERIDO')


def test_default_enabled_without_principal_or_grants(monkeypatch, tmp_path):
    from core.mcp_server import corrections
    path=tmp_path/'copy.db';db=sqlite3.connect(path)
    db.execute('CREATE TABLE largo_plazo(concepto TEXT,contenido TEXT)');db.close()
    for key in ('BIORAG_CORRECTIONS','BIORAG_CORRECTIONS_PRINCIPAL','BIORAG_CORRECTIONS_GRANTS'):
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(corrections,'resolve_db_path',lambda:path)
    service=corrections.configured_service(stdio=True)
    assert service.principal=='local-mcp'
    service.close()
    with pytest.raises(PermissionError):corrections.configured_service(stdio=False)


@pytest.mark.parametrize('message',[
    'Corrijo: el puerto de servicio en prod es 8443, no 8080.',
    'Corrijo: la bebida de persona en desayuno es té, no café.',
    'Corrijo: la ruta de archivo en equipo es nueva, no antigua.',
])
def test_corrections_are_not_restricted_to_versions(memory,message):
    service,rows=memory
    result=service.register('general',message,'old','new',3,2,1)
    assert result['confirmed'] is False
    review=service.review('general')
    receipt=service.confirm('general',review['digest'],'general-request')
    assert receipt['status']=='approved'
    fields=review['evidence']['payload']['fields']
    context=dict(mode='vigente',at=3,**{key:fields[key] for key in ('entity','attribute','scope')})
    assert apply(service.db,rows,context)[1]['winner']=='new'


def test_previous_receipt_replays_without_old_identity_configuration(memory):
    service,_=memory;approve(service)
    request,receipt=service.db.execute('SELECT request,receipt FROM ctx_approvals').fetchone()
    request=json.loads(request);request[2]='old-configured-agent'
    service.db.execute('UPDATE ctx_approvals SET request=?',(json.dumps(request),));service.db.commit()
    assert service.confirm('p',request[1],'r')==json.loads(receipt)


def test_default_off_and_explicit_one_description(monkeypatch):
    from core.mcp_server import search
    from core.mcp_server.server import _build_server
    monkeypatch.delenv('BIORAG_TEMPORAL_PROTOTYPE',raising=False)

    # Without configuration, omission must not be rejected by the prototype gate.
    def reached_database(): raise AssertionError('La búsqueda llegó al acceso de DB')
    monkeypatch.setattr(search,'_get_cerebro',reached_database)
    with pytest.raises(AssertionError,match='llegó al acceso de DB'):
        search._recordar_impl(query='recuerdos',sustantivos_clave='recuerdos')

    tools={tool.name:tool for tool in _build_server()._tool_manager.list_tools()}
    for name in ('recordar','buscar'):
        description=tools[name].parameters['properties']['contexto_vigencia']['description']
        assert 'desactivado por defecto' in description
        assert 'BIORAG_TEMPORAL_PROTOTYPE=1' in description

    for flag,expected in [('0',False),('1',True)]:
        monkeypatch.setenv('BIORAG_TEMPORAL_PROTOTYPE',flag)
        tools={tool.name:tool for tool in _build_server()._tool_manager.list_tools()}
        for name in ('recordar','buscar'):
            description=tools[name].parameters['properties']['contexto_vigencia']['description']
            assert ('Sin elección:' in description)==expected
