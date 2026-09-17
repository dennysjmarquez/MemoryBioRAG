# Spec 002 — Sustantivos Clave en CLI (biorag.py)

## Contexto y objetivo

El motor central (`core/memory_store.py`) y el servidor MCP (`mcp_server.py`) ya implementan el soporte completo y la validación para `sustantivos_clave`. Sin embargo, la interfaz de línea de comandos de terminal ([biorag.py](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/biorag.py)) aún no expone los flags ni subcomandos correspondientes, impidiendo que usuarios o scripts locales almacenen recuerdos o consulten/actualicen sustantivos clave desde la terminal.

Para garantizar la máxima usabilidad, transparencia y calidad del índice, el CLI no solo debe validar los parámetros, sino también:
1. Guiar pedagógicamente al usuario sobre el **Núcleo Temático** (de qué *trata* el texto vs. lo que meramente *menciona*) tanto en la ayuda como en los errores.
2. Proporcionar visibilidad transversal de los sustantivos clave en todos los comandos de inspección (`corteza`, `listar`, `buscar --completo`, `estado`).
3. Tolerar variaciones de orden de banderas y formato en la línea de comandos de forma robusta.

---

## Usuarios / actores

- **Agentes locales y scripts de terminal:** Ejecutan comandos de consola para consultar, guardar y actualizar recuerdos de forma automatizada.
- **Desarrolladores e investigadores:** Interactúan manualmente con BioRAG desde la terminal para pruebas, inspección y mantenimiento de la memoria.

---

## Historias de usuario

- **H1:** Como usuario del CLI, quiero pasar `--sustantivos-clave` al comando `guardar` para almacenar un nuevo recuerdo con su núcleo temático indexado.
- **H2:** Como usuario del CLI, si omito o ingreso mal el flag `--sustantivos-clave`, quiero recibir un mensaje pedagógico que me explique qué es un sustantivo clave, cómo extraerlo del contenido y un ejemplo concreto de uso.
- **H3:** Como usuario del CLI, quiero consultar la ayuda de `biorag.py` y ver explicada la regla del núcleo temático y la sintaxis de todos los comandos de sustantivos.
- **H4:** Como usuario del CLI, quiero consultar los sustantivos clave de cualquier nodo mediante `biorag.py sustantivos <concepto>`.
- **H5:** Como usuario del CLI, quiero asignar o actualizar los sustantivos de un nodo existente mediante `biorag.py agregar_sustantivos <concepto> "sust1,sust2"`.
- **H6:** Como usuario del CLI, quiero poder incluir `--sustantivos-clave` en `biorag.py buscar` para focalizar la búsqueda en un núcleo temático específico.
- **H7:** Como usuario del CLI, quiero que los comandos de inspección (`corteza`, `listar`, `buscar --completo`, `estado`) me muestren de forma transparente los sustantivos clave de los nodos para auditar la cobertura de la memoria de un solo vistazo.

---

## Requisitos funcionales (criterios de aceptación en EARS)

### Banderas y Sintaxis Principal
- **RF-1:** EL SISTEMA adoptará `--sustantivos-clave` de forma idéntica y consistente como la bandera principal tanto en el comando `guardar` como en el comando `buscar`, permitiendo `--sustantivos` como alias compatible en ambos comandos.
- **RF-2:** EL SISTEMA procesará los flags (`--sustantivos-clave`, `--syn`, `--cat`) independientemente de su posición relativa en la línea de comandos (antes, entre o después de los argumentos posicionales).

### Comando `guardar`
- **RF-3:** CUANDO el usuario ejecuta `biorag.py guardar <clave> <contenido> --sustantivos-clave "s1,s2"`, EL SISTEMA valida y almacena el recuerdo con sus sustantivos normalizados, confirma en la salida visual la lista de sustantivos indexados (ej. `Sustantivos clave: [s1, s2] (2/5)`) y retorna exit code `0`.
- **RF-4:** SI el usuario ejecuta `guardar` sin el flag `--sustantivos-clave` ni `--sustantivos`, ENTONCES EL SISTEMA muestra un mensaje pedagógico explicando el concepto de núcleo temático, la regla de extracción (de 1 a 5 sustantivos nucleares de lo que *trata* el texto), un ejemplo exacto de comando y finaliza con exit code `1`.
- **RF-5:** SI los sustantivos pasados a `guardar` no cumplen las reglas de validación (menos de 1, más de 5, o términos con longitud fuera de [2, 15] caracteres), ENTONCES EL SISTEMA muestra el error de validación detallado, la regla de formato y finaliza con exit code `1`.

