#!/usr/bin/env python3
"""
Tests T8 — Verificación de instalación — DB nueva y DB migrada (RF-22 / Spec 001).

RF cubierto: RF-22 (CL-12, CL-13).

Hecho cuando:
  - DB nueva desde cero: `.schema corto_plazo` y `.schema largo_plazo` muestran `sustantivos_clave TEXT DEFAULT ''`
    incluido en el CREATE TABLE original.
  - DB nueva: `largo_plazo_fts` se crea con 4 columnas (concepto, contenido, sinonimos, sustantivos_clave).
  - DB nueva: `percibir_corto_plazo` con sustantivos_clave funciona end-to-end (guardar → FTS5 → consolidar).
  - DB migrada: copia de DB sin la columna → arranque aplica ALTER a ambas tablas + rebuild FTS5.
  - DB migrada: nodos pre-existentes quedan intactos (solo suman la columna vacía, sin backfill).
  - DB migrada: nuevos nodos guardados y búsquedas FTS5 funcionan tras la migración.
"""
import os
import sys
import sqlite3
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_store import SQLiteMemoryBioRAG


def _get_table_ddl(db_path, table_name):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def _get_columns(db_path, table_name):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    cols = {row[1]: row[2] for row in cur.fetchall()}
    conn.close()
    return cols


class TestT8DBNuevaDesdeCero:
    """Verifica la ruta 1 de instalación: inicialización limpia desde cero (RF-22, CL-12)."""

    def test_db_nueva_schema_tablas_incluye_sustantivos_clave_en_ddl(self, tmp_path):
        db_path = tmp_path / "nueva_instalacion.db"
        cerebro = SQLiteMemoryBioRAG(str(db_path))
        cerebro.cerrar_sistema()

        # 1. Verificar DDL original de corto_plazo y largo_plazo
        ddl_cp = _get_table_ddl(db_path, "corto_plazo")
        ddl_lp = _get_table_ddl(db_path, "largo_plazo")

        assert "sustantivos_clave" in ddl_cp, f"corto_plazo DDL no incluye sustantivos_clave: {ddl_cp}"
        assert "sustantivos_clave" in ddl_lp, f"largo_plazo DDL no incluye sustantivos_clave: {ddl_lp}"

        cols_cp = _get_columns(db_path, "corto_plazo")
        cols_lp = _get_columns(db_path, "largo_plazo")
        assert "sustantivos_clave" in cols_cp
        assert "sustantivos_clave" in cols_lp

    def test_db_nueva_fts5_tiene_4_columnas(self, tmp_path):
        db_path = tmp_path / "nueva_fts.db"
        cerebro = SQLiteMemoryBioRAG(str(db_path))
        cerebro.cerrar_sistema()

        ddl_fts = _get_table_ddl(db_path, "largo_plazo_fts")
        assert "largo_plazo_fts" in ddl_fts
        assert "sustantivos_clave" in ddl_fts
        assert "sinonimos" in ddl_fts
        assert "concepto" in ddl_fts
        assert "contenido" in ddl_fts
        assert "trigram" in ddl_fts

    def test_db_nueva_flujo_e2e_guardar_consolidar_fts(self, tmp_path):
        db_path = tmp_path / "nueva_e2e.db"
        cerebro = SQLiteMemoryBioRAG(str(db_path))

        # Guardar en corto plazo
        cerebro.percibir_corto_plazo(
            concepto="nodo_fresco",
            contenido="Arquitectura de microservicios con balanceador de carga",
            sustantivos_clave="microservicios,balanceador"
        )

        # Verificar corto plazo
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT sustantivos_clave FROM corto_plazo WHERE concepto = 'nodo_fresco'")
        row_cp = cur.fetchone()
        assert row_cp is not None
        assert row_cp[0] == "microservicios,balanceador"

        # Consolidar a largo plazo
        cerebro.ciclo_sueno_consolidacion()

        # Verificar largo plazo y FTS5
        cur.execute("SELECT sustantivos_clave FROM largo_plazo WHERE concepto = 'nodo_fresco'")
        row_lp = cur.fetchone()
        assert row_lp is not None
        assert row_lp[0] == "microservicios,balanceador"

        cur.execute("""
            SELECT f.sustantivos_clave FROM largo_plazo_fts f
            JOIN largo_plazo l ON f.rowid = l.rowid
            WHERE l.concepto = 'nodo_fresco'
        """)
        row_fts = cur.fetchone()
        assert row_fts is not None
        assert row_fts[0] == "microservicios,balanceador"
        conn.close()
        cerebro.cerrar_sistema()


