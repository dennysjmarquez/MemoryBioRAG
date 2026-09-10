"""E8: pred_score solo si hay predicado extraido o Nt>=3."""
import inspect

from core.memory_store import SQLiteMemoryBioRAG


def test_mono_token_sin_verbo_cierra(monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "SRL_CONDICIONAL", True)
    assert SQLiteMemoryBioRAG._srl_predicado_informativo("boost") is False
    assert SQLiteMemoryBioRAG._srl_predicado_informativo("memoria") is False


def test_tres_tokens_abre(monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "SRL_CONDICIONAL", True)
    assert SQLiteMemoryBioRAG._srl_predicado_informativo("activa largo archivos") is True


def test_flag_off_siempre_abre(monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "SRL_CONDICIONAL", False)
    assert SQLiteMemoryBioRAG._srl_predicado_informativo("boost") is True


def test_fuente_buscar():
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "_srl_predicado_informativo" in src
    assert "_srl_e8" in src
