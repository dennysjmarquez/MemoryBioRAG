# Reconstrucción de la auditoría PR #13 sobre `d5c3834`

> **Qué es este documento.** El informe original lo escribió la auditora externa
> en su rama (commit `7609d18`, archivo `docs/auditoria_pr13_d5c3834.md`). No
> estaba en esta rama. A petición suya se reconstruye aquí.
> **Qué es mío y qué es suyo.** Las secciones 1–3 reproducen **su informe**,
> citado: son sus palabras y sus cifras, no mías. Las secciones 4–7 son la
> respuesta y el estado actual de esta rama.
> **Última revisión:** 2026-11-07.

## 1. Su decisión (citada)

> **No fusionar `d5c3834` tal como está.** La optimización acelera el caso sin
> cambios, pero en dos controles sintéticos deja pasar cambios del archivo
> principal que `2818e72` detectaba. Uno es una alteración in-place; el otro, un
> checkpoint raw que no altera el tamaño del archivo principal. Es una regresión
> en la detección pretendida, aparte de la ventana commit/publicación que ya se
> documentó. No demuestra corrupción ni se usaron datos reales.

Precisión suya que hay que conservar: *"Si el usuario decide aceptar la ventana,
eso no equivale a aceptar silenciosamente esta regresión nueva"*. Correcto: son
dos asuntos distintos y no se arreglan con la misma decisión.

## 2. Los dos casos que reprodujo (cifras de su informe)

| Caso | `2818e72` (antes) | `d5c3834` (la optimización) |
|---|---|---|
| Alteración in-place con tamaño e inodo constantes | `SQLiteDatabaseIdentityChangedError` en la lectura siguiente | Devuelve `(1,)` **sin alerta**, en los dos runtimes de prueba |
| Checkpoint raw `PASSIVE` sin cambio de tamaño (`(0, 1, 1)`) | Lanza el error | Devuelve **sin alerta** |

**Su diagnóstico, que es la clave del arreglo:** *"tamaño constante no es
suficiente para aplicar esa política"*. El *fast path* comprobaba solo
`data_version`, época y **tamaño** del principal; retornaba antes de leer la
firma que incluía `mtime`/`ctime` y el encabezado. Un cambio externo del archivo
puede no notificar `data_version` a SQLite.

**Su medición de rendimiento:** WAL sintético de 18.589.472 bytes, 30
`SELECT count(*)` protegidos: `2818e72` **1,628 s**; `d5c3834` **0,010 s**. La
mejora era real; el problema era el precio.

**Sus condiciones de medida, que limitan el alcance** (se recogen para no
exagerar lo probado): árboles aislados, Linux, SQLite 3.40.1 del sistema y
`pysqlite3==0.6.1` (SQLite 3.53.4) inyectado temporalmente. **No es el runtime
real de producción.** Para DELETE forzó el clasificador a 3.45.1 y para WAL a
3.51.3: eso decide la política de journal, no cambia el motor binario. No repitió
la suite completa del candidato; el 813/0 procedía del operador/CI.

Evidencia suya: `auditoria_pr13_d5c3834.tar.gz`, SHA-256
`e154b53a092bb4e037c409f53114d73590245274cc98fe32793448bb7b1e5ed8`.

## 3. La ventana commit/publicación

Ya venía documentada en `d5c3834` y **no es una regresión**: entre el commit de
SQLite y la publicación de la firma, un cliente sin protocolo puede confirmar y
la firma atestigua un estado que ya incluye su escritura. Es una carrera real que
ningún candado cooperativo cierra contra quien no acata el protocolo. **Sigue
abierta** y requiere decisión de diseño, no otro parche.

## 4. Qué se hizo (commit `4747ca8`)

Se acepta el diagnóstico completo. **El *fast path* se retiró.**

La sonda barata pasó a ser **`size + mtime + ctime`**, y se usa solo como
**condición necesaria** para saltar el hash. **Nunca decide sola**: si no
coincide, se ejecuta la firma completa, que es la que decide.

Precisión que se comprobó en el código y corrige una impresión incompleta: la
sonda **no cubre solo el archivo principal, cubre también el `-wal`**
(`_cheap_file_probe`, `core/memory_store.py`). Se amplió a propósito: una
alteración directa dentro del WAL deja intactos todos los campos del principal,
así que una sonda limitada al principal informaba "nada cambió" mientras el WAL
estaba alterado (`auditoría 4747ca8`, ver §6.2).

Su frase —"tamaño constante no es suficiente"— es literalmente el motivo del
cambio de criterio.

**Rendimiento recuperado sin perder detecciones:** 30 lecturas sobre un WAL de
14,7 MB en **0,0105 s**, igual que el *fast path* defectuoso. Su medición fue
1,628 s → 0,010 s; la mejora se conserva.

## 5. Las pruebas, y sus resultados

