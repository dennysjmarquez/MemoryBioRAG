# Seguridad: OWASP Top 10 aplicado a MemoryBioRAG

> **Regla inviolable.** Ningún cambio entra sin pasar esta lista.
> Está en `CONSTITUTION.md` como **Pilar 12** y en `AGENTS.md` como
> **Invariante 9**. Si un cambio choca con esto, se para el cambio, no la regla.
> **Última revisión:** 2026-11-07.

## 1. Antes de implementar: la pregunta obligatoria

**¿Este cambio introduce una entrada nueva de datos, una salida nueva, una
conexión nueva o un permiso nuevo?** Si la respuesta es "sí" a cualquiera, hay
que recorrer las diez categorías de §3 y dejar constancia en el PR.

Si la respuesta es "no" a las cuatro (por ejemplo, mover código a otro módulo,
añadir un docstring, extraer una función pura), se declara así y no hace falta
más. **La regla no es burocracia para todo: es obligatoria cuando cambia la
superficie.**

## 2. La superficie real de este proyecto

No es una web genérica. Lo que hay que proteger es esto:

| Superficie | Dónde | Riesgo principal |
|---|---|---|
| **MCP por stdio** | `core/mcp_server/` | Que el agente pase datos que se conviertan en SQL o comandos |
| **SQLite local** | `core/sqlite/` | Inyección SQL, archivos auxiliares manipulados |
| **FastAPI del dashboard** | `dashboard-neuro-visor/backend/server.py` | Endpoints sin autenticar, parámetros de ruta sin validar |
| **Rutas del sistema de archivos** | `core/paths.py`, `BIORAG_PATH` | Que una ruta apunte fuera del directorio previsto |
| **Variables de entorno** | `constants.py` de cada paquete | Valores no validados que cambian comportamiento |
| **Todo lo que escribe en la base** | `memory_store`, daemons | Denegación de servicio por escrituras sin tope |

## 3. Las diez, con el caso concreto de aquí

### A01 — Control de acceso roto
- Los endpoints del dashboard **declaran explícitamente** si requieren
  autenticación. Un endpoint público lleva **justificación escrita**.
- El dashboard **escucha en local**. Exponerlo en red es una decisión explícita,
  documentada, nunca un efecto colateral.
- **Comprobar:** ¿el cambio añade un endpoint? ¿Está en la tabla de §2 de la spec?

### A02 — Fallo criptográfico
- Aquí no hay contraseñas ni TLS que gestionar: **no se inventa criptografía**.
- Se usan `hashlib` y `secrets` de la biblioteca estándar. **Nunca** un hash
  casero para algo sensible.
- Lo que se guarda en la base es memoria del usuario: **no se envía a ningún
  servicio externo**. Si algún día se envía, es un cambio de superficie mayor.

### A03 — Inyección
Esta es **la categoría crítica** en este proyecto.

- **SQL:** siempre parámetros (`?`). Un `f-string` en SQL **solo** es aceptable
  para un **identificador o lista de placeholders que el propio código
  construye** (`?,?,?`), nunca para un valor que venga de fuera.
  ```python
  # ✅ bien: los valores van por parámetros
  cursor.execute(f"... WHERE id IN ({placeholders})", ids)
  # ❌ nunca: valor de fuera metido en el texto
  cursor.execute(f"... WHERE concepto = '{concepto}'")
  ```
- **Comandos de shell:** `subprocess` con lista de argumentos y `shell=False`.
  Prohibido `shell=True` con datos externos.
- **Rutas:** toda ruta que venga de fuera se resuelve y **se comprueba que
  queda dentro** del directorio permitido antes de usarla.

### A04 — Diseño inseguro
- **Fallo cerrado**: ante duda, se rechaza y se deja constancia (esto ya es la
  política de `pair_guard`).
- Toda operación que escribe tiene **tope**: cuántos registros, cuánto tiempo.

### A05 — Configuración incorrecta
- Los `PRAGMA` y modos de journal los decide el motor (`core/sqlite/journal.py`),
  **no cada llamador**.
- Mensajes de error: dicen **qué pasó y qué hacer**, sin volcar rutas internas
  del sistema más allá de lo necesario para diagnosticar.
