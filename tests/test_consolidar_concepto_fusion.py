"""Regresión: consolidar_concepto sobre un nodo existente debe FUSIONAR, no reemplazar.

Antes usaba ``INSERT OR REPLACE``: la fila vieja se borraba, cambiaba el id, los
``ON DELETE CASCADE`` se llevaban dimensiones / métricas / grupos semánticos,
el trigger de backup no se disparaba y quedaban filas fantasma en FTS5.
Ahora comparte la regla de fusión del ciclo de sueño
(``consolidation.fusionar_en_largo_plazo``).
"""
import time

from core.memory_store import SQLiteMemoryBioRAG

CONCEPTO = "nodo_regresion_fusion"
CONTENIDO_VIEJO = "mamifero domestico felidae gato minino ronronea"
CONTENIDO_NUEVO = "felino casero que caza ratones por la noche"


def _contar(c, sql, params):
    return c.cursor.execute(sql, params).fetchone()[0]


def _foto(c, concepto):
    fila = c.cursor.execute(
        "SELECT id, rowid, creado_en, contenido, peso_sinaptico, categoria, sinonimos, "
        "COALESCE(sustantivos_clave, '') FROM largo_plazo WHERE concepto = ?",
        (concepto,),
    ).fetchone()
    nodo_id = fila[0]
    return {
        "id": nodo_id,
        "rowid": fila[1],
        "creado_en": fila[2],
        "contenido": fila[3],
        "peso": fila[4],
        "categoria": fila[5],
        "sinonimos": fila[6],
        "sk": fila[7],
        "dims": _contar(c, "SELECT COUNT(*) FROM largo_plazo_dimensiones WHERE concepto = ?", (concepto,)),
        "grupos": _contar(c, "SELECT COUNT(*) FROM nodo_grupos_semanticos WHERE concepto = ?", (concepto,)),
        "metricas": _contar(c, "SELECT COUNT(*) FROM metricas_cognitivas_nodos WHERE largo_plazo_id = ?", (nodo_id,)),
    }


def _fantasmas_fts(c):
    total = 0
    for tabla in ("largo_plazo_fts", "largo_plazo_fts_unicode"):
        total += _contar(c, f"SELECT COUNT(*) FROM {tabla} WHERE rowid NOT IN (SELECT rowid FROM largo_plazo)", ())
    return total


def _sembrar_nodo_existente(c):
    """Nodo en largo_plazo con dimensiones, métricas, grupos, peso bajo y categoría propia."""
    c.percibir_corto_plazo(CONCEPTO, CONTENIDO_VIEJO, sinonimos="gato,minino", sustantivos_clave="gato,felino")
    assert c.consolidar_concepto(CONCEPTO) is True

    nodo_id = c.cursor.execute("SELECT id FROM largo_plazo WHERE concepto = ?", (CONCEPTO,)).fetchone()[0]
    cat_especifica = c.cursor.execute("SELECT id FROM categories WHERE id <> 1 ORDER BY id LIMIT 1").fetchone()[0]
    c.cursor.execute(
        "UPDATE largo_plazo SET peso_sinaptico = 0.05, categoria = ?, creado_en = ? WHERE concepto = ?",
        (cat_especifica, 1_700_000_000.0, CONCEPTO),
    )
    for (dim_id,) in c.cursor.execute("SELECT id FROM dimensiones_semanticas ORDER BY id LIMIT 3").fetchall():
        c.cursor.execute(
            "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
            (CONCEPTO, dim_id),
        )
    c.cursor.execute("INSERT OR IGNORE INTO grupos_semanticos (nombre) VALUES ('grupo_test_fusion')")
    grupo_id = c.cursor.execute("SELECT id FROM grupos_semanticos WHERE nombre = 'grupo_test_fusion'").fetchone()[0]
    c.cursor.execute(
        "INSERT OR IGNORE INTO nodo_grupos_semanticos (concepto, palabra, grupo_id) VALUES (?, 'gato', ?)",
        (CONCEPTO, grupo_id),
    )
    c.cursor.execute("INSERT INTO metricas_cognitivas (timestamp) VALUES (?)", (time.time(),))
    metrica_id = c.cursor.lastrowid
    for _ in range(2):
        c.cursor.execute(
            "INSERT INTO metricas_cognitivas_nodos (metrica_id, largo_plazo_id, accion, created_at) "
            "VALUES (?, ?, 'actualizado', ?)",
            (metrica_id, nodo_id, time.time()),
        )
    c.conn.commit()


