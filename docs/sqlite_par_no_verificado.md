# Cuando el motor se niega a abrir la base

Este documento explica qué hace BioRAG cuando encuentra un archivo `-wal` que no
puede atribuir con certeza a la base que tiene al lado, qué hacer en ese caso, y
cómo se apaga o se sustituye toda la capa de protección.

## El problema, en una frase

SQLite guarda los cambios recientes en un archivo aparte, el `-wal`, y los aplica
a la base al abrirla. Si ese `-wal` viene de **otra versión** de la base (por
ejemplo, de otra rama de git, o de una copia anterior), SQLite lo aplica igual y
la base termina con datos que no le corresponden. No avisa: el resultado es
estructuralmente válido, `integrity_check` dice `ok`, y aun así el contenido es
el equivocado.

Por eso la comprobación se hace **antes de abrir**, y ante la duda el motor no
abre.

## Qué ocurrió en el caso que originó esto

1. La base estaba versionada en git; el `.db` sí, el `-wal` no.
2. Se guardó información y se cambió de rama enseguida.
3. Git sustituyó el `.db`, pero el `-wal` de la rama anterior se quedó.
4. Al reabrir, SQLite aplicó ese diario ajeno.

El archivo principal no estaba dañado: solo sobraba el diario. Borrar el `.db`
era innecesario y destructivo; borrar los adyacentes era lo correcto.

## Qué hace el motor ahora

Al abrir comprueba cuatro cosas, todas de solo lectura sobre los archivos:

1. **¿Hay `-wal` con contenido?** Si está vacío o no existe, no hay nada que
   aplicar: se abre. Es el estado que deja un cierre ordenado.
2. **¿El modo de journal del archivo es WAL?** Se lee de la cabecera, sin abrir
   SQLite. Si la base usa otro modo pero hay un `-wal` al lado, ese archivo no
   es suyo.
3. **¿El archivo principal es exactamente el que se anotó?** Se compara el
   sha256. Si coincide, un diario nuevo viene de una escritura externa
   legítima y se abre.
4. **En cualquier otro caso no hay prueba de pertenencia.** Se rechaza con
   `SQLiteSidecarConflictError`.

**En ningún caso se mueve, renombra ni borra un archivo.** Si rechaza, deja una
constancia con los sha256, tamaños y fechas del `.db`, del `-wal` y del `-shm`
en `<base>.biorag-pair-state.conflicto.json`.

## Qué hacer cuando aparece el aviso

El mensaje te dice dónde está la constancia. Los pasos son:

1. **No borres nada todavía.** Copia los tres archivos juntos (`.db`, `-wal`,
   `-shm`) a otro sitio. Con la constancia JSON puedes comprobar que copiaste
   exactamente lo que había.
2. **Decide qué versión de la base quieres.** Si vienes de cambiar de rama, lo
   normal es quedarte con el `.db` actual y descartar el `-wal` heredado: ese
   diario es de la otra rama.
3. **Comprueba la copia antes de tocar nada.** Abre la copia con
   `sqlite3 copia.db "PRAGMA integrity_check; SELECT COUNT(*) FROM ..."` y mira
   si el contenido es el que esperas.
4. **Actúa sobre la copia, nunca sobre el original**, y solo cuando sepas qué
   versión es la buena.

### Para continuar aceptando el riesgo

Si ya revisaste la constancia y decides que el `-wal` sí corresponde a esa base:

```bash
BIORAG_SQLITE_FORCE_OPEN=1 python tu_script.py
```

Eso abre el par tal cual, deja constancia del hecho en el log y reanota el
estado. Queda registrado quién lo autorizó (la variable) y cuándo.

## Por qué no se detecta todo

Se comprobó, con las auditorías del PR #13, que **no existe una señal que separe
un `-wal` ajeno de uno legítimo**:

| Señal | Resultado |
|---|---|
| `quick_check` sobre una copia | Un diario ajeno puede pasarlo |
| Sal de la cabecera del WAL | Identifica al diario; si se conserva, no cambia |
| Tamaños y fechas | Coinciden entre pares legítimos y ajenos |
| Comparación estricta de contenido | Rechaza también mantenimiento legítimo |

Por eso la política es cerrada: ante un principal que cambió con un diario vivo,
no se adivina, se pide confirmación. **El precio es que a veces pedirá
confirmación en un mantenimiento normal.** Es deliberado: preferimos una
interrupción que una base con datos de otra versión.

## Consolidar al cerrar

Para que el caso no se produzca, el motor ejecuta `wal_checkpoint(TRUNCATE)` al
cerrarse: el `.db` queda completo y el diario vacío. Un `-wal` con datos deja de
sobrevivir al cierre y no puede quedar emparejado con otra versión al copiar o
versionar los archivos por separado.

Es best-effort: si no se puede consolidar (base en solo lectura, otro proceso
trabajando, plataforma sin soporte) se registra y se cierra igual.

**Lo que no cubre:** si el proceso se cae, el `.db` y el `-wal` siguen siendo de
la misma base, porque los commits son suyos. En ese caso SQLite debe aplicar el
diario, y lo hace: los datos se recuperan.

## La causa de fondo: la base en el control de versiones

Este problema nace de versionar el `.db` en git y no sus archivos auxiliares.
**La solución de raíz es sacar la base del repositorio** y respaldarla aparte.
Mientras siga en git, cada cambio de rama puede sustituirla.

Recomendación: `MemoryBioRAG_Data/*.db` fuera de git, con copias de seguridad
periódicas y un `PRAGMA wal_checkpoint(TRUNCATE)` antes de cualquier copia
manual.

## Apagar o sustituir la capa

La protección está centralizada en `core/sqlite_runtime.py`. Ningún otro módulo
del motor abre conexiones: todos pasan por `open_writer` / `open_reader`.

### Apagarla sin tocar código

```bash
BIORAG_SQLITE_GUARD=0 python tu_script.py
```

Con la capa apagada, el motor abre siempre y deja de consolidar al cerrar: se
comporta como un cliente SQLite normal. Los valores aceptados para desactivarla
son `0`, `false`, `no` y `off`.

### Sustituirla

Las funciones que forman la capa son:

- `guard_enabled()` — interruptor.
- `_pair_can_be_opened()` — la decisión.
- `record_pair_state()` — la anotación.
- `_save_conflict_forensics()` — la constancia.

Para cambiar de motor de base de datos hay que sustituir `core/sqlite_runtime.py`
y la capa de acceso de `core/memory_store.py`. El resto del motor usa el `cursor`
del objeto, así que la frontera existe, pero **no es una abstracción completa**:
el SQL con `PRAGMA`, `sqlite_master`, `rowid` y FTS está repartido en 24
archivos. Migrar a otro motor es un trabajo de porte, no un cambio de
configuración.

## Escenarios cubiertos por las pruebas

En `tests/test_sqlite_generation.py`:

- `test_caida_con_wal_vivo_recupera_los_datos`
- `test_wal_ajeno_tras_cambio_de_rama_no_se_aplica`
- `test_consolidacion_imposible_no_rompe_el_cierre`
- `test_la_capa_se_puede_desactivar`
- `test_force_open_es_la_via_de_escape_autorizada`
- `test_al_cerrar_no_queda_un_wal_con_datos`
