# Spec 009 — Dividir `core/sqlite_runtime.py` en un paquete

## Qué problema resuelve

`core/sqlite_runtime.py` llegó a **1.091 líneas** con cinco responsabilidades
mezcladas: constantes y versiones, época de commit, pertenencia del par
`-wal`/`.db`, instrumentación de la conexión y política de journal. La
Constitución (Pilar 9) dice: *"Nada monolítico. Cada pieza vive en su propio
módulo con una responsabilidad clara."*

El sistema va a crecer. Un archivo de más de mil líneas con cinco motivos
distintos es difícil de auditar, y esta es precisamente la pieza que la
auditora externa está revisando.

## Qué NO resuelve

- **No cambia comportamiento.** Cero líneas de lógica nueva.
- **No toca la base del usuario** ni sus archivos auxiliares.
- **No es la refactorización del motor entero.** Sigue habiendo 220 usos de SQL
  específico de SQLite en 24 archivos; eso es el trabajo del puerto y el
  adaptador (ver `docs/patron_repositorio.md`).

## Decisión

Dividir en `core/sqlite/` (paquete) con seis módulos, dejando
`core/sqlite_runtime.py` como **fachada que reexporta**. Así ningún consumidor
cambia sus imports.

```
opening → journal → tracking → pair_guard → epoch → constants
```

Dirección única, sin ciclos. Verificado con la herramienta del propio repo
(`scripts/mapa_dependencias_core.py sqlite`): ningún módulo interno es usado
desde fuera del paquete, y `open_writer` solo se expone por la fachada.

## Por qué ahora y no antes

Primero se cerraron los tres huecos de la auditora (`97b43c0`). Dividir código
con un fallo abierto mezcla dos cambios y hace la auditoría más difícil. La
regla del repo es un cambio medido a la vez (Invariante 2).

## Cómo se midió

| Medida | Antes | Después |
|---|---|---|
| Pruebas de la capa | 50/50 | 50/50 |
| Suite completa | 729 passed | 729 passed |
| Diferencias bloque a bloque contra el original | — | **0** |
| Funciones sin docstring | 12 | **0** |
| Archivo más grande del paquete | 1.091 | 334 (`epoch.py`) |

## Riesgos que aparecieron y cómo se corrigieron

1. **Decoradores perdidos al mover código**: `@contextmanager` ×3 y
   `@dataclass(frozen=True)` ×1. Sin ellos, `with` falla. Detectado comparando
   el AST del original con el nuevo, no a ojo.
2. **Cursor que retiene la conexión**: `execute()` crea un cursor por sentencia
   y no lo cierra. Ese cursor mantiene viva la conexión hasta que pasa el
   recolector, y mientras tanto la base queda bloqueada (*"database is locked"*).
   **Era un fallo latente del código anterior**; la división solo lo hizo
   visible. Se corrigió en `tracking.close()`.
3. **Las pruebas parcheaban la fachada**: al separar módulos, el `monkeypatch`
   sobre `sqlite_runtime` dejó de surtir efecto dentro del paquete. Se corrigió
   apuntando las pruebas a donde se lee el valor, y dejando reenvíos en los
   módulos que lo necesitan.

## Criterio de aceptación

- [x] Las 50 pruebas de la capa verdes.
- [x] Suite completa sin cambios (729 passed, mismos 7 fallos preexistentes).
- [x] Cero funciones sin docstring en el paquete.
- [x] Sin ciclos de importación.
- [x] Ningún consumidor externo cambió su código.
- [x] `core/sqlite/README.md` con la tabla de piezas.
