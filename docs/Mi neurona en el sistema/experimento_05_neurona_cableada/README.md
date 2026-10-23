# Experimento 05: la neurona cableada en el motor

**Objetivo (Dennys):** "déjalo cableado y que funcione bien, sin dañar el motor". Que funcione con una DB vacía y con recuerdos nuevos que nunca vio. Que aprenda sola y en vivo con un costo fijo por operación. Que tenga techo (deja de entrenar cuando ya no mejora) y que se despierte si baja. Nada de QA, feedback ni logs, y ningún trabajo extra para el agente.

## Qué se cableó

| Archivo | Cambio |
|---|---|
| `core/memory/neurona.py` (nuevo) | La neurona completa: rasgos (17 agujas), red 17→6→1, campeón/retador, piso, guardia, techo, persistencia y reordenación del top-5. |
| `core/memory/neurona_examen.py` (nuevo) | Autoexamen: cada recuerdo genera sus propias preguntas con respuesta conocida. Es determinista y se sembró con el nombre del concepto. |
| `core/memory/search.py` (+24/−5) | Anota las agujas de cada candidato (no toca el score). Reordena el top-5 si hay campeón. Las búsquedas de práctica van **en silencio**: no notifican actividad, no hacen accesos ACT-R, no escriben en `log_busquedas` ni publican en la cola epistémica. |
| `core/memory/ingest.py` (+8) | Al final de `consolidar_concepto`: `neurona.practicar(self, [key])`. |
| `core/memory/consolidation.py` (+9) | Al final del ciclo de sueño: `neurona.practicar(self, recién_consolidados)`. |

Lo aprendido vive **dentro de la propia DB** (tabla `neurona_estado`, creada sola). Ocupa unos 5 KB de pesos más 1.5–2 MB de memoria de examen, con tope fijo. Todo va envuelto en `try/except`: si la neurona falla, el motor responde como siempre. Se apaga por completo con `BIORAG_NEURONA=0`.

## Cómo funciona (resumen)

1. **Al consolidar** (cuando sí se sabe la respuesta) se examinan 2 recuerdos: los recién guardados o, si no hay, viejos elegidos al azar por `rowid`, que es O(log N). Cada uno se hace 2 preguntas (variante, typo, sinónimo, pregunta natural, por tema, cruce de idioma). El motor las responde en silencio y se guarda lo que vio cada aguja.
2. **La memoria de examen tiene tamaño fijo:** 1200 preguntas de estudio y 300 de guardia, con reemplazo al azar. El 20 % de los recuerdos (por hash del nombre) es **guardia**: nunca se estudia.
3. **El retador entrena** 30 pasos sobre el estudio. **Solo asciende a campeón** si cumple tres condiciones:
   - no baja la guardia;
   - mejora el total;
   - **en ninguna categoría queda por debajo de los pesos a mano, ni en aciertos #1 ni en MRR** (el piso).
4. **Techo:** tras 12 ciclos sin mejora queda *tranquila*. Deja de entrenar y solo vigila, a mitad de costo. Se despierta sola cuando juntó 150 preguntas nuevas. Si el campeón deja de cumplir el piso (la DB cambió), **se retira y vuelven los pesos a mano**.
5. **Al responder:** solo reordena los 5 primeros que eligió la fórmula, con los mismos nodos y los mismos números reasignados. Así **el R@5 no puede bajar** y los umbrales absolutos (GABA, abstención, FP) no cambian.
   - **Regla de identidad:** si la consulta es el nombre del recuerdo (`_` = espacio) y la fórmula ya lo tenía #1, sigue #1.
   - **DB vacía o sin datos suficientes:** no hay campeón y el motor responde idéntico.

## Resultados

### 1. No daña el motor (QA oficial, 921 casos, snapshot congelado)

| Corrida | R@5 | R@1 | MRR | FP | GATE |
|---|---|---|---|---|---|
| `qa_00` código sin cambios (worktree en `2275b51`) | 100 | **91.89** | .950 | 0/40 | OK |
| `qa_01` neurona cableada, sin nada aprendido | 100 | **91.89** | .950 | 0/40 | OK |

Las dos corridas coinciden: global, todas las categorías y la lista de fallidos byte a byte. Tardaron 588 s y 598 s. Las 346 pruebas de `tests/` pasan antes y después.

### 2. Aprende sola en el motor real (copia del snapshot, uso simulado)

`simular_uso.py` llama, ciclo a ciclo, exactamente lo que se ejecuta tras cada consolidación. Usa la configuración por defecto y parte de cero.

| Momento | Guardia: a mano → campeón | QA R@1 | QA MRR |
|---|---|---|---|
| Base | — | 91.89 | .950 |
| Ciclo 74: primer techo; ningún retador cumplió el piso (perdía 1 caso de sinónimo) | 70.8 % → sin campeón | **91.89** (`qa_03`) | .950 |
| Ciclo 474: 1153 autopreguntas, 15 ascensos | 72.6 % → 85.8 % | **95.31** (`qa_04`) | **.973** |

Detalle de `qa_04` frente a la base, por categoría (**ninguna baja en ninguna métrica**):

