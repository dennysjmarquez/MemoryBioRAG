# `core/sqlite/` — la capa de base de datos del motor

> **Para quién es esto:** cualquier persona o IA que llegue al proyecto y necesite saber **dónde está parada**.
> Regla de oro (Constitución, Pilares 9 y 10): cada pieza dice **qué es, por qué existe, qué aporta y con qué se conecta**. Si agregas, quitas o apagas un archivo, **actualiza esta tabla en el mismo cambio**.
> Las conexiones salen del código, no de la memoria: compruébalas con `python3 scripts/mapa_dependencias_core.py sqlite`.
> Última revisión: 2026-11-07.

## Cómo encaja en el sistema

```
memory_store.py ──► core/sqlite_runtime.py (fachada) ──► core/sqlite/*  ──► SQLite
   y otros 6                                         │
   consumidores                                      └─ un único punto de conexión:
                                                        open_writer / open_reader
```

- **`core/sqlite_runtime.py`** (un nivel arriba) es una **fachada**: solo reexporta. La implementación vive aquí.
- **Dirección de dependencias, en un solo sentido:**

```
opening → journal → tracking → pair_guard → epoch → config
```

Ningún módulo importa hacia arriba. Eso es lo que permite quitar o sustituir una pieza sin tocar las demás (Pilar 9).

## Por qué está dividido

Antes era **un solo archivo de 1.091 líneas** con cinco responsabilidades mezcladas. La Constitución pide que cada pieza viva en su propio módulo con una responsabilidad clara.

La división se hizo **después** de cerrar los tres huecos de la auditora: primero correcto, luego ordenado. Se midió como cualquier otro cambio: las 50 pruebas de la capa verdes antes y después, y la suite completa sin cambios (729 passed).

**Nada de esto cambió el comportamiento.** Los 54 bloques de código se movieron literalmente; se verificó con una comparación automática bloque por bloque contra el original (`0 diferencias`).

## Las piezas

| Archivo | Qué es | Por qué existe / qué aporta | Se conecta con | Estado |
|---|---|---|---|---|
| `config.py` | Constantes, los dos interruptores (`BIORAG_SQLITE_GUARD`, `BIORAG_SQLITE_FORCE_OPEN`), la versión del motor y los tres errores propios | Es la base del paquete: lo que todos necesitan y nadie más produce. Aquí se lee la versión **efectiva** de SQLite | Todos los demás. Usa `core.paths` | Activo |
| `epoch.py` | Época de commit compartida entre procesos, con sello en disco y lock entre procesos | Varios procesos escriben la misma base; necesitan saber si otro publicó sin abrir SQLite | `tracking` (ventana de commit), `opening` (identidad de ruta) | Activo |
| `pair_guard.py` | **Decide si un `.db` y su `-wal` pueden abrirse juntos**, leyendo solo cabeceras | Es la protección contra aplicar un diario de otra versión de la base. Nunca mueve, renombra ni borra: ante duda, rechaza y deja constancia con sha256 | `opening` (antes de cada `connect`), `tracking` (reanota tras cada commit) | Activo. Se apaga con `BIORAG_SQLITE_GUARD=0` |
| `tracking.py` | Conexión y cursor instrumentados: avisan cuándo una sentencia escribe | Para publicar la época en el momento justo sin que cada consumidor tenga que acordarse | `journal` lo instala como `factory` | Activo |
| `journal.py` | Política de **modo de diario** y diagnóstico del motor | SQLite < 3.51.3 tiene el WAL-reset bug; aquí se decide en qué modo puede abrirse cada conexión | `opening.open_writer` / `open_reader` | Activo |
| `opening.py` | Las dos puertas: `open_writer` y `open_reader` | Único punto de conexión del motor. Tenerlas juntas garantiza que ninguna ruta se salte las comprobaciones | Los 7 consumidores de fuera | Activo |

## Los siete consumidores (fuera del paquete)

`core/memory_store.py`, `core/adn_conceptual.py`, `core/dmn_engine.py`,
`core/feedback_implicito.py`, `core/neocortex_teleologico.py`,
`core/ppmi_hybrid_search.py` y `dashboard-neuro-visor/backend/server.py`.

Todos importan de `core.sqlite_runtime` (la fachada), **nunca** de los módulos internos.

## Dos reglas al tocar esto

1. **Si añades una función pública, reexpórtala en `core/sqlite_runtime.py`.** Lo que empieza por `_` es interno.
2. **Las funciones que las pruebas simulan se leen siempre en su módulo de origen**, no se importan por valor en otro módulo. Por eso `opening`, `journal` y `tracking` tienen pequeños reenvíos. Si se copiaran al importar, parchear un nombre surtiría efecto en unos sitios y no en otros, y las pruebas mentirían.

## Dos fallos que se encontraron al dividir (y se corrigieron)

Quedan escritos para que nadie los reintroduzca:

- **Los decoradores se pierden al mover código.** `@contextmanager` en tres funciones de `epoch` y `@dataclass(frozen=True)` en `SQLiteWriterRuntime`. Sin ellos, un `with` falla con *"'generator' object does not support the context manager protocol"*. Se detectó comparando el AST del original con el nuevo.
- **Un cursor abierto mantiene bloqueada la base.** `execute()` crea un cursor por sentencia y no lo cierra; ese cursor mantiene viva la conexión hasta que pasa el recolector, y mientras tanto el `-wal` no se consolida y la siguiente apertura falla con *"database is locked"*. Se corrigió haciendo que `close()` cierre también los cursores que la conexión entregó. **Este era un fallo latente del código anterior**, no de la división: la división solo lo hizo visible.
