"""La capa SQLite del motor, dividida por responsabilidad.

Qué problema resuelve: `core/sqlite_runtime.py` tenía 1.091 líneas y cinco
responsabilidades mezcladas. La Constitución (Pilar 9) exige que cada pieza
viva en su propio módulo con una responsabilidad clara y que se comunique por
una interfaz pequeña y explícita.

Cómo está dividida:

| Módulo | Responsabilidad única |
|---|---|
| `config` | Constantes, interruptores, versión del motor y errores propios |
| `epoch` | Época de commit compartida entre procesos |
| `pair_guard` | ¿Se puede probar que el `-wal` es de este `.db`? |
| `tracking` | Conexión y cursor que avisan cuándo se escribe |
| `journal` | Política de modo de diario y diagnóstico |
| `opening` | Las dos puertas: `open_writer` y `open_reader` |

La dirección de dependencias va en un solo sentido:
`opening → journal → tracking → pair_guard → epoch → config`.
Ningún módulo importa hacia arriba, así que cualquiera se puede sustituir sin
tocar los demás (Pilar 9: quitar una pieza no rompe el resto).

**Nada de fuera importa de estos módulos internos.** El punto de entrada es
`core.sqlite_runtime`, que conserva exactamente la misma API pública que antes
de la división; por eso ningún consumidor tuvo que cambiar.

Se dividió en el cambio `specs/009`, con las 55 pruebas de la capa verdes
antes y después. Se hizo *después* de cerrar los tres huecos de la auditora:
primero correcto, luego ordenado.
"""
