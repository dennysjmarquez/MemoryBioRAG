"""Multihop v1: expansion 1-salto en retrieval (flag OFF default)."""
import pytest

import core.memory_store as ms
from core.memory_store import SQLiteMemoryBioRAG


@pytest.fixture()
def cz_tmp(tmp_path, monkeypatch):
    cz = SQLiteMemoryBioRAG(db_path=str(tmp_path / "mh.db"))
    monkeypatch.setattr(ms, "MULTIHOP_EXPANSION", False)
    return cz


def _nodo(cz, concepto, contenido, estado="activo", peso=0.5):
    cz.cursor.execute(
        "INSERT INTO largo_plazo (concepto, contenido, peso_sinaptico, estado)"
        " VALUES (?, ?, ?, ?)",
        (concepto, contenido, peso, estado),
    )


def _sinapsis(cz, a, b, peso=0.9):
    cz.cursor.execute(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en, ultimo_uso)"
        " VALUES (?, ?, ?, 'manual', 1, 1)",
        (a, b, peso),
    )


def _nombres(pool):
    return [r[0] for r in pool]


def test_off_no_invoca_expansion(cz_tmp, monkeypatch):
    """Flag 0: helper jamas llamado, busqueda intacta."""
    cz = cz_tmp
    _nodo(cz, "mh_manzana", "una manzana roja")
    cz.conn.commit()
    llamadas = []
    orig = ms.SQLiteMemoryBioRAG._multihop_vecinos

    def _spy(self, semillas, excluir, limite):
        llamadas.append(1)
        return orig(self, semillas, excluir, limite)

    monkeypatch.setattr(ms.SQLiteMemoryBioRAG, "_multihop_vecinos", _spy)
    pool, total = cz.buscar_por_frase("manzana", limite=5)
    assert llamadas == [] and total >= 1


def test_on_rescata_vecino_al_pool(cz_tmp, monkeypatch):
    """Flag 1: vecino sin match lexico entra al pool; OFF lo excluye."""
    cz = cz_tmp
    _nodo(cz, "mh_a", "manzana jugosa madura")
    _nodo(cz, "mh_b", "tornillo de acero inoxidable")
    _sinapsis(cz, "mh_a", "mh_b", 0.9)
    cz.conn.commit()
    monkeypatch.setattr(ms, "MULTIHOP_EXPANSION", True)
    pool_on, _ = cz.buscar_por_frase("manzana", limite=10)
    assert "mh_b" in _nombres(pool_on)
    monkeypatch.setattr(ms, "MULTIHOP_EXPANSION", False)
    pool_off, _ = cz.buscar_por_frase("manzana", limite=10)
    assert "mh_b" not in _nombres(pool_off)


def test_cap_total_acota_inyeccion(cz_tmp, monkeypatch):
    """Diferencia ON-OFF <= MAX_TOTAL aunque haya mas vecinos."""
    cz = cz_tmp
    _nodo(cz, "mh_hub", "manzana central unica")
    for i in range(8):
        _nodo(cz, "mh_v%d" % i, "contenido neutral numero %d" % i)
        _sinapsis(cz, "mh_hub", "mh_v%d" % i, 0.9 - i * 0.01)
    cz.conn.commit()
    monkeypatch.setattr(ms, "MULTIHOP_EXPANSION", False)
    off, _ = cz.buscar_por_frase("manzana", limite=50)
    monkeypatch.setattr(ms, "MULTIHOP_EXPANSION", True)
    monkeypatch.setattr(ms, "MULTIHOP_MAX_TOTAL", 5)
    on, _ = cz.buscar_por_frase("manzana", limite=50)
    assert len(set(_nombres(on)) - set(_nombres(off))) <= 5


def test_solo_nodos_activos(cz_tmp, monkeypatch):
    """Vecino dormido jamas entra, aunque la arista exista."""
    cz = cz_tmp
    _nodo(cz, "mh_a2", "manzana verde acida")
    _nodo(cz, "mh_z", "tornillo dormido profundo", estado="dormido")
    _sinapsis(cz, "mh_a2", "mh_z", 0.9)
    cz.conn.commit()
    monkeypatch.setattr(ms, "MULTIHOP_EXPANSION", True)
    pool, _ = cz.buscar_por_frase("manzana", limite=10)
    assert "mh_z" not in _nombres(pool)


def test_gate_profundidad_no_activos(cz_tmp, monkeypatch):
    """profundidad != activos: sin expansion (dormido/negativo intactos)."""
    cz = cz_tmp
    _nodo(cz, "mh_a3", "manzana amarilla dulce")
    _nodo(cz, "mh_w", "clavo oxidado viejo")
    _sinapsis(cz, "mh_a3", "mh_w", 0.9)
    cz.conn.commit()
    llamadas = []
    orig = ms.SQLiteMemoryBioRAG._multihop_vecinos

    def _spy(self, semillas, excluir, limite):
        llamadas.append(1)
        return orig(self, semillas, excluir, limite)

    monkeypatch.setattr(ms.SQLiteMemoryBioRAG, "_multihop_vecinos", _spy)
    monkeypatch.setattr(ms, "MULTIHOP_EXPANSION", True)
    pool, _ = cz.buscar_por_frase("manzana", limite=10, profundidad="profundo")
    assert llamadas == [] and "mh_w" not in _nombres(pool)


def test_determinismo_doble_corrida(cz_tmp, monkeypatch):
    """Misma query+DB: orden identico (desempate peso->nombre)."""
    cz = cz_tmp
    _nodo(cz, "mh_s", "manzana semilla test")
    _nodo(cz, "mh_m", "alambre cobre fino")
    _nodo(cz, "mh_n", "madera roble mesa")
    _sinapsis(cz, "mh_s", "mh_m", 0.5)
    _sinapsis(cz, "mh_s", "mh_n", 0.5)
    cz.conn.commit()
    monkeypatch.setattr(ms, "MULTIHOP_EXPANSION", True)
    p1, _ = cz.buscar_por_frase("manzana", limite=10)
    p2, _ = cz.buscar_por_frase("manzana", limite=10)
    assert _nombres(p1) == _nombres(p2)
