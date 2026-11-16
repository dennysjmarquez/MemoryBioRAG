"""Regression tests for strict Top-5 stability under append-only corpus growth.

All writes happen on temporary SQLite backups. The versioned QA snapshot is
opened read-only and checked byte-for-byte after each experiment.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from core.memory_store import SQLiteMemoryBioRAG

_SNAPSHOT = (
    Path(__file__).resolve().parents[1]
    / "snapshots"
    / "qa_escape_qcr_20260811.db"
)
_QUERY_CASES = (
    ("0516", "real más sistemas"),
    ("0564", "¿Dónde encuentro la info de memoria v5 1 optimizaciones?"),
    ("0608", "declaración dennys puente"),
    ("0670", "establece creador familia"),
    ("0730", "parámetros otrosmemorybioragmcp solo"),
    ("0763", "fin aprendizaje"),
    ("0805", "cv"),
    ("0861", "más dennys asumir"),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _backup_snapshot(destination: Path) -> None:
    source_uri = _SNAPSHOT.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source, sqlite3.connect(destination) as target:
        source.backup(target)


def _fixar_baseline(path: Path) -> int:
    db = SQLiteMemoryBioRAG(db_path=str(path))
    try:
        cutoff = db._search_baseline_rowid
        assert cutoff is not None and cutoff > 0
        return cutoff
    finally:
        db.conn.close()


def _engine(path: Path, monkeypatch) -> SQLiteMemoryBioRAG:
    # Remove variability from optional background/WordNet paths while leaving
    # the production lexical, dimensional and PPMI weights unchanged.
    monkeypatch.setenv("BIORAG_NEURONA", "0")
    monkeypatch.setenv("BIORAG_WORDNET_ENABLED", "0")
    monkeypatch.setenv("BIORAG_ESCALA", "1")
    monkeypatch.setenv("BIORAG_QCR_ACTIVO", "1")
    from core.memory import constants
    monkeypatch.setattr(constants, "SDM_FALLBACK_ACTIVO", False)
    return SQLiteMemoryBioRAG(db_path=str(path))


def _top5_por_query(path: Path, monkeypatch) -> dict[str, list[str]]:
    db = _engine(path, monkeypatch)
    try:
        result = {}
        for case_id, query in _QUERY_CASES:
            rows, _ = db.buscar_por_frase(query, limite=5)
            result[case_id] = [row[0] for row in rows[:5]]
        return result
    finally:
        db.conn.close()


def _top5_unico(path: Path, query: str, monkeypatch) -> list[str]:
    db = _engine(path, monkeypatch)
    try:
        rows, _ = db.buscar_por_frase(query, limite=5)
        return [row[0] for row in rows[:5]]
    finally:
        db.conn.close()


def test_top5_y_orden_no_cambian_con_96_distractores_lexicos(tmp_path, monkeypatch):
    """Stress the ranking with distractors that repeat each query's exact terms."""
    snapshot_hash = _sha256(_SNAPSHOT)
    base_db = tmp_path / "base.db"
    grown_db = tmp_path / "grown.db"
    _backup_snapshot(base_db)
    _backup_snapshot(grown_db)
    cutoff_base = _fixar_baseline(base_db)
    cutoff_growth = _fixar_baseline(grown_db)
    assert cutoff_base == cutoff_growth

    connection = sqlite3.connect(grown_db)
    distractors = []
    for case_id, query in _QUERY_CASES:
        query_terms = re.findall(r"\w{2,}", query.lower())
        for index in range(12):
            distractors.append(
                (
                    f"invarianza_ruido_{case_id}_{index:02d}",
                    "Nota administrativa de inventario. Este registro no responde "
                    "la pregunta ni trata su tema. Etiquetas copiadas sin relación: "
                    f"{' '.join(query_terms)}. Tema real: mantenimiento de estanterías "
                    "y organización de almacén.",
                )
            )
    connection.executemany(
        "INSERT INTO largo_plazo "
        "(concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, "
        " sinonimos, creado_en, sustantivos_clave) "
        "VALUES (?, 1, ?, 1.0, 'activo', '', '', 0, '')",
        distractors,
    )
    # Simula la asociación automática de nuevas memorias irrelevantes con un
    # hub histórico. Las aristas nuevas deben quedar fuera de la geometría del
    # cohorte de referencia, igual que las filas nuevas quedan fuera del FTS base.
    connection.executemany(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
        "VALUES (?, 'version_actual_biorag', 0.99, 'test', 0)",
        ((concepto,) for concepto, _ in distractors),
    )
    connection.commit()
    connection.close()

    baseline = _top5_por_query(base_db, monkeypatch)
    grown = _top5_por_query(grown_db, monkeypatch)
    assert grown == baseline
    assert _sha256(_SNAPSHOT) == snapshot_hash


