# Spec 005 — Reconsolidación de nodos

## Contexto y objetivo

Hoy `actualizar` solo permite corregir un nodo dentro de una ventana de 15 minutos anclada a su `creado_en` (×3 con sesión activa); un nodo viejo está fuera de ventana para siempre. El único camino alternativo —volver a guardar con la misma clave— **concatena** (`contenido_viejo + " | Actualización: nuevo"`), de modo que el texto anterior nunca se elimina: nodos como `version_actual_biorag` acumulan cadenas con versiones vencidas, el nombre sigue disparando el piso de match exacto en el scoring, y el texto viejo sigue pesando en BM25. Paralelamente, hoy no hay ninguna señal que diga "este nodo está vencido" ni en `recordar` ni en el ciclo de sueño.

Esta especificación introduce la **reconsolidación**: un nodo se vuelve reescribible cuando vuelve a la mente de un agente en una sesión (no solo al nacer), gana un modo `reemplazar` que sustituye en vez de concatenar (con historial forense antes/después), y el ciclo de sueño —mediante reglas deterministas, sin LLM y sin intervención humana— marca los nodos `vencido` para que `recordar` los señale y el agente los cure reescribiéndolos. Los nodos `version_*` vencidos existentes se curan por este mismo camino en las primeras sesiones, sin backfill manual.

Orden de implementación fijo: la **004 (suite blindada)** se implementa y aprueba primero; esta spec se implementa después.

## Usuarios / actores

- **Agente de IA (Athena, Artemis, Hermes, clientes MCP):** ejecuta `recordar`, interpreta las marcas `vencido` y `ventana_abierta`, y reescribe con `actualizar(modo='reemplazar')` cuando tiene la versión vigente en su sesión.
- **Ciclo de sueño (consolidación):** componente del sistema que aplica las reglas de marcado `vencido` sin LLM.
- **Dennys / mantenedor:** audita el historial forense (antes/después, timestamp, autor) y revisa las alarmas `anomalo=1`.
- **Harness de evaluación:** verifica el gate de no-regresión (tests, suite QA, golden).

## Historias de usuario

- **H1 (Curación sin intervención humana):** Como agente, quiero que `recordar` me señale los nodos vencidos y con ventana abierta, para reescribirlos con la versión vigente que tengo en sesión sin pedirle nada a un humano.
- **H2 (Reconsolidación al recordar):** Como agente, quiero poder corregir un nodo de hace meses en la misma sesión en que lo acabo de traer con `recordar`, para que la memoria diga la verdad vigente.
- **H3 (Auditoría forense):** Como mantenedor, quiero que cada reescritura guarde antes y después con timestamp y autor, para saber qué cambió, cuándo y quién.
- **H4 (Detección automática de vencidos):** Como mantenedor, quiero que el ciclo de sueño marque solo, con reglas configurables y sin LLM, los nodos cuyo contenido está podrido, para que ningún nodo vencido quede sin señal.

## Requisitos funcionales (criterios de aceptación en EARS)

### Ventana de reconsolidación (anclada a la sesión, no a `ultimo_acceso`)

- **RF-1 (Dirigido por evento):** CUANDO un agente con sesión activa (`contexto_inicio` sin `contexto_fin`) recibe un nodo como resultado de `recordar`, EL SISTEMA habilitará `actualizar` sobre ese nodo para ese agente durante el resto de la sesión, sin importar la antigüedad del nodo.
- **RF-2 (Ubicuo):** EL SISTEMA mantendrá la ventana actual por `creado_en` (default 900 segundos, ×3 con sesión activa) para nodos recién creados y para nodos no devueltos por `recordar` en la sesión.
- **RF-3 (No deseado):** SI un agente intenta `actualizar` un nodo que no le fue devuelto por `recordar` en su sesión activa y cuya edad supera la ventana por `creado_en`, ENTONCES EL SISTEMA responderá `status="fuera_de_ventana"` con el mensaje actual: `"Nodo '<concepto>' tiene <N> minutos — supera la ventana de corrección (<M> min<con sesión activa>). Usá biorag_aprender para crear un nodo nuevo y biorag_vincular para conectarlo."`.
- **RF-4 (No deseado):** SI un agente sin sesión activa intenta `actualizar` un nodo fuera de la ventana por `creado_en`, ENTONCES EL SISTEMA responderá `status="fuera_de_ventana"` sin habilitar la vía por sesión.
- **RF-5 (No deseado):** SI un agente intenta `actualizar` un nodo devuelto por `recordar` a **otro** agente en la misma ventana de tiempo, ENTONCES EL SISTEMA tratará la elegibilidad como propia de cada agente (no compartida).

