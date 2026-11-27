# Inventario de los `except sqlite3.OperationalError: pass` de `core/` (sonda del 27-11)

> Generado por `sonda_except_pass.py`. Estático: `ast` sobre `core/`. Dinámico: traza en un mundo sintético de la capa L (s7, |D| = 200, D∪I1, motor real; búsquedas c1/c2 en `activos` y `profundo`, 1 de cada 5 en modo estricto; canal 2; 2 sueños). **«No salta» solo quiere decir que no saltó en estos caminos**, no que nunca salte. No se tocó el motor. Duración: 53 s.

| # | sitio (handler) | bloque try | primera línea del try | ¿saltó? | excepción (n) |
|---|---|---|---|---|---|
| 1 | `core/mcp_server/search.py:877` | L860–876 | `cerebro.cursor.execute(f"""` | no | — |
| 2 | `core/memory/consolidation.py:740` | L739–739 | `self.cursor.execute("INSERT INTO largo_plazo_fts_unicode(largo_plazo_fts_unicode) VALUES('` | no | — |
| 3 | `core/memory/rafaga.py:132` | L110–131 | `self.cursor.execute(` | no | — |
| 4 | `core/memory/rafaga.py:159` | L137–158 | `self.cursor.execute(` | no | — |
| 5 | `core/memory/rafaga.py:39` | L32–38 | `self.cursor.execute(` | no | — |
| 6 | `core/memory/schema.py:109` | L108–108 | `self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN sinonimos TEXT DEFAULT ''")` | no | — |
| 7 | `core/memory/schema.py:120` | L114–119 | `self.cursor.execute("ALTER TABLE largo_plazo ADD COLUMN creado_en REAL DEFAULT 0")` | no | — |
| 8 | `core/memory/search.py:567` | L563–566 | `self.cursor.execute(sql_rol_all, tuple(fb_rol_params))` | no | — |
| 9 | `core/memory/search.py:628` | L617–627 | `self.cursor.execute(` | no | — |
| 10 | `core/memory/search.py:664` | L658–663 | `self.cursor.execute(sql_con_pc, tuple([near_query]) + tuple(temporal_params) + tuple(pc_pa` | no | — |
| 11 | `core/memory/search.py:676` | L670–675 | `self.cursor.execute(sql_con_pc, (fts_match,) + tuple(temporal_params) + tuple(pc_params))` | no | — |
| 12 | `core/memory/search.py:692` | L683–691 | `self.cursor.execute(sql_con_pc, (fts_match,) + tuple(temporal_params) + tuple(pc_params))` | no | — |
| 13 | `core/memory/search.py:744` | L725–743 | `self.cursor.execute(` | no | — |
| 14 | `core/memory/search.py:791` | L769–790 | `query_wild = self._agregar_prefix_wildcards(query)` | no | — |
| 15 | `core/memory/search.py:817` | L801–816 | `_cjk_rows = _cjk_corto.filas(self.cursor, _cjk_terms, clause[len(" AND "):] if clause else` | no | — |
| 16 | `core/memory/search.py:913` | L838–912 | `_ids_17 = (` | pasa otra excepción (no la traga) | GeneratorExit ×75:  |
| 17 | `core/memory/search.py:1071` | L1057–1070 | `self.cursor.execute(` | no | — |
| 18 | `core/memory/search.py:1089` | L1081–1088 | `self.cursor.execute(sql_snap, (query,) + tuple(temporal_params) + tuple(pc_params) + (limi` | no | — |
| 19 | `core/memory/search.py:1914` | L1814–1913 | `if constants.DIM_RESONANCIA:` | no | — |
| 20 | `core/memory/search.py:761` | L754–760 | `self.cursor.execute(sql_con_pc, (fts_match,) + tuple(temporal_params) + tuple(pc_params))` | no | — |
| 21 | `core/memory/search.py:1495` | L1488–1494 | `self.cursor.execute(` | **sí, lo traga** | OperationalError ×316: no such column: l.contenido |
| 22 | `core/memory/search.py:1654` | L1643–1653 | `self.cursor.execute(` | no | — |
| 23 | `core/memory/search.py:1674` | L1663–1673 | `self.cursor.execute(` | no | — |
| 24 | `core/memory/search.py:1687` | L1680–1686 | `_cjk_nuevas = _cjk_corto.filas(self.cursor, _cjk_terms, overlay_where, overlay_params,` | no | — |
| 25 | `core/memory/search.py:1033` | L931–1032 | `try:` | no | — |
| 26 | `core/memory/search.py:1153` | L1114–1152 | `self.cursor.execute(` | no | — |
| 27 | `core/memory/search.py:1424` | L1406–1423 | `self.cursor.execute(` | no | — |
| 28 | `core/memory/search.py:1550` | L1541–1549 | `self.cursor.execute(` | no | — |
| 29 | `core/memory/search.py:1870` | L1861–1869 | `self.cursor.execute(` | no | — |
| 30 | `core/memory/search.py:1912` | L1901–1911 | `self.cursor.execute(` | no | — |
| 31 | `core/memory_store.py:109` | L98–108 | `from core.schema_status import check_schema_version` | no | — |
| 32 | `core/neurona_asociativa.py:293` | L289–292 | `for a, d in cursor.execute("SELECT concepto, dimension_id FROM largo_plazo_dimensiones").f` | no | — |
| 33 | `core/neurona_asociativa.py:389` | L387–388 | `d.update(r[0] for r in self.cursor.execute(` | no | — |
| 34 | `core/sinapsis.py:255` | L218–253 | `cerebro.cursor.execute(` | no | — |
| 35 | `core/sinapsis.py:316` | L275–315 | `cerebro.cursor.execute(` | no | — |

**Total:** 35 sitios. Tragaron un `OperationalError` en esta sonda: 1. Bloques por los que solo pasó otra excepción, que este handler no captura (p. ej. `GeneratorExit` al cerrar un generador): 1.

Fuera de este inventario, porque no son `except …: pass`: `search.py` L316 (caché del diccionario de dominios que se reintenta en cada búsqueda), `search.py` L45, `synapses.py` L33 y `similitud_conceptual.py` L46 (`int(None)` en el corte por rowid), y `ppmi_vectorizer.py` L153 (F-B). Ver `HALLAZGOS_DEL_MOTOR_K8.md`.