def test_overlay_estable_y_recupera_alta_pertinente_tras_2000_distractores(tmp_path, monkeypatch):
    """Ignore lexical noise while still admitting a later strong relevant memory."""
    snapshot_hash = _sha256(_SNAPSHOT)
    base_db = tmp_path / "base_2k.db"
    grown_db = tmp_path / "grown_2k.db"
    _backup_snapshot(base_db)
    _backup_snapshot(grown_db)
    cutoff_base = _fixar_baseline(base_db)
    cutoff_growth = _fixar_baseline(grown_db)
    assert cutoff_base == cutoff_growth

    query = "fin aprendizaje"
    before = _top5_unico(base_db, query, monkeypatch)
    assert len(before) == 5
    connection = sqlite3.connect(grown_db)
    distractors = [
        (
            f"ruido_fin_aprendizaje_{index:05d}",
            "Nota de almacén ajena al tema. Etiquetas copiadas: fin aprendizaje. "
            "El asunto real es organización de estanterías.",
        )
        for index in range(2_000)
    ]
    connection.executemany(
        "INSERT INTO largo_plazo "
        "(concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, "
        " sinonimos, creado_en, sustantivos_clave) "
        "VALUES (?, 1, ?, 1.0, 'activo', '', '', 0, '')",
        distractors,
    )
    connection.executemany(
        "INSERT INTO sinapsis (origen, destino, peso, tipo, creado_en) "
        "VALUES (?, 'version_actual_biorag', 0.99, 'test', 0)",
        ((concepto,) for concepto, _ in distractors),
    )
    connection.commit()
    connection.close()

    connection = sqlite3.connect(grown_db)
    plan = connection.execute(
        "EXPLAIN QUERY PLAN SELECT l.rowid, l.concepto "
        "FROM largo_plazo_fts f CROSS JOIN largo_plazo l ON l.rowid=f.rowid "
        "WHERE largo_plazo_fts MATCH ? AND l.rowid>? AND l.estado='activo' "
        "ORDER BY rank LIMIT ?",
        ('"fin" OR "aprendizaje"', cutoff_growth, 100),
    ).fetchall()
    connection.close()
    plan_text = " ".join(row[3] for row in plan).upper()
    assert "VIRTUAL TABLE INDEX" in plan_text
    assert "SCAN LARGO_PLAZO" not in plan_text

    after_noise = _top5_unico(grown_db, query, monkeypatch)
    assert after_noise == before

    # La alta relevante queda detrás de los 2.000 rowids de ruido: el overlay
    # debe rankear sus postings, no truncar por antigüedad de inserción.
    connection = sqlite3.connect(grown_db)
    connection.execute(
        "INSERT INTO largo_plazo "
        "(concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, "
        " sinonimos, creado_en, sustantivos_clave) "
        "VALUES (?, 1, ?, 1.0, 'activo', '', '', 0, '')",
        (
            "fin_aprendizaje",
            "El fin del aprendizaje es comprender y aplicar conocimiento.",
        ),
    )
    connection.commit()
    connection.close()

    after_relevant = _top5_unico(grown_db, query, monkeypatch)
    assert after_relevant[0] == "fin_aprendizaje"
    assert after_relevant != before
    assert _sha256(_SNAPSHOT) == snapshot_hash


def test_un_recuerdo_nuevo_pertinente_si_puede_entrar_al_top5(tmp_path, monkeypatch):
    """The frozen seed cohort must not block a genuinely strong new match."""
    snapshot_hash = _sha256(_SNAPSHOT)
    base_db = tmp_path / "base.db"
    grown_db = tmp_path / "grown.db"
    _backup_snapshot(base_db)
    _backup_snapshot(grown_db)
    _fixar_baseline(base_db)
    _fixar_baseline(grown_db)

    query = "parámetros otrosmemorybioragmcp solo"
    before = _top5_unico(base_db, query, monkeypatch)

    connection = sqlite3.connect(grown_db)
    connection.execute(
        "INSERT INTO largo_plazo "
        "(concepto, categoria, contenido, peso_sinaptico, estado, asociaciones, "
        " sinonimos, creado_en, sustantivos_clave) "
        "VALUES (?, 1, ?, 1.0, 'activo', '', '', 0, '')",
        (
            "parametros_otrosmemorybioragmcp_solo",
            "Oráculo para los parámetros de otrosmemorybioragmcp solo: "
            "permite preguntar y obtener una respuesta pertinente.",
        ),
    )
    connection.commit()
    connection.close()

    after = _top5_unico(grown_db, query, monkeypatch)
    assert after[0] == "parametros_otrosmemorybioragmcp_solo"
    assert after != before
    assert _sha256(_SNAPSHOT) == snapshot_hash


def test_sdm_full_scan_is_opt_in_and_skipped_by_online_search(tmp_path, monkeypatch):
    """Keep the legacy O(N) SDM fallback out of the default search path."""
    from core.memory import constants
    import core.sdm as sdm

    snapshot_hash = _sha256(_SNAPSHOT)
    db_path = tmp_path / "sdm_route.db"
    _backup_snapshot(db_path)
    db = _engine(db_path, monkeypatch)
    query = "zzqx jkmn rtyu"
    calls = []
    statements = []
    monkeypatch.setattr(constants, "SDM_FALLBACK_ACTIVO", True)
    monkeypatch.setattr(
        sdm,
        "rescatar_fallback_sdm",
        lambda _db, phrase, **_kwargs: calls.append(phrase) or [],
    )
    db.conn.set_trace_callback(statements.append)
    try:
        # This no-overlap query reaches Fallback 2.5 when the legacy flag is on.
        db.buscar_por_frase(query, limite=5)
        assert query in calls

        # The production default is now OFF; no full nodos_sdm read is allowed.
        calls.clear()
        statements.clear()
        monkeypatch.setattr(constants, "SDM_FALLBACK_ACTIVO", False)
        db.buscar_por_frase(query, limite=5)
        assert calls == []
        normalized_sql = {" ".join(sql.lower().split()) for sql in statements}
        assert "select concepto, vector from nodos_sdm" not in normalized_sql
    finally:
        db.conn.close()

    assert _sha256(_SNAPSHOT) == snapshot_hash


def test_sdm_fallback_default_is_disabled():
    """An unset env var must not re-enable the O(N) online fallback."""
    env = os.environ.copy()
    env.pop("BIORAG_SDM_FALLBACK", None)
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from core.memory import constants; "
            "print(int(constants.SDM_FALLBACK_ACTIVO))",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        check=True,
        text=True,
    )
    assert result.stdout.strip().splitlines()[-1] == "0"