### Modo `reemplazar` e historial forense

- **RF-6 (Dirigido por evento):** CUANDO `actualizar` se invoca con `modo='reemplazar'` dentro de una ventana abierta, EL SISTEMA sustituirá el contenido anterior por el contenido nuevo sin concatenar.
- **RF-7 (Ubicuo):** EL SISTEMA mantendrá `modo='append'` como valor por defecto de `actualizar`, con el comportamiento de concatenación actual sin cambios.
- **RF-8 (Dirigido por evento):** CUANDO `actualizar` modifica el contenido de un nodo (append o reemplazar), EL SISTEMA registrará en el historial forense: versión anterior, versión nueva, timestamp y autor (valor del parámetro `agente`).
- **RF-9 (Ubicuo):** EL SISTEMA expondrá `modo` en `actualizar` como parámetro con valores `'append'` (default) y `'reemplazar'`; cualquier otro valor producirá `status="error"` con mensaje `"modo inválido: '<valor>'. Valores permitidos: append, reemplazar."`.
- **RF-10 (No deseado):** SI el parámetro `agente` no se provee en una invocación de `actualizar`, ENTONCES EL SISTEMA registrará el autor como `'desconocido'` en el historial forense.

### Salvaguarda de acortamiento brusco

- **RF-11 (Dirigido por evento):** CUANDO se aplica `modo='reemplazar'` sobre un nodo cuya última reescritura tiene más de 30 días y el contenido nuevo es más de un 50 % más corto que el anterior (longitud_nueva < 0.5 × longitud_anterior), EL SISTEMA registrará la entrada del historial forense con `anomalo=1` y devolverá en la respuesta un diff resumido con `longitud_anterior`, `longitud_nueva`, `preview_anterior` (primeros 200 caracteres) y `preview_nuevo` (primeros 200 caracteres).
- **RF-12 (No deseado):** SI la condición del RF-11 se cumple, ENTONCES EL SISTEMA aplicará la actualización igualmente; la salvaguarda nunca bloquea, solo avisa.
- **RF-13 (No deseado):** SI el contenido nuevo está vacío y el nodo supera los 30 días, ENTONCES EL SISTEMA aplicará el reemplazo con `anomalo=1` y el diff devuelto mostrará `longitud_nueva=0`.

### Sincronización de índices tras reemplazar

- **RF-14 (Ubicuo):** EL SISTEMA mantendrá el índice de búsqueda plena (FTS) sincronizado tras cada reemplazo: una búsqueda posterior devolverá el nodo con su contenido nuevo, y el texto reemplazado no será localizable como contenido del nodo.
- **RF-15 (Ubicuo):** EL SISTEMA preservará los `sustantivos_clave` del nodo tras un reemplazo de contenido, salvo que se indiquen explícitamente en la misma operación.
- **RF-16 (Ubicuo):** EL SISTEMA mantendrá sincronizados `sinonimos` y `categoria` del nodo tras un reemplazo (sin pérdida).

### Marcado automático `vencido` en el ciclo de sueño (reglas, sin LLM)

- **RF-17 (Dirigido por evento):** CUANDO el ciclo de sueño procesa un nodo activo cuyo nombre contiene `actual`, `version` o `vigente` y su última reescritura (creación o último reemplazo) tiene más de N días, EL SISTEMA marcará el nodo como `vencido`.
- **RF-18 (Dirigido por evento):** CUANDO el contenido de un nodo activo contiene 2 o más ocurrencias del marcador `" | Actualización:"`, EL SISTEMA marcará el nodo como `vencido` en el ciclo de sueño, independientemente de su nombre o antigüedad.
- **RF-19 (Ubicuo):** EL SISTEMA configurará N mediante la variable de entorno `BIORAG_VENCIMIENTO_DIAS` con default `30`.
- **RF-20 (Ubicuo):** EL SISTEMA ejecutará el marcado con reglas deterministas, sin llamadas a modelos de lenguaje y sin red.
- **RF-21 (No deseado):** SI un nodo no cumple ninguna de las condiciones de los RF-17 y RF-18, ENTONCES EL SISTEMA no le aplicará el marcado `vencido` (la ausencia de marca es el estado por defecto).