def test_consolidar_nodo_existente_fusiona_y_preserva(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "fusion.db"))
    try:
        _sembrar_nodo_existente(c)
        antes = _foto(c, CONCEPTO)
        backups_antes = _contar(c, "SELECT COUNT(*) FROM largo_plazo_backup", ())
        assert antes["dims"] == 3 and antes["metricas"] == 2 and antes["grupos"] >= 1
        assert _fantasmas_fts(c) == 0

        c.percibir_corto_plazo(CONCEPTO, CONTENIDO_NUEVO, sinonimos="minino,felino")
        assert c.consolidar_concepto(CONCEPTO) is True
        despues = _foto(c, CONCEPTO)

        # Identidad y fecha de nacimiento intactas
        assert despues["id"] == antes["id"]
        assert despues["rowid"] == antes["rowid"]
        assert despues["creado_en"] == antes["creado_en"]
        # Contenido fusionado (el viejo no se pierde)
        assert despues["contenido"] == f"{CONTENIDO_VIEJO} | Actualización: {CONTENIDO_NUEVO}"
        # LTP de consolidación y categoría específica conservada
        assert abs(despues["peso"] - 0.25) < 1e-9
        assert despues["categoria"] == antes["categoria"]
        # Sinónimos unidos sin duplicados; sustantivos_clave preservados (corto vino vacío)
        assert despues["sinonimos"].split(",") == ["gato", "minino", "felino"]
        assert despues["sk"] == antes["sk"] != ""
        # Nada satélite se pierde por cascada
        assert despues["dims"] >= antes["dims"]
        assert despues["metricas"] == antes["metricas"]
        assert despues["grupos"] >= antes["grupos"]
        # FTS limpio: exactamente una fila por índice para el nodo, cero fantasmas
        assert _fantasmas_fts(c) == 0
        for tabla in ("largo_plazo_fts", "largo_plazo_fts_unicode"):
            assert _contar(c, f"SELECT COUNT(*) FROM {tabla} WHERE rowid = ?", (despues["rowid"],)) == 1
        # No hubo borrado: ni backup nuevo ni filas duplicadas
        assert _contar(c, "SELECT COUNT(*) FROM largo_plazo_backup", ()) == backups_antes
        assert _contar(c, "SELECT COUNT(*) FROM largo_plazo WHERE concepto = ?", (CONCEPTO,)) == 1
        # corto_plazo vaciado
        assert _contar(c, "SELECT COUNT(*) FROM corto_plazo WHERE concepto = ?", (CONCEPTO,)) == 0
    finally:
        c.cerrar_sistema()


def test_consolidar_nodo_nuevo_inserta(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "nuevo.db"))
    try:
        c.percibir_corto_plazo("nodo_nuevo_fusion", CONTENIDO_NUEVO, sinonimos="felino", sustantivos_clave="felino,raton")
        assert c.consolidar_concepto("nodo_nuevo_fusion") is True
        fila = c.cursor.execute(
            "SELECT contenido, peso_sinaptico, estado, sinonimos, sustantivos_clave, creado_en, ultimo_acceso "
            "FROM largo_plazo WHERE concepto = 'nodo_nuevo_fusion'"
        ).fetchone()
        assert fila[0] == CONTENIDO_NUEVO
        assert fila[1] == 1.0
        assert fila[2] == "activo"
        assert fila[3] == "felino"
        assert fila[4] == "felino,raton"
        assert fila[5] is not None and fila[6] is not None
        assert _fantasmas_fts(c) == 0
        assert c.consolidar_concepto("no_existe_en_corto") is False
    finally:
        c.cerrar_sistema()


def test_consolidar_misma_clave_dos_veces(tmp_path):
    c = SQLiteMemoryBioRAG(str(tmp_path / "doble.db"))
    try:
        c.percibir_corto_plazo("clave_repetida", "primera version del recuerdo sobre redes")
        c.consolidar_concepto("clave_repetida")
        id_inicial = c.cursor.execute("SELECT id FROM largo_plazo WHERE concepto = 'clave_repetida'").fetchone()[0]
        for texto in ("segunda version sobre routers", "tercera version sobre switches"):
            c.percibir_corto_plazo("clave_repetida", texto)
            assert c.consolidar_concepto("clave_repetida") is True
        fila = c.cursor.execute(
            "SELECT id, contenido, peso_sinaptico FROM largo_plazo WHERE concepto = 'clave_repetida'"
        ).fetchone()
        assert fila[0] == id_inicial
        assert fila[1] == (
            "primera version del recuerdo sobre redes"
            " | Actualización: segunda version sobre routers"
            " | Actualización: tercera version sobre switches"
        )
        assert fila[2] == 1.0  # tope de LTP
        assert _contar(c, "SELECT COUNT(*) FROM largo_plazo WHERE concepto = 'clave_repetida'", ()) == 1
        assert _fantasmas_fts(c) == 0
    finally:
        c.cerrar_sistema()