| Prueba | Qué fija |
|---|---|
| `test_alteracion_in_place_de_tamano_constante_se_detecta` | Caso 1: reescritura con mismo tamaño e inodo, forzando `mtime`; **debe lanzar** `SQLiteDatabaseIdentityChangedError` |
| `test_checkpoint_raw_sin_cambio_de_tamano_se_detecta` | Caso 2: checkpoint `PASSIVE` de cliente sin protocolo con tamaño constante; **debe fallar cerrado** |
| `test_lectura_sin_cambios_no_rehashea_el_wal` | El coste: 30 lecturas sobre WAL > 5 MB en menos de 0,5 s |

Las tres llevan su informe nombrado en el docstring, para que la trazabilidad no
dependa de la memoria de nadie.

**Coste declarado de `test_checkpoint_raw_sin_cambio_de_tamano_se_detecta`:**
lleva `BIORAG_SQLITE_FORCE_OPEN=1` porque su política es **rechazar un checkpoint
externo**, y la capa nueva rechaza antes de llegar a lo que la prueba mide. Es
deliberado: el precio de fallar cerrado.

## 6. Lo que este documento no resuelve

1. **La ventana commit/publicación sigue abierta** (§3). No se ha tocado.
2. **`test_alteracion_directa_del_wal_se_detecta` falló de forma intermitente**
   en una ejecución completa de la suite. No reprodujo en aislamiento, ni en dos
   mitades, ni en tres ejecuciones completas posteriores. **Se declara no
   explicado, no resuelto.** Una prueba intermitente no es una prueba en la que
   se pueda confiar hasta que se explique.
3. **El runtime de producción no está cubierto** por las pruebas de CI, igual que
   señaló ella en §2. La CI usa el SQLite de cada plataforma, no el binario real
   de despliegue.

## 7. Revisión independiente sobre `88ef43f` (dos hallazgos, ambos reales)

La revisión independiente encontró dos fallos que las 60 pruebas de SQLite no
cubrían. **Los dos se reprodujeron y se corrigieron.**

### Hallazgo 1 — Un `-wal` ajeno se aceptaba si el principal coincidía

**Causa:** el caso 3 de `_pair_can_be_opened` aceptaba con solo comparar el
sha256 del **principal** con el anotado. Eso descarta que hayan sustituido el
archivo principal, **pero no que el `-wal` sea de otra base**.

**El escenario exacto que lo dispara:** un proceso hace commit y **se cae**. El
principal queda intacto y el registro sigue siendo válido. En ese hueco se
coloca un `-wal` de otra base y se aplicaba en silencio sin alerta.

**Arreglo:** la **sal de la cabecera del `-wal`** identifica al diario y ya
estaba anotada; ahora **participa en la decisión**. Si el principal coincide
pero la sal no es la anotada, ese diario no es el que había cuando se verificó
el par: se rechaza.

**Lo que esto conserva:** tras una caída legítima el diario es el mismo que
había en el último commit propio (misma sal), así que se sigue aceptando y
SQLite recupera los datos. La recuperación tras caída sigue probada y verde.

**Prueba:** `test_wal_ajeno_con_principal_intacto_se_rechaza`. Reproduce una
caída real (`subprocess` + `kill`) y coloca el diario ajeno. **Falla sin el
arreglo, pasa con él** (comprobado con `git stash`).

### Hallazgo 2 — `open_reader` abría el par que `open_writer` rechazaba

**Causa:** la comprobación de pertenencia solo estaba en `open_writer`.
`open_reader` no comprobaba nada.

**Por qué importa:** un lector también abre el par y SQLite aplica el `-wal`
al abrirlo, igual que en escritura. La lectura veía datos de otra versión por
la puerta de al lado, aunque la de escritura estuviera cerrada.

**Arreglo:** `open_reader` aplica la **misma** política, antes de abrir:
`SQLiteSidecarConflictError` con constancia forense, y `FORCE_OPEN` como vía de
escape autorizada.

**Prueba:** `test_open_reader_rechaza_el_mismo_par_que_open_writer`. **Falla sin
el arreglo, pasa con él.**

### Lo que esta revisión demuestra sobre el método

Las 60 pruebas de SQLite pasaban y los dos fallos seguían ahí. La razón es que
las pruebas cubrían los caminos que yo había imaginado. Una revisión
independiente busca los que no imaginé. **Eso no lo sustituye ninguna prueba
propia**, y es el argumento más fuerte que hay para que la revisión exista.

## 8. Estado de la rama

- Commit revisado por la revisión independiente: `88ef43f0382cf31d2091f748598c045e810ae6f6`.
- Los dos hallazgos de §7 están corregidos en el commit siguiente a ese.
- Sin merge a `master`. Sin tocar la base real ni sus archivos auxiliares.
- La capa vive en `core/sqlite/` (seis módulos) con `core/sqlite_runtime.py` como
  fachada. Cero lógica nueva en esa división: los 54 bloques se movieron
  literalmente y se compararon con el AST (`0 diferencias`).