### Señal en `recordar` y curación automática

- **RF-22 (Dirigido por evento):** CUANDO `recordar` devuelve un resultado, EL SISTEMA incluirá en cada nodo los campos booleanos `vencido` y `ventana_abierta`.
- **RF-23 (Ubicuo):** EL SISTEMA evaluará `ventana_abierta` como verdadera cuando el nodo sea elegible para `actualizar` por el agente consultante en la sesión actual (creado dentro de la ventana por `creado_en`, o devuelto por `recordar` a ese agente en esta sesión).
- **RF-24 (Dirigido por evento):** CUANDO un nodo marcado `vencido` con `ventana_abierta=true` es reescrito mediante `actualizar(modo='reemplazar')`, EL SISTEMA limpiará la marca `vencido` de forma automática.
- **RF-25 (No deseado):** SI un nodo `vencido` se modifica solo con `modo='append'`, ENTONCES EL SISTEMA conservará la marca `vencido` (concatenar no cura el vencimiento).
- **RF-26 (Dirigido por evento):** CUANDO el ciclo de sueño reescribe un nodo por su mecanismo de concatenación existente, EL SISTEMA no alterará su marca `vencido` salvo que el contenido resultante deje de cumplir las condiciones de marcado.

### No-regresión del scoring

- **RF-27 (Ubicuo):** EL SISTEMA conservará intacto el cálculo de scoring y ranking: ninguna funcionalidad de esta spec modificará pesos, señales ni orden de resultados.

## Requisitos no funcionales

- **RNF-1:** El marcado `vencido` se ejecuta dentro del ciclo de sueño existente, sin dependencias fuera de la stdlib, sin red y sin nuevos requerimientos de hardware.
- **RNF-2:** El marcado es determinista: misma base + misma configuración → mismos nodos marcados en cada corrida.
- **RNF-3:** La ventana de reconsolidación no alarga el tiempo de respuesta perceptible de `recordar` (sin llamadas externas en su evaluación).
- **RNF-4:** `actualizar` y `recordar` conservan sus firmas públicas existentes; los campos nuevos (`modo`, `vencido`, `ventana_abierta`) son aditivos y no rompen clientes existentes.
- **RNF-5:** El historial forense usa el mecanismo de auditoría ya existente en el sistema (sin nuevo almacén externo).

## Casos límite

- **CL-1:** Nodo con `creado_en` nulo o 0 → se trata como fuera de ventana por `creado_en` (comportamiento actual preservado); solo la vía por sesión puede habilitarlo.
- **CL-2:** Varios agentes con sesión activa recuerdan el mismo nodo → la elegibilidad de `actualizar` es individual por agente (RF-5).
- **CL-3:** Dos reescrituras concurrentes del mismo nodo en la misma ventana → última escritura gana; cada una genera su entrada de historial forense.
- **CL-4:** Nodo marcado `vencido` pero sin ventana abierta para el agente consultante → `recordar` lo devuelve con `vencido=true, ventana_abierta=false`; `actualizar` responde `fuera_de_ventana`.
- **CL-5:** Nodo con exactamente 1 ocurrencia de `" | Actualización:"` → no cumple RF-18 (se requieren 2 o más).
- **CL-6:** Nodo con nombre `version_*` y edad ≤ N días → no cumple RF-17; solo se marca si cumple RF-18.
- **CL-7:** Página 2 o N de resultados de `recordar` → los campos `vencido` y `ventana_abierta` aparecen en todos los nodos de todas las páginas.
- **CL-8:** Reemplazo con contenido vacío sobre nodo ≤ 30 días → se aplica sin `anomalo=1` (la salvaguarda solo aplica a nodos > 30 días).
- **CL-9:** `contexto_fin` cierra la sesión → los nodos habilitados por sesión dejan de ser elegibles (RF-1 deja de aplicar); un nuevo `contexto_inicio` habilita una ventana nueva.
- **CL-10:** Nodo ya marcado `vencido` que vuelve a cumplir las condiciones tras un reemplazo parcial → RF-24 manda: el reemplazo limpia la marca; el siguiente ciclo de sueño re-evalúa.

## Fuera de alcance

