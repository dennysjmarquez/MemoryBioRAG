# Patrón repositorio: qué haría falta para cambiar de base de datos

Nota de arquitectura. Responde a la pregunta: *"hoy SQLite, mañana Postgres"*.

## Sí, es el patrón repositorio (y va dentro de la hexagonal)

Son dos cosas distintas que se complementan:

- **Arquitectura hexagonal** organiza la aplicación alrededor del dominio y pone
  adaptadores en los bordes. El motor de memoria es el núcleo; la base de datos
  es un detalle que vive en un borde.
- **Patrón repositorio** es la pieza concreta que hace ese borde: el dominio pide
  `guardar_recuerdo(...)` o `buscar_similar(...)`, y no sabe si detrás hay
  SQLite, Postgres o un archivo.

La regla que lo define: **el dominio nunca escribe SQL**. Si escribe SQL, el
repositorio es decorativo.

## Dónde está el sistema hoy

Medido sobre el árbol actual:

| Qué | Cuánto |
|---|---|
| Puntos de conexión dentro del motor (`sqlite3.connect`) | **1 archivo** (`core/sqlite_runtime.py`) |
| Conexiones directas fuera del motor (scripts, benchmarks, docs) | ~303 |
| Archivos con SQL específico de SQLite (`PRAGMA`, `sqlite_master`, `rowid`, FTS5) | 24 |
| Usos de ese SQL específico | ~220 |

Traducido: **el motor tiene una sola puerta, pero el SQL está repartido por toda
la casa.** Abrir conexiones ya está centralizado. El acoplamiento que queda no
es el `connect`: es el dialecto.

## Por qué cambiar de motor no es un `if`

Esto es lo que rompe una migración ingenua:

- `PRAGMA journal_mode`, `wal_checkpoint`, `busy_timeout` — no existen en
  Postgres; allí son configuración de servidor.
- `sqlite_master` — en Postgres es `information_schema`.
- `rowid` — en Postgres no hay; hace falta una clave explícita.
- **FTS5** — la búsqueda de texto de SQLite. En Postgres sería `tsvector` o
  `pg_trgm`, con otra semántica de ranking. Esto es lo más caro: no es traducir
  sintaxis, es reproducir comportamiento de búsqueda.
- Transacciones y concurrencia: SQLite serializa escrituras con un lock de
  archivo; Postgres usa MVCC. El código que hoy asume "un escritor a la vez"
  tendría que revisarse.
- El bug del WAL y toda la capa de esta rama **son específicos de SQLite**. Con
  otro motor desaparecen y con ellos la protección: por eso la capa es
  desactivable con `BIORAG_SQLITE_GUARD=0`.

## Qué habría que construir, en orden

1. **Definir el puerto.** Una interfaz con las operaciones que el dominio
   necesita de verdad, no una copia de la API de SQLite. Por ejemplo:
   `guardar`, `obtener`, `buscar_lexico`, `buscar_vectorial`, `relacionar`,
   `transaccion`.
2. **Un adaptador SQLite** que implemente el puerto. Es en su mayoría mover
   código existente detrás de la interfaz, no reescribirlo.
3. **Sacar el SQL del dominio.** Los 24 archivos con SQL específico se van
   bajando al adaptador. Este es el trabajo largo, y es mecánico.
4. **Un adaptador Postgres**, escrito contra el puerto y validado con la misma
   batería de pruebas que el de SQLite.
5. **Pruebas contra el puerto**, no contra SQLite. Las que hoy usan `PRAGMA` o
   `sqlite_master` tendrían que expresarse como comportamiento observable.

## Lo importante para decidir

- **La capa de esta rama no estorba a ese plan.** Está toda dentro de
  `core/sqlite_runtime.py`, se apaga con una variable de entorno, y ningún otro
  módulo depende de ella. Es exactamente lo que un adaptador de SQLite
  contendría.
- **No conviene hacer el patrón repositorio ahora** si el objetivo es empezar a
  usar el sistema. Es una refactorización de varios días que no cambia lo que el
  sistema sabe hacer. Se puede hacer después, sin deshacer nada de esto.
- **Lo que sí conviene ahora** es no añadir SQL nuevo fuera del motor. Es la
  regla barata que mantiene la puerta única mientras llega la refactorización.

## Respuesta corta

Sí, es el patrón repositorio. Desactivar la protección de SQLite ya es cambiar
una variable. Cambiar de motor es un trabajo real: hay una sola puerta de
conexión, pero unos 220 usos de SQL propio de SQLite en 24 archivos, y la
búsqueda FTS5 no se traduce sola. Es un port con interfaz y adaptadores, no un
cambio de configuración.
