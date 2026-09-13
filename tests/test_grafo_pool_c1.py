"""Conexion #1 v1: grafo -> pool primario con admision estricta (flag OFF default)."""
import pytest

import core.memory_store as ms
from core.memory_store import SQLiteMemoryBioRAG


@pytest.fixture()
def cz_tmp(tmp_path, monkeypatch):
    cz = SQLiteMemoryBioRAG(db_path=str(tmp_path / "c1.db"))
    monkeypatch.setattr(ms, "GRAFO_POOL_ACTIVO", False)
    monkeypatch.setattr(ms, "GRAFO_POOL_K_SEEDS", 2)
    monkeypatch.setattr(ms, "GRAFO_POOL_MAX", 6)
    monkeypatch.setattr(ms, "GRAFO_POOL_PESO_MIN", 0.30)
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


def _pool_nombres(cz):
    return [r[1] for r in (cz.last_todos or [])]


def _armar_convergencia(cz):
    _nodo(cz, "c1_s1", "manzana roja dulce")
    _nodo(cz, "c1_s2", "manzana roja acida")
    _nodo(cz, "c1_x", "contenido sin match lexico zzqx")
    _nodo(cz, "c1_y", "otro contenido sin match zzqw")
    _nodo(cz, "c1_z", "mas contenido sin match zzqe")
    _sinapsis(cz, "c1_s1", "c1_x", 0.9)
    _sinapsis(cz, "c1_s2", "c1_x", 0.9)
    _sinapsis(cz, "c1_s1", "c1_y", 0.9)
    _sinapsis(cz, "c1_s1", "c1_z", 0.2)
    _sinapsis(cz, "c1_s2", "c1_z", 0.2)
    cz.conn.commit()


def test_off_default_sin_inyeccion(cz_tmp):
    """Flag 0: convergente fuerte NO entra al pool."""
    _armar_convergencia(cz_tmp)
    pool, _ = cz_tmp.buscar_por_frase("manzana roja", limite=10)
    assert "c1_x" not in _pool_nombres(cz_tmp)


def test_on_convergencia_k2(cz_tmp, monkeypatch):
    """Flag 1: entra X (k=2, peso alto); Y (k=1) y Z (bajo piso) fuera."""
    _armar_convergencia(cz_tmp)
    monkeypatch.setattr(ms, "GRAFO_POOL_ACTIVO", True)
    pool, _ = cz_tmp.buscar_por_frase("manzana roja", limite=10)
    nombres = _pool_nombres(cz_tmp)
    assert "c1_s1" in nombres and "c1_s2" in nombres  # semillas presentes
    assert "c1_x" in nombres
    assert "c1_y" not in nombres and "c1_z" not in nombres
    orig, conf = cz_tmp.last_origen_scores["c1_x"]
    assert orig == "grafo_rescate" and conf == pytest.approx(0.9)


def test_cap_acota_inyeccion(cz_tmp, monkeypatch):
    """Max 6 aunque haya 8 convergentes."""
    _nodo(cz_tmp, "c1_a", "tornillo acero")
    _nodo(cz_tmp, "c1_b", "tornillo acero")
    for i in range(8):
        _nodo(cz_tmp, f"c1_n{i}", f"relleno {i} qqwx")
        _sinapsis(cz_tmp, "c1_a", f"c1_n{i}", 0.9)
        _sinapsis(cz_tmp, "c1_b", f"c1_n{i}", 0.9)
    cz_tmp.conn.commit()
    monkeypatch.setattr(ms, "GRAFO_POOL_ACTIVO", True)
    cz_tmp.buscar_por_frase("tornillo acero", limite=20)
    iny = [c for c in _pool_nombres(cz_tmp) if c.startswith("c1_n")]
    assert len(iny) == 6


def test_solo_nodos_activos(cz_tmp, monkeypatch):
    """Convergente dormido NO se inyecta (profundidad activos)."""
    _nodo(cz_tmp, "c1_p", "cable cobre")
    _nodo(cz_tmp, "c1_q", "cable cobre")
    _nodo(cz_tmp, "c1_dorm", "dormido qqwz", estado="dormido")
    _sinapsis(cz_tmp, "c1_p", "c1_dorm", 0.9)
    _sinapsis(cz_tmp, "c1_q", "c1_dorm", 0.9)
    cz_tmp.conn.commit()
    monkeypatch.setattr(ms, "GRAFO_POOL_ACTIVO", True)
    cz_tmp.buscar_por_frase("cable cobre", limite=10)
    assert "c1_dorm" not in _pool_nombres(cz_tmp)


def test_determinismo_doble_corrida(cz_tmp, monkeypatch):
    """Dos corridas ON: mismo pool en el mismo orden."""
    _armar_convergencia(cz_tmp)
    monkeypatch.setattr(ms, "GRAFO_POOL_ACTIVO", True)
    cz_tmp.buscar_por_frase("manzana roja", limite=10)
    run1 = _pool_nombres(cz_tmp)
    cz_tmp.buscar_por_frase("manzana roja", limite=10)
    run2 = _pool_nombres(cz_tmp)
    assert run1 == run2 and "c1_x" in run1


def test_un_token_no_inyecta(cz_tmp, monkeypatch):
    """Query de 1 token: strictness, sin inyeccion aunque haya convergencia."""
    _armar_convergencia(cz_tmp)
    monkeypatch.setattr(ms, "GRAFO_POOL_ACTIVO", True)
    cz_tmp.buscar_por_frase("manzana", limite=10)
    assert "c1_x" not in _pool_nombres(cz_tmp)
