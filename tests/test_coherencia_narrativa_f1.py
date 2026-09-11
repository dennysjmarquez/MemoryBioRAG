"""F1: coherencia narrativa SRL sobre top-k."""
import inspect
import time

from core.memory_store import SQLiteMemoryBioRAG


def test_transicion_objeto_sujeto(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "COHERENCIA_NARRATIVA_PESO", 0.05)
    c = SQLiteMemoryBioRAG(str(tmp_path / "f1.db"))
    for name, txt in (
        ("nodo_causa_f1", "el sistema fallo en produccion"),
        ("nodo_efecto_f1", "el operador reacciono al sistema"),
    ):
        c.percibir_corto_plazo(name, txt)
        c.consolidar_concepto(name)
    ahora = time.time()
    c.cursor.execute(
        "INSERT INTO predicados (concepto, sujeto, accion, objeto, contexto, creado_en) "
        "VALUES ('nodo_causa_f1', 'sistema', 'fallo', 'produccion', '', ?)",
        (ahora,),
    )
    c.cursor.execute(
        "INSERT INTO predicados (concepto, sujeto, accion, objeto, contexto, creado_en) "
        "VALUES ('nodo_efecto_f1', 'operador', 'reacciono', 'sistema', '', ?)",
        (ahora,),
    )
    c.conn.commit()
    coh = c._evaluar_coherencia_narrativa(["nodo_causa_f1", "nodo_efecto_f1", "ausente"])
    assert coh["nodo_causa_f1"] == 1.0
    assert coh["nodo_efecto_f1"] == 1.0
    assert coh.get("ausente", 0.0) == 0.0
    c.cerrar_sistema()


def test_peso_cero(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "COHERENCIA_NARRATIVA_PESO", 0.0)
    c = SQLiteMemoryBioRAG(str(tmp_path / "f1z.db"))
    assert c._evaluar_coherencia_narrativa(["a", "b"]) == {}
    c.cerrar_sistema()


def test_fuente_top_k():
    src = inspect.getsource(SQLiteMemoryBioRAG.buscar_por_frase)
    assert "_evaluar_coherencia_narrativa" in src
    assert "COHERENCIA_NARRATIVA_PESO" in src
