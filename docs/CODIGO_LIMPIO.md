# Código limpio y antipatrones en MemoryBioRAG

> **Para quién es esto:** cualquier persona o IA que vaya a escribir código aquí.
> **Qué es:** las convenciones concretas que la Constitución pide pero no detalla.
> La Constitución dice *"nada monolítico"* y *"todo documentado"*; esto dice **cómo**.
> **Última revisión:** 2026-11-07.

## 1. Lo que ya estaba y lo que faltaba

Hay que ser honesto con lo que existe:

| Ya está escrito | Dónde |
|---|---|
| Nada monolítico, evitar acoplamiento, mentalidad hexagonal | `CONSTITUTION.md` Pilar 9, `AGENTS.md` Invariante 6 |
| Todo documentado: qué, por qué ahí, por qué se quitó | Pilar 10, Invariante 7 |
| Cero regresiones, un cambio a la vez, fallos visibles | Pilares 1–3 |
| Cómo partir un archivo en paquete (niveles, nombres, dirección) | `AGENTS.md` §4b |

| **Faltaba** | **Está en** |
|---|---|
| SOLID aplicado a este código, con ejemplos reales | §2 de este documento |
| Catálogo de antipatrones **medidos aquí**, no de manual | §3 |
| Convenciones de nombres, errores, estado global | §4 |
| Deuda técnica congelada y cómo bajarla | §5 |

## 2. SOLID, aplicado a este proyecto

No es teoría: cada principio tiene su caso real en el repo.

### S — Una responsabilidad por pieza
Un módulo debe poder describirse sin usar "y".
- ❌ "conecta a SQLite **y** decide si el `-wal` es ajeno **y** lleva la época de commit" (era `sqlite_runtime.py`).
- ✅ `opening` conecta, `pair_guard` decide, `epoch` lleva la época.

**Prueba rápida:** si el docstring del módulo necesita más de una frase con "y", son dos módulos.

### O — Abierto a extensión, cerrado a modificación
Añadir una señal de ranking no debe obligar a tocar las otras señales.
- Mal: una cadena de `if` que crece con cada señal nueva.
- Bien: una lista de señales con pesos (`core/memory/scoring.py` es el modelo).

### L — Sustituibilidad
Si `open_reader` y `open_writer` devuelven algo que se usa como `conn`, ese algo debe comportarse como una conexión. `_TrackedSQLiteConnection` **es** una subclase de `sqlite3.Connection`, no un envoltorio que imita la mitad de la API. Por eso los consumidores no cambian.

### I — Interfaces pequeñas
Ningún consumidor debería importar 20 nombres para usar uno. Por eso la fachada `core/sqlite_runtime.py` expone `__all__` explícito y lo interno (`_` delante) no se toca desde fuera.

### D — Depender de abstracciones, no de detalles
La dirección `opening → journal → tracking → pair_guard → epoch → constants` es esto en la práctica: la parte alta no sabe cómo se implementa la baja.

**El caso pendiente:** el motor **sí** depende de un detalle, FTS5 (220 usos de SQL propio de SQLite en 24 archivos). Eso es lo que impide cambiar de motor. Ver `docs/patron_repositorio.md`.

## 3. Antipatrones medidos en este repositorio

Datos reales al 2026-11-07, no de manual. Cada uno con su remedio.

| Antipatrón | Medida real | Remedio |
|---|---|---|
| **Archivo Dios** | 11 archivos de `core/` pasan de 600 líneas. El mayor: `core/memory/search.py` con **2.904** | Partir en paquete según §4b de `AGENTS.md`. Se hace **de a uno**, midiendo |
| **Función Dios** | `buscar_por_frase` (24 parámetros), `_calcular_score_hibrido` (22) | Agrupar parámetros en un objeto de consulta (`@dataclass`). **No se toca sin pruebas de comportamiento** |
| **Documentación ausente** | **370** funciones de `core/` sin docstring | Congelado: solo puede bajar (ver §5) |
| **Números mágicos** | Umbrales repartidos en el código en lugar de `constants.py` | Mover a `constants.py` con nombre y comentario del porqué |
| **`except:` desnudo** | Silencia hasta Ctrl-C | Siempre `except Exception` o la excepción concreta |
| **`import *`** | Rompe el rastreo de dependencias | Importar nombres explícitos |
| **Estado global mutable** | `_COMMIT_EPOCHS` en `epoch.py` | Documentado y protegido por `_COMMIT_EPOCH_LOCK`. Si añades uno, igual |
| **Cajón de sastre** | `utils.py`, `helpers.py`, `common.py` | Prohibidos por `AGENTS.md` §4b.2 |

