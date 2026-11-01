# Diagnóstico sanitizado: rutas del authorizer en la verificación C0

Fecha: 2026-11-01. Alcance: lectura estática del código y resumen de los eventos privados del intento. No se repitió la búsqueda, no se consultaron ni publicaron consultas/resultados/recuerdos y no se modificaron el motor ni las bases.

## Hallazgos

| Operación observada | Ruta de código y propósito | Evaluación |
|---|---|---|
| Un `PRAGMA database_list` denegado | `core/memory/search.py:218-225` entra en `expandir_query_con_hub` con el Hub habilitado. En el motor de escala predeterminado, `core/concept_hub.py:742-744, 796-797` conduce a `_expandir_a_escala` y `_puntajes_por_recuerdo`; `core/concept_hub.py:586-592` (`_indice_hubs`) consulta `PRAGMA database_list` para formar la clave de caché. | Lectura de metadatos esperable en esa ruta, no una escritura. Si se deniega, el `except sqlite3.Error` devuelve un índice vacío. La expansión Hub queda sin candidatos y `buscar_por_frase` recibe `hub_expansion=None`; por tanto, la búsqueda deja de aplicar esa parte del scoring/promoción. La ruta es consistente con el evento, aunque el registro del authorizer no guardó stack y no permite atribución de línea absolutamente concluyente. |
| 18 acciones de escritura denegadas contra el catálogo de esquema: 16 `UPDATE` en `main`, un `INSERT` en `main` y un `INSERT` en `temp` | El authorizer registró los códigos SQLite y la base, pero no guardó SQL, stack ni fase (búsqueda o postverificación). La inspección no encontró en la ruta de lectura del Hub una instrucción directa que escriba ese catálogo. | **Sin explicación concluyente.** No es posible asignar responsable, intención o función exacta con la evidencia capturada; no se debe inferir que sea una inicialización inocua. Todos los intentos fueron denegados. |

## Rutas de escritura conocidas que no explican esos eventos

- `core/memory/search.py:2265-2273` puede actualizar memorias dormidas al usar `profundidad="profundo"`; la corrida fue de profundidad `activos`, por lo que esa rama no aplica. Además, aquella operación apunta a la tabla de memoria, no al catálogo de esquema.
- `core/memory/search.py:2404-2422` puede insertar telemetría de búsqueda, pero la corrida fijó `BIORAG_NO_LOG=1`; ese bloque queda desactivado. Tampoco coincide con el objeto registrado por el authorizer.
- `core/concept_hub.py:188-265` contiene DDL de creación/migración y sus funciones CRUD escriben las tablas Hub. Son rutas de mantenimiento; la expansión de consulta que se siguió es de lectura y no demuestra que esas funciones originaran los intentos.

Así, la rama de `PRAGMA database_list` es funcionalmente esperada, pero las acciones sobre el catálogo de esquema siguen sin explicar. Las huellas del volcado y de la copia restaurada quedaron iguales antes/después; la copia fuente se abrió `read-only immutable`. Esto confirma que los intentos fueron rechazados, no que su origen ya esté comprendido.

## Efecto sobre C0 y valor de la prueba

La denegación de `database_list` **sí cambia el C0 configurado con Hub habilitado**: `_indice_hubs` captura el error y devuelve `{}`, lo que elimina la expansión basada en Hub de esa invocación. Por ello, el resultado guardado no representa el comportamiento normal de ese C0. Rechazar las escrituras puede también afectar rutas que dependan de inicialización o estado derivado; como su origen no está identificado, no se puede afirmar equivalencia conductual.

La prueba sigue siendo útil como **diagnóstico de seguridad/fail-closed**: descubrió que el motor intenta acciones que el authorizer bloquea y que puede capturar sus excepciones. No es, en su estado actual, una evaluación válida de ranking ni de comportamiento normal de C0. La única invocación se invalidó; no se presentan métricas ni conclusiones parciales.

## Propuesta para revisión del auditor (sin ejecutar todavía)

1. Mantener denegadas todas las escrituras. No abrir permisos genéricos de `PRAGMA`.
2. Si el auditor confirma que es necesario para conservar la ruta Hub, añadir únicamente una excepción exacta de solo lectura para `PRAGMA database_list` (nombre exacto, sin argumento; sin permitir `data_version`, journal, foreign keys ni otros PRAGMA). Registrar solo que se usó, no sus valores devueltos.
3. Antes de otra búsqueda, instrumentar el arnés —no el motor— para registrar en privado la fase y los marcos Python sanitizados (`módulo/función/línea`) en el momento de cada callback. No capturar SQL, consultas, parámetros, variables locales ni datos de memoria.
4. Como el motor puede capturar una excepción de SQLite, la denegación por sí sola no interrumpe el método Python. Si se autoriza otra prueba, el supervisor debe guardar primero un evento privado de violación y detener el worker antes de cualquier búsqueda siguiente. Mantener máximo 21, cero reintentos y ninguna interpretación de resultados de una corrida que active una guarda.
5. Solo reconsiderar una evaluación de comportamiento cuando las escrituras queden atribuidas y se pruebe que el modo elegido mantiene la semántica buscada sin permitir cambios de datos. Hasta entonces, clasificar el resultado como prueba de aislamiento fallida, no como C0 normal.

No se hizo otra búsqueda. E1 sigue abierto; W pendiente.