- **Ningún secreto en el repositorio.** El `.env.local` está ignorado por git.

### A06 — Componentes vulnerables
- SQLite: la política de versión ya existe (`is_wal_reset_vulnerable`).
  **Añadir una dependencia obliga a justificar versión y mantenimiento.**
- Antes de subir una dependencia nueva: ¿está mantenida? ¿tiene alternativa en
  la biblioteca estándar? Este proyecto presume de **Python puro**, así que la
  respuesta por defecto es "no añadir".

### A07 — Fallos de identificación y autenticación
- Hoy no hay usuarios que autenticar en el motor. Si un cambio introduce
  identidad, **entra en esta lista y se revisa aparte**.

### A08 — Fallos de integridad de datos y software
- **El `.db` y sus sidecars son datos del usuario.** Ningún código los mueve,
  renombra ni borra sin autorización explícita (ya es la política de `pair_guard`).
- Toda migración de esquema es **idempotente** y no destructiva.

### A09 — Fallos de registro y monitorización
- Los rechazos **se registran**, con el dato justo para diagnosticar.
- La constancia forense (`*.conflicto.json`) es parte de esto: si algo se
  rechaza, queda rastro.

### A10 — Falsificación de peticiones del lado del servidor (SSRF)
- El motor **no hace peticiones de red** en el camino de búsqueda. Es una
  decisión de diseño (Constitución §1: cero APIs externas en el path).
- Si un cambio introduce una llamada de red, es un cambio de superficie mayor:
  se revisa entero y se documenta.

## 4. La lista de comprobación, para copiar en el PR

```markdown
## Seguridad (OWASP Top 10)
- [ ] Este cambio no añade entrada, salida, conexión ni permiso nuevos
      (si los añade, responder las diez de abajo)
- [ ] A01 Acceso: endpoint nuevo → declarado público o autenticado, con justificación
- [ ] A03 Inyección: ningún valor externo llega a SQL, shell o ruta sin validar
- [ ] A04 Fallo cerrado: ante duda se rechaza; la operación tiene tope
- [ ] A05 Configuración: sin secretos; PRAGMA y modos los decide el motor
- [ ] A06 Dependencias: ninguna nueva, o justificada
- [ ] A08 Integridad: no se mueve, renombra ni borra nada del usuario
- [ ] A09 Registro: el rechazo deja rastro
```

## 5. Lo que se midió al crear esta regla (estado real, 2026-11-07)

| Comprobación | Resultado |
|---|---|
| SQL con `f-string` en `core/` | **62**, revisados uno a uno con el AST. **Todos** interpolan solo placeholders (`?`), nombres de tabla constantes o enteros del propio código. **Ninguno** mete un valor de fuera. Cifra congelada: `tests/test_arquitectura.py` falla si crece |
| `subprocess` con `shell=True` | 0 en el motor |
| Endpoints del dashboard | FastAPI, escucha en local |
| Secretos en el repo | `.env.local` ignorado por git |
| Dependencias externas en el path de búsqueda | 0 (Python puro, decisión de diseño) |
| `except:` desnudo | 0 (se corrigieron los 7 que había) |

Detalle de la revisión de los 62: el 100% interpola placeholders (`ph`,
`placeholders`, `','.join('?' * n)`), nombre de tabla constante (`tabla`,
`_TABLA`, `_VOCAB`) o un entero calculado (`sql_limit`, `PRAGMA cache_size`).
Los casos que parecían sospechosos se comprobaron en su origen:
`_resolver_categoria_id` devuelve un **entero** del caché de categorías, nunca
el texto que llegó de fuera.

**No se declara el proyecto "seguro":** se declara **medido en estos puntos**.
Una auditoría de seguridad completa es un trabajo aparte y más profundo.

## 6. Cómo se aplica, sin parar el proyecto

La regla no bloquea el avance: lo hace **verificable**.

- En un cambio pequeño (docstring, refactor sin superficie nueva): una línea
  diciendo "no añade superficie".
- En un cambio con superficie nueva: la lista de §4 completa.
- **Si aparece una duda fundada, el cambio se para y se documenta el porqué.**
  Esa duda es información, no un obstáculo.