- **IDF en `auto_vincular`** (caché de IDF, umbral, candidatos) — va en la 006.
- **Sinapsis provisionales `sugerida`** y vinculación hebbiana por uso — va en la 006.
- **Co-activación de sesión para auto-vinculación** — va en la 006.
- **Backfill manual de nodos `version_*`** — eliminado del alcance: los nodos se curan por el camino automático (sueño → `recordar` → reemplazo) en las primeras sesiones.
- **Cambios en scoring, pesos, señales o ranking** — prohibidos (RF-27).
- **Cambiar el comportamiento de concatenación del ciclo de sueño** — el mecanismo de fusión existente (`" | Actualización:"`) se conserva; solo se marca, no se modifica.
- **Cambiar el default de `ordenar_por`** en búsquedas.
- **Modo de reemplazo masivo o automático de contenido** — la reescritura siempre la ejecuta un agente que dispone de la versión vigente; el sistema nunca reescribe contenido por sí solo.
- **Spec 004 (suite blindada)** — dependencia de orden, no parte de esta spec.

## Criterios de finalización

1. Spec 004 (suite blindada) implementada y aprobada **antes** de iniciar la implementación de 005.
2. 264/264 tests unitarios en verde (`pytest tests/ -v`).
3. Suite QA 875/875 **idéntica** al resultado previo — misma casuística ganada, no "dentro de umbral".
4. Golden de 921 casos con **0 diferencias de score** a 4 decimales y Top-5 idéntico caso a caso.
5. Fuzzing/adversariales 33/33 en verde.
6. Cero cambios en el cálculo de scoring (verificable por el punto 4).
7. Demo manual del flujo principal en base real, con evidencia pegada:
   a. Ejecutar ciclo de sueño → nodos `version_*` cumpliendo RF-17/RF-18 quedan marcados `vencido` (conteo y lista).
   b. `recordar` de un nodo marcado → campos `vencido=true` y `ventana_abierta=true` visibles en la respuesta.
   c. `actualizar(modo='reemplazar')` con la versión vigente → contenido sustituido (sin `" | Actualización:"` nuevo), marca `vencido` limpiada (RF-24), historial forense con antes/después + timestamp + autor.
   d. Repetir (a): el nodo reescrito **no** vuelve a marcarse.
   e. Salvaguarda RF-11: aplicar un reemplazo >50 % más corto sobre un nodo >30 días y mostrar `anomalo=1` + diff en la respuesta, con la operación aplicada.
8. Los nodos `version_*` históricos de la base productiva quedan sin marca `vencido` tras las primeras sesiones de sueño + reescritura (curación sin backfill manual).

## Mensajes y formato de salida (contrato observable)

- **`actualizar` — fuera de ventana:** `status="fuera_de_ventana"` con el mensaje citado en RF-3 (texto actual, conservado sin cambios).
- **`actualizar` — modo inválido:** `status="error"`, mensaje `"modo inválido: '<valor>'. Valores permitidos: append, reemplazar."`.
- **`actualizar` — reemplazo con salvaguarda:** la respuesta incluirá `diff: {longitud_anterior, longitud_nueva, preview_anterior, preview_nuevo}` y `anomalo: true`.
- **`actualizar` — reemplazo normal:** `status="ok"`, `modo="reemplazar"`, `vencido_limpiado: true|false`.
- **`recordar` — por nodo:** campos nuevos `vencido: bool` y `ventana_abierta: bool` presentes en todos los resultados.
- **Historial forense:** entrada con contenido anterior, contenido nuevo, timestamp, autor y flag `anomalo` (0/1) — usando el mecanismo de auditoría existente.

## Dudas abiertas

- [NECESITA ACLARACIÓN: ¿el autor `'desconocido'` del RF-10 es aceptable, o preferís que `actualizar` exija `agente` siempre (error 400 si falta)?]
- [NECESITA ACLARACIÓN: RF-15 interpreta "sustantivos_clave sincronizados" como **preservados** tras el reemplazo (no se borran ni se recalculan). ¿Es esa la lectura correcta, o querés que se recalculen desde el contenido nuevo?]
- [NECESITA ACLARACIÓN: ¿la lista de palabras clave del nombre (`actual|version|vigente`) queda fija en el sistema o también debe ser configurable por variable de entorno? RF-19 solo hace configurable N (días).]
