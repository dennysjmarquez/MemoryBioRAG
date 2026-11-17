"""Explicit dimensional searches can retrieve memories added after startup."""

from core.memory_store import SQLiteMemoryBioRAG


def test_explicit_dimension_search_includes_post_baseline_memories(tmp_path):
    path = tmp_path / "dimensional_overlay.db"

    # Seed one reference row, then reopen so its rowid becomes the frozen cutoff.
    seed = SQLiteMemoryBioRAG(str(path))
    seed.cursor.execute(
        "INSERT INTO largo_plazo "
        "(concepto, contenido, peso_sinaptico, estado, creado_en) "
        "VALUES ('referencia_sin_dim', 'memoria de referencia', 1.0, 'activo', 1)"
    )
    seed.conn.commit()
    seed.cerrar_sistema()

    db = SQLiteMemoryBioRAG(str(path))
    try:
        cutoff = db._search_baseline_rowid
        assert cutoff is not None and cutoff > 0
        dimension_id = db.cursor.execute(
            "SELECT id FROM dimensiones_semanticas ORDER BY id LIMIT 1"
        ).fetchone()[0]

        db.cursor.execute(
            "INSERT INTO largo_plazo "
            "(concepto, contenido, peso_sinaptico, estado, creado_en) "
            "VALUES ('memoria_dimensional_nueva', 'contenido sin coincidencia léxica', "
            "1.0, 'activo', 2)"
        )
        db.cursor.execute(
            "INSERT INTO largo_plazo_dimensiones (concepto, dimension_id) "
            "VALUES ('memoria_dimensional_nueva', ?) ",
            (dimension_id,),
        )
        db.conn.commit()

        results, total = db.buscar_por_frase(
            "", dimensiones_ids=[dimension_id], profundidad="profundo", limite=10
        )

        assert total > 0
        assert "memoria_dimensional_nueva" in [row[0] for row in results]
        assert db.last_origen_scores["memoria_dimensional_nueva"][0] == "dimensional_fallback"
    finally:
        db.cerrar_sistema()


def test_symbolic_search_includes_post_baseline_memories(tmp_path, monkeypatch):
    path = tmp_path / "symbolic_overlay.db"
    monkeypatch.setenv("BIORAG_ESCALA", "1")
    monkeypatch.setenv("BIORAG_WORDNET_ENABLED", "0")
    monkeypatch.setenv("BIORAG_HUB_ENABLED", "0")

    seed = SQLiteMemoryBioRAG(str(path))
    seed.cursor.execute(
        "INSERT INTO largo_plazo "
        "(concepto, contenido, peso_sinaptico, estado, creado_en) "
        "VALUES ('referencia_sin_salud', 'nota de referencia', "
        "1.0, 'activo', 1)"
    )
    seed.conn.commit()
    seed.cerrar_sistema()

    db = SQLiteMemoryBioRAG(str(path))
    try:
        cutoff = db._search_baseline_rowid
        assert cutoff is not None and cutoff > 0
        db.cursor.execute(
            "INSERT INTO largo_plazo "
            "(concepto, contenido, peso_sinaptico, estado, asociaciones, sinonimos, creado_en) "
            "VALUES ('test_hta_simbolico', 'Hipertensión arterial sistémica. Presión elevada.', "
            "1.0, 'activo', '', 'hta,presion alta,tension arterial', 2)"
        )
        db.conn.commit()

        results, total = db.buscar_por_frase("hipertension", limite=10)

        assert total >= 1
        assert "test_hta_simbolico" in [row[0] for row in results]
    finally:
        db.cerrar_sistema()
