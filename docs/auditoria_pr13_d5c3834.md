# Auditoría PR #13: fast path `d5c3834`

## Decisión

**No fusionar `d5c3834` tal como está.** La optimización acelera el caso sin cambios, pero en dos controles sintéticos deja pasar cambios del archivo principal que `2818e72` detectaba. Uno es una alteración in-place; el otro, un checkpoint raw que no altera el tamaño del archivo principal. Es una regresión en la detección pretendida, aparte de la ventana commit/publicación que ya se documentó. No demuestra corrupción ni se usaron datos reales.

No está demostrado que sea imposible mejorar la ventana anterior ni que criptografía sea la única opción; cualquier propuesta debe evaluar sus garantías y costes. Si el usuario decide aceptar la ventana, eso no equivale a aceptar silenciosamente esta regresión nueva.

## Estado y pruebas

PR #13 head exacto `d5c38343f112628dde57709b5ac56ddacd1e1503`; GitHub lo informó abierto, `CLEAN`, `MERGEABLE`, y 10 jobs verdes en dos ejecuciones. `git diff --check 2818e72 d5c3834` pasó. En Linux ejecutamos **59 focales, todas pasan**; no repetimos la suite completa del candidato. La cifra 813/0 completa procede del operador/CI.

Dos versiones idénticas salvo el diff `2818e72..d5c3834`, en árboles aislados. Las pruebas usan SQLite estándar Linux 3.40.1 y `pysqlite3==0.6.1` SQLite 3.53.4 inyectado temporalmente como `sqlite3`; no es el runtime real de producción ni una prueba de compatibilidad completa. Para DELETE se fuerza el clasificador a 3.45.1 y para WAL a 3.51.3: solo decide la política de journal, no cambia el motor binario.

### 1. Alteración in-place de tamaño constante

DB sintética en DELETE, tabla y fila de prueba creadas por el motor, lectura protegida inicial. Un descriptor de archivo reescribe una cadena de prueba por otra del mismo largo y preserva tamaño e inode; se fuerza mtime distinto con `os.utime` para que la diferencia de metadata de la firma sea inequívoca. El contenido es sintético; la sonda no trata de inferir el efecto sobre filas almacenadas o caché.

- `2818e72`: `SQLiteDatabaseIdentityChangedError` en la siguiente lectura protegida.
- `d5c3834`: la lectura devuelve normalmente `(1,)` sin alerta, en ambos runtimes de prueba.

El fast path comprueba solo data_version, época y tamaño principal; retorna antes de leer la firma que incluía mtime/ctime y encabezado. Un cambio externo del archivo puede no notificar data_version de SQLite. Cambiar mtime expresamente sirve para un control determinista; no se afirma que SQLite o el sistema siempre actualicen timestamps de una determinada manera.

### 2. Checkpoint sin cambio de tamaño

En una DB sintética WAL se crea una tabla y se hace checkpoint PASSIVE coordinado, se realiza un UPDATE coordinado de una página existente, y se actualiza el snapshot con una lectura protegida. Luego una conexión raw ejecuta `PRAGMA wal_checkpoint(PASSIVE)`, resultado `(0, 1, 1)`, y se verifica que el tamaño del archivo principal no cambió.

- `2818e72`: la lectura protegida posterior lanza `SQLiteDatabaseIdentityChangedError`.
- `d5c3834`: la lectura retorna normalmente sin alerta, en ambos runtimes de prueba.

El checkpoint no coordinado no implica corrupción ni es necesariamente dañino; el operador había documentado como política detectarlo y fallar cerrado. Esta prueba muestra que **tamaño constante no es suficiente para aplicar esa política**. Mantener los checkpoints coordinados es una restricción operativa, no prueba de que otros consumidores respeten el protocolo.

## Rendimiento

Microprueba propia (un runtime, caché caliente, WAL sintético 18.589.472 bytes, 30 `SELECT count(*)` protegidos): `2818e72` **1,628 s**, `d5c3834` **0,010 s**. La mejora en este escenario es real; no es benchmark de producción ni justifica afirmar que se conservan todas las protecciones. Evitar resolverlo a costa de alertas perdidas.

Evidencia privada con sonda pareada y 59 pruebas focales: `auditoria_pr13_d5c3834.tar.gz`, Drive ID `1eT4aVNhUcWuRDuwp_Q7RaDGQTmZD4r54`, SHA-256 `e154b53a092bb4e037c409f53114d73590245274cc98fe32793448bb7b1e5ed8`. El script de microprueba de rendimiento se ejecutó por separado. No se hizo merge ni se modificó `master`.