### Comando `sustantivos`
- **RF-6:** CUANDO el usuario ejecuta `biorag.py sustantivos <concepto>`, EL SISTEMA busca el concepto en la corteza permanente y muestra en consola sus sustantivos clave formateados con exit code `0`.
- **RF-7:** SI el concepto consultado en `biorag.py sustantivos` no existe en la base de datos, ENTONCES EL SISTEMA muestra `"Error: Concepto '<concepto>' no encontrado en la corteza"` y finaliza con exit code `1`.
- **RF-8:** SI el concepto existe pero no tiene sustantivos asignados (nodo legado), ENTONCES EL SISTEMA muestra `"El concepto '<concepto>' no tiene sustantivos clave asignados."` con indicación de cómo agregarlos vía `agregar_sustantivos` y finaliza con exit code `0`.
- **RF-9:** EL SISTEMA reconocerá `sustantivo` (singular) como alias válido de `sustantivos`.

### Comando `agregar_sustantivos`
- **RF-10:** CUANDO el usuario ejecuta `biorag.py agregar_sustantivos <concepto> "s1,s2"`, EL SISTEMA valida los términos, actualiza el nodo en la base de datos, sincroniza el índice FTS5 y retorna `"Sustantivos clave actualizados para '<concepto>': s1, s2"` con exit code `0`.
- **RF-11:** SI el concepto especificado en `agregar_sustantivos` no existe, ENTONCES EL SISTEMA muestra el error correspondiente y finaliza con exit code `1`.
- **RF-12:** SI los sustantivos pasados a `agregar_sustantivos` son inválidos (0 o más de 5, o términos fuera del rango [2, 15] caracteres), ENTONCES EL SISTEMA muestra el mensaje de error con la explicación pedagógica y finaliza con exit code `1`.
- **RF-13:** EL SISTEMA reconocerá `agregar-sustantivos` y `asignar_sustantivos` como alias válidos.

### Comando `buscar`
- **RF-14:** DONDE se especifique el flag `--sustantivos-clave` o `--sustantivos` en `biorag.py buscar`, EL SISTEMA incorpora dichos términos en la consulta de búsqueda semántica.
- **RF-15:** DONDE se ejecute `biorag.py buscar` con el flag `--completo` o `--asociados`, EL SISTEMA incluirá en el bloque de detalle de cada resultado la línea `Sustantivos clave: s1, s2, ...` si el nodo los posee.
- **RF-16:** SI una búsqueda no arroja ningún resultado, ENTONCES EL SISTEMA incluirá una sugerencia de uso con `--sustantivos-clave` para refinar la consulta.

### Visibilidad en Inspección y Diagnóstico (`corteza`, `listar`, `estado`)
- **RF-17:** CUANDO el usuario ejecuta `biorag.py corteza`, EL SISTEMA muestra para cada nodo listado sus sustantivos clave entre corchetes o como metadato observable.
- **RF-18:** CUANDO el usuario ejecuta `biorag.py listar`, EL SISTEMA incluye los sustantivos clave en el resumen paginado de cada concepto.
- **RF-19:** CUANDO el usuario ejecuta `biorag.py estado`, EL SISTEMA incluye en el reporte de métricas el total y porcentaje de nodos con sustantivos clave asignados (ej. `Nodos con sustantivos clave: X/Y (Z%)`).

