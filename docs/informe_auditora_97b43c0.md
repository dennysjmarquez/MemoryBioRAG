# Informe para la auditora — cierre de los tres huecos de `59ef8a4`

Commit que se somete a revisión: **`97b43c0`** sobre `59ef8a4`.
Rama: `arena/a6f83961-memorybiorag`. PR abierto, sin mergear.

## 1. Su objeción y lo que se hizo con ella

Su frase que resolvió el diseño fue esta:

> "no mover ni borrar el WAL no garantiza que no pueda dañar la base: SQLite
> podría aplicarlo al abrirla"

Correcta, y fue el punto de giro. `59ef8a4` solo evitaba **producir** el WAL
huérfano. Si ya existía, se aplicaba igual. La reparación estaba a medias.

`97b43c0` cambia el criterio: **la protección es no abrir**. La decisión se
toma antes de `sqlite3.connect`, leyendo únicamente las cabeceras de los
archivos. Si no hay prueba de que el `-wal` pertenece al `.db` que tiene al
lado, el motor no abre.

## 2. Los tres escenarios, medidos

### Escenario 1 — caída del proceso

Proceso hijo real con `subprocess.Popen`, commit hecho, `kill()` sin cierre
ordenado. WAL resultante: **1 709 832 bytes**.

Resultado: la capa **deja abrir** y SQLite recupera. Las 2 filas están ahí,
`integrity_check` = `ok`.

Es deliberado. Tras una caída, el `-wal` es de esa misma base: contiene
commits suyos que aún no se consolidaron. Rechazarlo sería **perder datos**.
La política no puede tratar igual un diario propio pendiente que un diario
ajeno.

Prueba: `test_caida_con_wal_vivo_recupera_los_datos`. Usa `subprocess` +
`kill()`; una versión anterior que cerraba conexiones a mano era una prueba
mal planteada y se reescribió.

### Escenario 2 — agente abierto al cambiar de rama

Se reproduce el caso original: `.db` de `branch_B`, `-wal` de `branch_A`.

Resultado: **RECHAZADO** con `SQLiteSidecarConflictError`. El principal no
cambia un byte. El `-wal` no se mueve. Queda constancia con sha256 de los
tres archivos en `<base>.biorag-pair-state.conflicto.json`.

Prueba: `test_wal_ajeno_tras_cambio_de_rama_no_se_aplica`.

### Escenario 3 — consolidación que no se puede completar

Base en solo lectura al cerrar (`chmod 444`).

Resultado: el cierre **no rompe**; se registra y se cierra. Los datos siguen
legibles.

Prueba: `test_consolidacion_imposible_no_rompe_el_cierre`.

## 3. Cómo decide, sin abrir SQLite

Todas las comprobaciones son de solo lectura sobre archivos:

1. ¿Hay `-wal` con contenido? Si no, se abre: no hay nada que aplicar.
2. ¿El journal mode de la cabecera es WAL? Se lee el byte 18 de la cabecera.
   Si la base no está en WAL pero hay un `-wal` al lado, ese archivo no es suyo.
3. ¿El sha256 del principal coincide con el anotado tras el último commit
   propio? Si coincide, un diario nuevo solo puede venir de una escritura
   externa legítima, y se abre.
4. Cualquier otro caso: **no hay prueba de pertenencia**, se rechaza.

En ningún caso se mueve, renombra ni borra un archivo. Ante duda, originales
intactos.

## 4. Coste aceptado, y por qué

Una sustitución de la base **y** un checkpoint externo legítimo producen el
mismo estado observable. Se probó separarlos y no hay señal que lo permita:

| Señal probada | Por qué no sirve |
|---|---|
| `quick_check` sobre una copia | Un diario ajeno puede pasarlo |
| Sal de la cabecera del WAL | Identifica al diario, no a la base |
| `size` + `mtime_ns` + `ctime_ns` | No identifica contenido |
| sha256 estricto del principal | Rechaza también mantenimiento legítimo |

Por eso se falla cerrado y se pide confirmación. Dos pruebas existentes
(`test_reuso_de_wal_tras_checkpoint_no_oculta_commit_raw`,
`test_checkpoint_raw_sin_cambio_de_tamano_se_detecta`) ahora llevan
`BIORAG_SQLITE_FORCE_OPEN=1` porque su política es precisamente rechazar un
checkpoint externo. Y `test_runtime_vulnerable_no_degrada_wal_si_otra_conexion_sigue_abierta`
también lo lleva, porque abre un par con `-wal` vivo de otro cliente: la capa
lo considera no verificado antes de llegar a lo que esa prueba mide.

**Eso es el coste, y es el que usted señaló que había que asumir.**

## 5. Vías de escape

- `BIORAG_SQLITE_GUARD=0` — apaga la capa entera. No comprueba y no consolida.
- `BIORAG_SQLITE_FORCE_OPEN=1` — autoriza abrir un par no verificado; deja
  constancia y reanota el estado.

Pruebas: `test_la_capa_se_puede_desactivar`, `test_force_open_es_la_via_de_escape_autorizada`.

## 6. Documentación

`docs/sqlite_par_no_verificado.md`. El mensaje de error la referenciaba y el
archivo no existía; era un cabo suelto señalado en la revisión anterior.

## 7. Estado de las pruebas

- `tests/test_sqlite_generation.py`: **29/29**
- `tests/test_sqlite_runtime.py` + generación + hilos: **54/54**
- Suite completa: **728 passed, 7 failed, 89 errors**.
  Los 7 fallos y los 89 errores son **preexistentes** y ajenos a este cambio:
  dependencias ausentes en este entorno (`test_memory_core`,
  `test_qa_multilingue_e3a`, `test_escala_motor`, `test_evidence_convergence`,
  `test_sustantivos_clave_recordar`). No tocan SQLite ni el motor.

Hubo un fallo intermitente de `test_alteracion_directa_del_wal_se_detecta`
en la suite completa que no reproducía en aislamiento ni en dos mitades. En
dos ejecuciones completas posteriores no volvió a aparecer. **Lo declaro como
no explicado**, no como resuelto: si vuelve a salir, se investiga.

## 8. Lo que este cambio NO hace

- No toca `master`.
- No toca la base real ni sus archivos auxiliares.
- No integra `prototypes/sqlite_coordination/`.
- No arregla la causa de fondo: **la base sigue versionada en git**. Mientras
  lo esté, cada cambio de rama puede sustituirla. La recomendación está en el
  documento: sacar la base del repositorio. Eso es una decisión suya y de
  Dennys, no la tomo yo.

## 9. Preguntas abiertas para usted

1. ¿Acepta el coste de fallar cerrado cuando un checkpoint externo legítimo
   cambia el principal? Es la única forma que se encontró de no adivinar.
2. ¿Considera suficiente `FORCE_OPEN` como vía de escape, o preferiría una
   confirmación interactiva?
3. ¿La base debe salir del control de versiones? Es la causa raíz y es lo
   único que evita el problema de origen en lugar de detectarlo.
