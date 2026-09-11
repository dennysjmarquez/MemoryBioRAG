"""F2: memoria episódica temporal — expansión ±24h y afinidad de pool."""
import time

from core.memory_store import SQLiteMemoryBioRAG, EPISODIO_TEMPORAL_PESO


def _nodo(c, concepto, contenido, ts):
    c.percibir_corto_plazo(concepto, contenido)
    c.consolidar_concepto(concepto)
    c.cursor.execute(
        "UPDATE largo_plazo SET creado_en=?, ultimo_acceso=? WHERE concepto=?",
        (ts, ts, concepto),
    )
    c.conn.commit()


def test_expandir_episodio_ventana_24h(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "f2.db"))
    now = time.time()
    _nodo(c, "ancla", "evento principal", now)
    _nodo(c, "cerca", "mismo dia", now + 3600)
    _nodo(c, "lejos", "otro mes", now + 40 * 86400)
    hits = c._expandir_episodio_temporal("ancla", ventana_horas=24, limite_episodio=5)
    names = {h["concepto"] for h in hits}
    assert "cerca" in names
    assert "lejos" not in names
    assert len(hits) <= 5


def test_afinidad_pool_mismo_bucket(tmp_path, monkeypatch):
    import core.memory_store as ms
    monkeypatch.setattr(ms, "EPISODIO_TEMPORAL_PESO", 0.05)
    c = SQLiteMemoryBioRAG(str(tmp_path / "f2aff.db"))
    now = time.time()
    _nodo(c, "a", "uno", now)
    _nodo(c, "b", "dos", now + 100)
    _nodo(c, "c", "otro dia", now + 3 * 86400)
    aff = c._afinidad_temporal_pool(["a", "b", "c"])
    assert aff["a"] == 1.0
    assert aff["b"] == 1.0
    assert aff["c"] == 0.0


def test_peso_default_on_tras_gate():
    assert EPISODIO_TEMPORAL_PESO == 0.05


def test_expandir_episodio_en_buscar(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "f2b.db"))
    now = time.time()
    _nodo(c, "ancla_q", "frase unica xyzabc", now)
    _nodo(c, "vecino_ep", "otro contenido", now + 120)
    r, _total = c.buscar_por_frase("frase unica xyzabc", expandir_episodio=True)
    names = [x[0] for x in r]
    assert "ancla_q" in names
    assert "vecino_ep" in names
