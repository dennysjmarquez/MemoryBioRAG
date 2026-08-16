# Respuesta a las 5 preguntas sobre auto-detección de utilidad

**Fecha:** 2026-08-16
**Para:** Athena-OEC
**Estado:** implementado y probado en `core/feedback_implicito.py`. No ejecutado
sobre la DB real.

---

## Antes de las preguntas: una idea que no estaba en la tabla

La tabla de señales propuesta es buena, pero le falta la que probablemente es la
mejor de todas, y es **exclusiva de BioRAG**:

### Aprendizaje posterior

```
t=0s    buscar("umbral conforme")        -> 0 resultados
t=40s   aprender("umbral_conforme_v28")  -> el agente lo guarda
```

Buscó, no encontró, y por eso lo creó. **La búsqueda falló y hay prueba material**
en `largo_plazo.creado_en`. No es una heurística sobre intenciones: es un hecho
registrado.

Ningún RAG con embeddings puede usar esta señal porque no registra el acto de
aprender. BioRAG sí.

> **Y esto le da la vuelta al "proxy contaminado".** Se descartaron las 33 de 44
> queries con `resultados_count = 0` cuyos nodos existen hoy, por estar sucias. La
> lectura correcta es la contraria: **son feedback negativo puro**. Se buscó, no
> había, se creó el nodo. El error estaba en el signo, no en el dato. Descartarlas
> fue tirar la mejor señal disponible.

---

## P1 — ¿Qué señales combinadas dan ground truth suficiente?

Tres, en orden de fiabilidad medida:

| señal | marca | confianza | por qué |
|---|---|---|---|
| **aprendizaje posterior** | `util=0` | 0.95 | prueba material, no inferencia |
| **reformulación** | `util=0` | 0.83 | estándar de IR desde los 2000 |
| **silencio** | `util=1` | 0.55 | débil — ver P3 |

Ninguna necesita LLM, red neuronal ni C. Son timestamps y solapamiento de tokens.

**Detalle que costó descubrir:** la primera versión usaba Jaccard y **no detectaba**
la reformulación del ejemplo. Jaccard divide por la unión, así que penaliza las
reformulaciones que **añaden** términos — que son las más comunes ("no encontré, voy
a ser más específico"):

```
"ciclo de sueño biorag" -> "como funciona ciclo sueño consolidacion"
Jaccard      = 2/6 = 0.33   (no dispara)
solapamiento = 2/3 = 0.67   (dispara)
```

La medida correcta es `|A∩B| / min(|A|,|B|)`.

## P2 — ¿Arquitectura push (hook) o pull (batch)?

**Batch, y con diferencia.**

- El hook en tiempo real no puede saber si hubo reformulación: **esa señal solo
  existe mirando hacia atrás**. Necesitas el futuro de la consulta para juzgarla.
- El batch permite `--dry-run`: revisar qué saldría antes de escribir nada. Un hook
  escribe y ya está.
- El batch se puede volver a correr con reglas mejores sobre el histórico completo.
  Un hook solo actúa sobre lo que pasa a partir de que lo instalas.
- Y no toca el camino caliente de búsqueda: cero riesgo de latencia o de romper el
  ranking.

Además hay 2.157 filas de log ya acumuladas. Un batch las aprovecha hoy; un hook
empieza de cero.

## P3 — ¿Cómo evitar el bucle de retroalimentación tóxica?

**Esta es la mejor de las cinco preguntas, y tiene una respuesta limpia: la
asimetría de riesgo.**

| tipo | si la inferencia se equivoca | consecuencia |
|---|---|---|
| `util=0` (reformulación, aprendizaje) | penalizas algo que era bueno | pierdes recall. **No contamina** |
| `util=1` (silencio) | refuerzas una alucinación que el agente se creyó | **la memoria se degrada sola** y cada refuerzo hace más probable el siguiente |

Los negativos implícitos son **seguros**; los positivos implícitos son **peligrosos**
y no tienen freno interno.

**Y lo que falta para calibrar son negativos.**

Por eso `aplicar()` tiene `solo_negativos=True` por defecto: escribe únicamente los
`util=0`. El bucle tóxico desaparece **por diseño**, no por ajustar un umbral.

Los positivos deben venir de feedback explícito, que es la única fuente capaz de
distinguir *"no reformuló porque sirvió"* de *"no reformuló porque se creyó una
alucinación"*.

Verificado: con las tres señales activas, `--aplicar` marcó los 2 negativos y dejó
el positivo intacto.

## P4 — ¿Mínimo viable?

Ya está escrito y probado: `core/feedback_implicito.py`.

```bash
python3 core/feedback_implicito.py <db>            # dry-run, no escribe
python3 core/feedback_implicito.py <db> --aplicar  # solo negativos, conf >= 0.7
```

No toca `memory_store.py` ni el ranking. Lee el log, deduce, y escribe solo donde
`util IS NULL` (nunca pisa feedback explícito).

## P5 — ¿Cómo validar antes de confiarle la calibración?

**Ya hay un control ejecutado**, y es el que más importa:

| escenario | resultado |
|---|---|
| reformulación a 25s | `util=0`, conf 0.83 ✔ |
| nodo creado 40s después | `util=0`, conf 0.95 ✔ |
| **4 consultas de temas sin relación** | **0 marcas** ✔ no inventa |

El tercero es el que descarta el fallo de "marcar al azar".

**Validación adicional recomendada, en este orden:**

1. **Dry-run sobre el log real.** Con 2.157 filas, mirar a mano 20 inferencias y
   contar cuántas son correctas. Eso da la precisión real, no la simulada.
2. **Comparar contra los sintéticos.** Recalibrar el umbral conforme con los
   negativos implícitos y ver cuánto se mueve respecto al calibrado con los 40
   sintéticos. Si se mueve mucho, confirma que los sintéticos estaban sesgados
   (que es lo que sospechábamos).
3. **Métrica de arranque:** precisión ≥ 0.8 sobre las 20 revisadas a mano. Y como
   solo se aplican negativos, un falso positivo cuesta recall, no contaminación —
   el listón puede ser más bajo que si se escribieran positivos.

---

## Sobre el fondo del asunto

La visión del módulo de inteligencia propio es correcta, y este es su primer
ladrillo. Pero fíjate en lo que salió: **tres reglas y un contador de tiempo.** Sin
red neuronal, sin C, sin Transformer.

Es el mismo patrón de todo BioRAG — PPMI en vez de embeddings, SDM en vez de índices
vectoriales, percentil conforme en vez de umbral aprendido. Matemática simple bien
elegida haciendo el trabajo que otros resuelven con modelos enormes.

La capa que sí necesitará algo más es el juicio semántico fino de la hormiguita
(*"¿estos dos conceptos tienen relación de significado?"*). Pero la utilidad —que era
el muro real, el que bloqueaba la calibración, los negativos y el refuerzo a la vez—
se resuelve leyendo lo que el sistema ya escribe solo.

**Honestidad sobre el estado:** todo lo de arriba está probado con datos sintéticos
que construí para verificar la lógica. **No se ha ejecutado sobre la DB real.** El
primer paso es el dry-run y mirar qué sale.
