# Informe sintético: instrumentación del authorizer y TEMP views

Fecha: 2026-11-01. Solo se usaron conexiones SQLite `:memory:` con tablas y filas sintéticas. No se abrió la base del proyecto, no se repitió ninguna búsqueda real, no se modificó el motor ni datos.

## Diff incluido en esta revisión

El cambio de código está en `tests/test_sqlite_authorizer_diagnostic_synthetic.py`. Es una prueba autónoma de la instrumentación propuesta, no un cambio a `core/` ni al arnés de búsqueda real.

- Cada evento denegado incluye solo `phase`, nombre de acción SQLite, clase de base (`main`/`temp`/otra) y marcos Python sanitizados (`archivo`, `función`, `línea`). No registra SQL, argumentos de SQLite, valores, locales ni filas.
- Conserva el primer evento: el worker lo envía por IPC; el supervisor lo escribe con creación exclusiva, modo `0600` y `fsync`, y **después** solicita la terminación del worker.
- Excepción de metadatos: permitir `SQLITE_PRAGMA` solo cuando sea `database_list` sin argumento, con `database=None` y `source=None`. Se mantiene además la excepción previa, precisa, para `table_info` de una tabla enumerada en `main`. Todos los demás PRAGMA se deniegan.
- La prueba de TEMP views usa un observador permisivo únicamente en una conexión sintética para ver las acciones que produce SQLite. Está separada del authorizer estricto y no se usa en bases reales.

## Resultados sintéticos

Ejecutado con Python 3.11.2 / SQLite 3.40.1; `unittest`: **3 pruebas, OK**.

1. **Crear y resolver una vista TEMP.** Al crearla, SQLite emitió una acción `SQLITE_CREATE_TEMP_VIEW`, una acción `SQLITE_INSERT` y cinco `SQLITE_UPDATE` asociados al catálogo `temp`. Al resolverla con un `SELECT`, se observaron cero acciones DML contra el catálogo. La prueba resolvió una fila sintética y no publicó su valor.
2. **Allowlist PRAGMA.** Pasó `database_list` sin argumento y `main.table_info` de una tabla enumerada. Denegó cinco formas fuera de allowlist: `foreign_keys`, `journal_mode`, `data_version`, `query_only` y `temp.table_info`. No imprimió las filas de `database_list`.
3. **Supervisor.** Un worker sintético capturó la excepción de un `INSERT` denegado y siguió vivo; el supervisor recibió el primer evento, lo persistió antes de pedir terminación y confirmó que el worker terminó. El evento quedó en modo `0600`, con fase y marcos, sin SQL ni valores. La prueba no fija ni afirma una latencia instantánea: existe una ventana entre el evento, la notificación, la escritura/fsync y la señal de terminación.

Salida resumida de las pruebas:

```text
TEMP view create/resolve: CREATE_TEMP_VIEW=1; catalog DML on temp during create: INSERT=1, UPDATE=5; catalog DML during resolve=0
Strict PRAGMA allowlist: allowed database_list + listed main.table_info; denied other PRAGMA forms=5
Synthetic supervisor: first event durable before termination; worker stopped; mode=0600; instant interruption claimed=false
Ran 3 tests — OK
```

## Relación —y límites de la inferencia— con el intento anterior

El intento real registró 16 `UPDATE` en `main`, un `INSERT` en `main` y un `INSERT` en `temp` contra el catálogo de esquema, además del `PRAGMA database_list`. La prueba sintética muestra que crear una vista TEMP sí puede generar operaciones en el catálogo TEMP; **no demuestra que eso originara los eventos reales**. El patrón de TEMP observado no explica por sí mismo los 16 `UPDATE` ni el `INSERT` de `main`, y el registro real no guardó fase ni marco de llamada. Por tanto, las escrituras reales siguen sin atribución concluyente.

El `PRAGMA database_list` sí tiene una ruta de búsqueda coherente en `core/memory/search.py` → `core/concept_hub.py::_indice_hubs`: sirve para construir la clave de caché del índice Hub. Denegarlo puede dejar vacío ese índice; permitirlo de forma exacta evita abrir PRAGMA general, pero no resuelve los eventos de escritura.

## Supervisor: garantías y límites

La secuencia propuesta es: (1) registrar el primer evento sanitizado en el worker; (2) enviar la notificación; (3) el supervisor persiste el evento y hace `fsync`; (4) solicita `SIGTERM`, espera la salida y, si vence el plazo configurado, escala a `SIGKILL`; (5) no inicia otro worker/búsqueda hasta que el proceso anterior haya terminado y el evento esté preservado. El retardo real depende de scheduling, IPC, I/O y entrega de señales; no se afirma interrupción instantánea. Si no llega la notificación, el supervisor debe agotar un timeout, terminar el worker y marcar la evidencia como incompleta, nunca reintentar.

Este diff y sus resultados son solo para revisión del auditor. No autorizan otra búsqueda real. E1 sigue abierto; W pendiente.