class TestT8DBMigradaLegacy:
    """Verifica la ruta 2 de instalación: migración transparente de una DB legacy (RF-22, CL-13)."""

    def _crear_db_legacy_autentica(self, db_path):
        """Construye una DB completa y la degrada al esquema pre-T2 (sin columna sustantivos_clave y FTS3)."""
        cerebro = SQLiteMemoryBioRAG(str(db_path))
        cerebro.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, sinonimos, categoria, creado_en) "
            "VALUES ('nodo_legacy_1', 'Contenido historico importante de la base de datos', 'legacy,historia', 1, 1000.0)"
        )
        cerebro.cursor.execute(
            "INSERT INTO largo_plazo (concepto, contenido, sinonimos, categoria, creado_en) "
            "VALUES ('nodo_legacy_2', 'Configuracion de red y parametros de conexion', 'red,conexion', 1, 1000.0)"
        )
        # Degradar schema eliminando sustantivos_clave y FTS4
        cerebro.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_ai")
        cerebro.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_ad")
        cerebro.cursor.execute("DROP TRIGGER IF EXISTS largo_plazo_au")
        try:
            cerebro.cursor.execute("ALTER TABLE largo_plazo DROP COLUMN sustantivos_clave")
            cerebro.cursor.execute("ALTER TABLE corto_plazo DROP COLUMN sustantivos_clave")
        except sqlite3.OperationalError:
            pass
        cerebro.cursor.execute("DROP TABLE IF EXISTS largo_plazo_fts")
        cerebro.cursor.execute("""
            CREATE VIRTUAL TABLE largo_plazo_fts USING fts5(
                concepto,
                contenido,
                sinonimos,
                tokenize='trigram'
            )
        """)
        cerebro.cursor.execute("""
            INSERT INTO largo_plazo_fts(rowid, concepto, contenido, sinonimos)
            SELECT id, concepto, contenido, sinonimos FROM largo_plazo
        """)
        cerebro.conn.commit()
        cerebro.cerrar_sistema()
        return db_path

    def test_migracion_agrega_columnas_rebuild_fts_y_preserva_datos(self, tmp_path):
        db_path = tmp_path / "legacy.db"
        self._crear_db_legacy_autentica(db_path)

        # Verificar que inicialmente NO tienen la columna
        cols_cp_antes = _get_columns(db_path, "corto_plazo")
        cols_lp_antes = _get_columns(db_path, "largo_plazo")
        assert "sustantivos_clave" not in cols_cp_antes
        assert "sustantivos_clave" not in cols_lp_antes

        # Instanciar SQLiteMemoryBioRAG para disparar la migración
        cerebro = SQLiteMemoryBioRAG(str(db_path))

        # 1. Verificar que las columnas fueron agregadas
        cols_cp_despues = _get_columns(db_path, "corto_plazo")
        cols_lp_despues = _get_columns(db_path, "largo_plazo")
        assert "sustantivos_clave" in cols_cp_despues
        assert "sustantivos_clave" in cols_lp_despues

        # 2. Verificar que los nodos preexistentes se mantuvieron intactos con sustantivos_clave="" (RF-15)
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT concepto, contenido, sinonimos, sustantivos_clave FROM largo_plazo ORDER BY id")
        rows = cur.fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "nodo_legacy_1"
        assert rows[0][1] == "Contenido historico importante de la base de datos"
        assert rows[0][2] == "legacy,historia"
        assert rows[0][3] == "", "RF-15: nodo legacy debe tener sustantivos_clave vacío sin backfill"

        assert rows[1][0] == "nodo_legacy_2"
        assert rows[1][3] == ""

        # 3. Verificar que FTS5 fue reconstruida con 4 columnas y contiene los nodos legacy
        cur.execute("SELECT concepto, contenido, sinonimos, sustantivos_clave FROM largo_plazo_fts ORDER BY rowid")
        rows_fts = cur.fetchall()
        assert len(rows_fts) == 2
        assert rows_fts[0][0] == "nodo_legacy_1"
        assert rows_fts[0][3] == ""
        assert rows_fts[1][0] == "nodo_legacy_2"

        # 4. Verificar que se pueden agregar nuevos nodos tras la migración
        cerebro.percibir_corto_plazo(
            concepto="nodo_post_migracion",
            contenido="Nuevo servicio desplegado post migracion de esquema",
            sustantivos_clave="servicio,despliegue"
        )
        cerebro.ciclo_sueno_consolidacion()

        cur.execute("SELECT sustantivos_clave FROM largo_plazo WHERE concepto = 'nodo_post_migracion'")
        assert cur.fetchone()[0] == "servicio,despliegue"

        # 5. Búsqueda por FTS funcionando en la base migrada
        resultados, total = cerebro.buscar_por_frase("servicio desplegado", limite=5)
        assert len(resultados) > 0
        assert resultados[0][0] == "nodo_post_migracion"

        conn.close()
        cerebro.cerrar_sistema()