### Seguridad, Sanitización y Validación OWASP (A03: Injection & Input Validation)
- **RF-21:** EL SISTEMA sanitizará todas las entradas recibidas por CLI (clave, contenido, sustantivos, sinónimos, frase de búsqueda), eliminando bytes nulos (`\x00`), caracteres de control ASCII y espacios invisibles antes de cualquier operación.
- **RF-22:** EL SISTEMA rechazará inmediatamente con exit code `1` cualquier `sustantivo_clave` que contenga caracteres prohibidos (sólo se permiten caracteres alfanuméricos y guiones bajos `^[a-zA-Z0-9_]+$`), previniendo inyección de comandos o metacaracteres.
- **RF-23:** EL SISTEMA aplicará límites de tamaño estricto (*DDoS / Memory Exhaustion prevention*): longitud máxima de concepto ≤ 200 caracteres, longitud por sustantivo ≤ 15 caracteres (mínimo 2), y contenido ≤ 100,000 caracteres.
- **RF-24:** EL SISTEMA utilizará exclusivamente sentencias SQL parametrizadas (Placeholders `?`) en todas las operaciones de base de datos del CLI y escapará caracteres especiales de sintaxis FTS5 (`"`, `*`, `NOT`, `NEAR`, `{`, `}`) en consultas de búsqueda para evitar inyecciones o excepciones de sintaxis FTS5.

### Ayuda y Documentación Pedagógica en CLI
- **RF-25:** CUANDO el usuario ejecuta `biorag.py` sin argumentos o con `help`/`--help`/`-h`, EL SISTEMA muestra en el docstring de ayuda:
  1. La definición de **Núcleo Temático**: sustantivos esenciales que definen de qué *trata* el recuerdo vs. lo que sólo *menciona*.
  2. La sintaxis de `--sustantivos-clave` en `guardar` y `buscar`.
  3. Los subcomandos `sustantivos` y `agregar_sustantivos`.
  4. La visibilidad de sustantivos en `corteza`, `listar` y `estado`.
  5. Reglas de validación, caracteres permitidos y límites de seguridad.
  6. Ejemplos completos y ejecutables paso a paso.

---

## Requisitos no funcionales

- **RND-1 (Determinismo y UX):** Los mensajes de error deben ser auto-contenidos, legibles y proporcionar siempre la solución inmediata sin requerir consultar el código fuente.
- **RND-2 (Sin regresiones):** Los comandos existentes del CLI (`buscar`, `corteza`, `estado`, `asociar`, `sueno`, `comunicar`, etc.) deben mantener su comportamiento previo sin alteraciones.
- **RND-3 (Tiempo de respuesta):** La ejecución de cualquier comando de CLI debe completarse en menos de 500 ms en operaciones locales.

---

## Casos límite

- **CL-1 (Sustantivos con espacios y tildes):** Las comas con espacios alrededor (`" IA , red neuronal "`) deben limpiarse y las tildes removerse automáticamente en los sustantivos (`"red_neuronal"` si aplica o `"ia"`).
- **CL-2 (Flag sin argumento):** Si se pasa `--sustantivos-clave` al final de la línea sin valor asociado, debe mostrar un error de sintaxis claro sin lanzar excepciones no controladas (`IndexError`).
- **CL-3 (Conceptos con mayúsculas):** Los conceptos pasados a `sustantivos` o `agregar_sustantivos` deben normalizarse a minúsculas para coincidir de forma insensible a mayúsculas.
- **CL-4 (Sustantivos sin comillas):** Si el usuario escribe `--sustantivos-clave palabra1,palabra2` sin comillas, el parser debe procesarlo exactamente igual que con comillas.

---

## Fuera de alcance

- Prompts interactivos por terminal tipo asistente (se mantiene estilo UNIX estándar determinista).
- Generación automática de sustantivos vía TF-IDF en el CLI.
- Migración forzada masiva desde el CLI.

---

## Criterios de finalización

1. Todos los comandos (`guardar --sustantivos-clave`, `sustantivos`, `agregar_sustantivos`, `buscar --sustantivos-clave`, `corteza`, `listar`, `estado`, `help` pedagógico) implementados en [biorag.py](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/biorag.py).
2. Suite completa de tests automatizados de integración de CLI (`tests/test_biorag_cli.py`) con cobertura de todos los 20 RFs, mensajes de error pedagógicos y casos límite en verde.
3. Suite global de regresión (`pytest tests/ -v`) al 100% pasando sin fallos.
