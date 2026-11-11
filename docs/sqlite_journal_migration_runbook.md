# Runbook: DB existente en WAL y runtime SQLite vulnerable

**Este runbook no se ejecutó contra una DB real.** La transición fue ejercitada únicamente en tests con DBs temporales.

## Decisión preferida

Actualizar todos los procesos escritores a un runtime SQLite corregido y verificar en cada proceso `sqlite3.sqlite_version` y `sqlite_source_id()`. BioRAG no instala ni reemplaza SQLite automáticamente. Los releases clasificados corregidos por `core.sqlite_runtime` son 3.51.3+, 3.50.7 y 3.44.6 con el backport correspondiente.

## Si se necesita migrar el journal a DELETE

1. Aprobar una ventana de mantenimiento y detener ordenadamente **todos** los escritores y lectores que mantengan handles abiertos. No matar procesos ni borrar `-wal`/`-shm` manualmente.
2. Crear y validar un backup consistente con el procedimiento corporativo de SQLite. No copiar solo el `.db` mientras WAL tenga commits pendientes.
3. Repetir primero la operación sobre una copia descartable. En un único proceso, con runtime vulnerable, usar la API explícita:

   ```python
   from core.sqlite_runtime import open_writer

   conn = open_writer(
       ruta_a_la_copia,
       allow_existing_journal_transition=True,
       consumer="offline_journal_migration",
   )
   try:
       modo = conn.execute("PRAGMA journal_mode").fetchone()[0].lower()
       integridad = conn.execute("PRAGMA integrity_check").fetchone()[0]
       if modo != "delete" or integridad != "ok":
           raise RuntimeError(f"Verificación fallida: journal={modo}, integrity={integridad}")
   finally:
       conn.close()
   ```

4. Comparar en la copia los conteos y verificaciones funcionales acordados para la aplicación. Si SQLite no obtiene el lock exclusivo, el factory falla cerrado; no volver a intentar borrando sidecars.
5. Solo después de aprobar la copia, planificar la misma operación para la DB autorizada, con backup restaurable y la misma ventana sin consumidores. Verificar runtime, journal e integridad antes de reabrir servicios.

`allow_existing_journal_transition=True` es opt-in deliberado y hoy es una API Python; **no hay todavía una CLI corporativa de migración ni una ejecución operativa sobre DB de usuario**. Los tests `test_runtime_vulnerable_transicion_wal_a_delete_conserva_filas` y `test_runtime_vulnerable_no_degrada_wal_si_otra_conexion_sigue_abierta` verifican conservación de filas, transición explícita y fallo cerrado con otra conexión activa usando fixtures.