| Categoría | R@5 | R@1 | MRR |
|---|---|---|---|
| cruce_idioma (8) | 100 → 100 | 62.50 → **87.50** | .740 → .938 |
| dormido (65) | 100 → 100 | 100 → 100 | 1.000 → 1.000 |
| literal (487) | 100 → 100 | 99.59 → **100** | .998 → 1.000 |
| por_tema (65) | 100 → 100 | 63.08 → **81.54** | .771 → .900 |
| pregunta_natural (65) | 100 → 100 | 93.85 → **96.92** | .964 → .985 |
| sinonimo (55) | 100 → 100 | 56.36 → **58.18** | .722 → .738 |
| typo (65) | 100 → 100 | 89.23 → **98.46** | .936 → .992 |
| variante_gramatical (65) | 100 → 100 | 89.23 → **96.92** | .940 → .985 |
| **GLOBAL** | 100 → 100 | **91.89 → 95.31** | **.950 → .973** |

FP 0/40, ambiguo igual (2), GATE OK. Tiempo del QA: 585 s (sin costo medible al responder).

**Fallo encontrado y corregido (`qa_02`, primera versión):** el campeón subió el R@1 a 93.83, pero **literal bajó de 99.59 a 98.36** y el MRR de sinónimo de .722 a .707. Hubo dos causas:
- La regla de identidad comparaba el nombre exacto, y las consultas literales usan espacios en vez de `_`.
- El piso solo miraba aciertos #1.

Se corrigió con la identidad normalizada y el piso también en MRR. Con esa corrección, el ciclo 74 quedó sin campeón (el piso frenó el daño a sinónimo) y el 474 da la tabla de arriba.

### 3. Datos que nunca vio: DB nueva desde cero (doc de Python en español)

`construir_db_desconocida.py` crea una DB vacía con 279 recuerdos (164 respuestas del FAQ y 115 términos del glosario), guardados uno por uno con `memory_service.aprender`, más un sueño cada 50. El examen usa **las 164 preguntas del FAQ escritas por humanos**. No salen de nuestro generador, y el recuerdo se nombra con palabras de la respuesta, no de la pregunta.

| Momento | R@5 | R@1 | MRR | Casos |
|---|---|---|---|---|
| A mano | 56.10 | 42.07 | .481 | — |
| Tras construir (285 ciclos; en esta DB sus autopreguntas ya salen bien a mano, 92 %, así que no hubo campeón) | 56.10 | 42.07 | .481 | idéntico |
| Tras 300 ciclos más de uso (campeón: guardia 88.3 % → 93.0 %) | 56.10 | **42.68** | **.478** | gana 4, pierde 3 |
| Campeón de la DB de Dennys **trasplantado** (prueba) | 56.10 | 37.20 | .452 | gana 2, pierde 10 |

**Lectura honesta:**
- En una DB desconocida la neurona **no daña** (el R@5 nunca se mueve). Pero con preguntas humanas su mejora es **casi nula**: +0.6 en R@1 y −0.003 en MRR.
- Aprende muy bien el *tipo* de pregunta del autoexamen, que es la misma familia que el QA. Por eso en el QA gana +3.4 puntos y con preguntas humanas casi nada. Es el riesgo de "enseñar para el examen" que ya habíamos anticipado, y aquí queda medido.
- Los pesos son **de cada DB**: el campeón de otra DB daña (−4.9 R@1). En la práctica eso no puede pasar, porque en su primer ciclo el piso lo detecta y **lo retira**.

### 4. Costo (2 CPUs, con otros procesos corriendo en paralelo)

Cada consolidación agrega **un número fijo de búsquedas del propio motor** (2 recuerdos × 2 preguntas; en tranquila, 1 × 2), con un tope de 3 s que se revisa antes de cada pregunta. El costo no crece con la cantidad de recuerdos, salvo lo que ya crece la búsqueda misma.

| DB | Aprendiendo (p50 / p95) | Tranquila (p50 / p95) |
|---|---|---|
| Snapshot de Dennys (866 nodos) | 3.1 s / 5.1 s | 1.4 s / 3.7 s |
| DB de Python (279 nodos) | 0.45 s / 1.2 s | 0.27 s / 0.6 s |

Al responder el costo no es medible: el QA tarda 585 s con campeón frente a 588 s de la base. En MCP, `aprender` solo escribe en corto plazo, así que este costo aparece en el ciclo de sueño (`consolidar`) y en el autoguardado de fin de sesión, no en cada `aprender`.

## Pendiente / decisiones de Dennys

- **Activada por defecto** (`BIORAG_NEURONA=1`). Los parámetros de producción (preguntas por ciclo, tope de tiempo, paciencia) los decides tú. Todos son variables `BIORAG_NEURONA_*` en `neurona.py::_cfg`.
- La mejora real con preguntas humanas es pequeña. El siguiente paso para que generalice sería que el autoexamen se parezca más a cómo pregunta una persona, por ejemplo con preguntas sobre el *contenido* y no solo sobre el nombre.
- La memoria de examen (≤ 2 MB) se reescribe en cada ciclo. Si molesta, puede guardarse cada N ciclos.

## Reproducir

`bash correr_validacion.sh` (variables `LAB` y `PY`). Todas las salidas literales del QA están en `resultados/qa_0*.txt|json`, las curvas en `resultados/curva_*.jsonl` y el campeón final en `resultados/campeon_snapshot_474_consolidaciones.json`.