## 4. Convenciones concretas

### Nombres
| Qué | Convención | Ejemplo |
|---|---|---|
| Módulo | `snake_case`, dice qué hace | `pair_guard.py` |
| Clase | `CamelCase` | `SQLiteWriterRuntime` |
| Función | `snake_case`, verbo | `record_pair_state` |
| Constante | `MAYUSCULAS` | `_DEFAULT_BUSY_TIMEOUT_MS` |
| Interno | `_` delante | `_pair_can_be_opened` |
| Interruptor de entorno | `BIORAG_` + área + nombre | `BIORAG_SQLITE_GUARD` |

**Idioma:** el código en inglés o español está mezclado ya; **no se renombra lo
que funciona**. Lo nuevo sigue el idioma del archivo que lo rodea.

### Errores
- **Fallo cerrado** por defecto: ante duda, se rechaza y se deja constancia.
- Excepción propia cuando el llamador puede hacer algo distinto
  (`SQLiteSidecarConflictError`); `ValueError`/`TypeError` para uso incorrecto.
- **El mensaje dice qué pasó, qué no se tocó y qué hacer.** Ejemplo vivo:
  el de `SQLiteSidecarConflictError` nombra el archivo de constancia y la guía.
- **Nunca** un `except` vacío que se coma el error.

### Comentarios
- El comentario dice **por qué**, no qué. El qué ya lo dice el código.
- Si un bloque necesita un comentario para entenderse, primero se intenta
  extraer a una función con nombre.
- **Todo bloque raro lleva su porqué.** Ejemplo real en `tracking.close()`:
  *"un cursor sin cerrar mantiene bloqueada la base"*. Sin ese comentario,
  alguien lo borra en seis meses y vuelve el fallo.

### Pruebas
- Una prueba por cada fallo corregido, y **debe reproducir el fallo**
  (proceso real si hace falta), no simularlo.
- Nombre en forma de frase: `test_caida_con_wal_vivo_recupera_los_datos`.
- Si una prueba necesita `monkeypatch`, que parchee **donde se lee** el valor.

## 5. La deuda, congelada y a la vista

La deuda existe y no se arregla de golpe sin riesgo. Se **congela** y solo se
permite que baje:

```bash
python3 scripts/auditar_arquitectura.py            # informe completo
python3 scripts/auditar_arquitectura.py sqlite --strict   # un paquete, estricto
```

`tests/test_arquitectura.py` falla si la cifra **sube**. Estado al congelar:
114 funciones sin docstring en `core/`. `core/sqlite` está en **cero**.

**Regla de convivencia:** el archivo que toques, lo dejas mejor de como estaba
(una docstring, un nombre, un número mágico). No hace falta una campaña; hace
falta que nadie empeore.

## 6. Lo que se puede hacer sin miedo y lo que no

| Sí | No |
|---|---|
| Añadir docstrings y comentarios del porqué | Cambiar firmas de funciones del motor sin pruebas |
| Extraer una función pura a su módulo | Mover código y renombrar a la vez |
| Añadir una prueba que reproduce un fallo | "Limpiar" código que no entiendes del todo |
| Mover constantes a `constants.py` | Cambiar un peso de ranking (requiere medición y OK de Dennys) |
| Partir un archivo en paquete con fachada | Tocar la base del usuario o sus archivos auxiliares |
