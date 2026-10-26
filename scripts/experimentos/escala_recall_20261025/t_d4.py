import sys; sys.path.insert(0,'/home/user/MemoryBioRAG/tests')
import test_qcr_typo_d4 as T, core.memory.constants as constants, pytest
def test_ver(tmp_path, monkeypatch):
    monkeypatch.setenv("BIORAG_ESCALA","1")
    for piso_a in (0.9,0.20):
        c=T._db(tmp_path,f"x{piso_a}.db")
        T._score_por_concepto(monkeypatch,{"a_topico_qcr":piso_a,"c_topico_qcr":0.8,"d_topico_qcr":0.9})
        for on in (False,True):
            monkeypatch.setattr(constants,"QCR_TYPO_ACTIVA",on)
            res,_=c.buscar_por_frase(T.QUERY,limite=5)
            print("score_a",piso_a,"QCR_TYPO",on,"→",[(r[0],(c.last_origen_scores or {}).get(r[0])) for r in res])
        c.cerrar_sistema()
