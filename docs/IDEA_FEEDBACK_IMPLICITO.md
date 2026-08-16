# Feedback automático sin modelo: la señal ya está en tu log

**Fecha:** 2026-08-16
**Respuesta a:** "¿sale de aquí alguna idea para hacer esto automático?"
**Estado:** implementado y probado en `core/feedback_implicito.py`. **No ejecutado
sobre la DB real.**

---

## 1. La idea

El plan que se venía discutiendo era construir un módulo de inteligencia que juzgara
si una respuesta sirvió. Athena tenía razón en que no hace falta un Transformer.

Pero se puede ir un paso más allá: **no hace falta ningún clasificador, porque el
comportamiento del agente ya contiene la respuesta.** Solo hay que leerla.

`log_busquedas` ya guarda `query`, `resultados_count`, `top_score` y **`creado_en`**.
Ese timestamp es la pieza que nadie estaba usando.

## 2. Las tres señales

### a) Reformulación (estándar de IR desde los 2000)

```
t=0s    "ciclo de sueño biorag"
t=25s   "como funciona ciclo sueño consolidacion"   <- reformuló: la 1ª FALLÓ
```

Si tras buscar X el agente busca algo parecido a X en segundos, la primera no
sirvió. Google y Bing llevan veinte años midiendo calidad así. Es aritmética sobre
timestamps.

### b) Aprendizaje posterior — **exclusiva de BioRAG**

```
t=0s    buscar("umbral conforme")        -> 0 resultados
t=40s   aprender("umbral_conforme_v28")  -> el agente lo guarda
```

Buscó, no encontró, y guardó. **La búsqueda falló y el sistema tiene la prueba
material** en `largo_plazo.creado_en`. Ningún RAG con embeddings puede hacer esto,
porque no registra el acto de aprender.

> **Esto le da la vuelta al hallazgo del "proxy contaminado".** Se descartaron las
> 33 de 44 queries con `resultados_count = 0` cuyos nodos existen hoy, por estar
> "sucias". La lectura correcta es la opuesta: **son feedback negativo puro y sin
> ambigüedad** — se buscó, no había, y por eso se creó el nodo. El error estaba en
> el signo, no en el dato. Descartarlas era tirar la mejor señal disponible.

### c) Silencio posterior

Si no reformula ni aprende, siguió con su tarea: sirvió. Es la señal más débil, y
por eso va marcada con confianza 0.55 y queda fuera del umbral por defecto.

## 3. Probado

| escenario | resultado |
|---|---|
| reformulación a 25s | `util=0`, confianza **0.83** ✔ |
| nodo creado 40s después | `util=0`, confianza **0.95** ✔ |
| búsqueda sin secuela | `util=1`, confianza 0.55 (débil, no se aplica) |
| **control: 4 temas distintos seguidos** | **0 marcas** ✔ no inventa |

El control es lo importante: con consultas de temas sin relación no produce ninguna
inferencia fuerte. No marca al azar.

## 4. Un bug que encontré en mi propio código al probarlo

La primera versión usaba **Jaccard** para comparar consultas y **no detectaba la
reformulación del ejemplo**:

```
"ciclo de sueño biorag" -> "como funciona ciclo sueño consolidacion"
Jaccard      = 2/6 = 0.33   (no dispara)
solapamiento = 2/3 = 0.67   (dispara)
```

Jaccard divide por la unión, así que **penaliza las reformulaciones que añaden
términos** — que son justo las más comunes ("no encontré, voy a ser más
específico"). Cuantas más palabras añade el agente, menos parecidas las ve. Al
revés de lo que hace falta.

Corregido a coeficiente de solapamiento `|A∩B| / min(|A|,|B|)`. El razonamiento
está en el docstring de la función, con los números medidos.

## 5. Lo que esto desbloquea

Con `util` poblándose sola, sin que nadie pulse nada:

| bloqueo | se resuelve |
|---|---|
| 0 negativos reales para calibrar | señales (a) y (b) dan `util=0` con alta confianza |
| El "FP 6%" es sobre negativos sintéticos | recalibrar con negativos **reales** |
| No se puede verificar intercambiabilidad | la distribución pasa a ser la real |
| No se sabe el ratio de la carga | conteo directo |
| Los recuerdos mueren de silencio | el refuerzo deja de depender de que alguien se acuerde |

Y no reemplaza al feedback explícito: `aplicar()` solo escribe donde `util IS NULL`,
así que un feedback real de un agente nunca se sobrescribe con una inferencia.

## 6. Honestidad sobre qué es y qué no

**No mide calidad.** Mide comportamiento: dice si el agente *siguió buscando*, no si
la respuesta era *buena*. Tiene ruido — se puede reformular por curiosidad, o
abandonar por una interrupción externa.

Por eso cada inferencia lleva `confianza` y el default solo aplica ≥ 0.7. Para
calibración conforme conviene ser aún más estricto y usar solo la señal (b), que es
la única con prueba material.

**No está ejecutado sobre la DB real.** Todo lo de arriba son pruebas con datos
sintéticos que construí para verificar la lógica. El primer paso es correrlo en
`--dry-run` sobre el log real y mirar qué sale antes de aplicar nada.

## 7. Cómo probarlo

```bash
# Solo reporta, no escribe nada
python3 core/feedback_implicito.py MemoryBioRAG_Data/memory_biorag.db

# Si lo que sale tiene sentido, aplicar
python3 core/feedback_implicito.py MemoryBioRAG_Data/memory_biorag.db --aplicar
```

Con 2.157 filas en el log, es razonable esperar que salgan decenas de inferencias
fuertes — bastantes más negativos reales que los 2-3 que quedaron tras descartar el
"proxy contaminado".

## 8. Y sobre el módulo de inteligencia propio

La visión es correcta y esto es su primer ladrillo. Pero fíjate en lo que pasó:
**el módulo resultó ser tres reglas y un contador de tiempo.** Sin red neuronal, sin
C, sin Transformer.

Ese es el mismo patrón de todo BioRAG: PPMI en vez de embeddings, SDM en vez de
índices vectoriales, percentil conforme en vez de umbral aprendido. La matemática
simple, bien elegida, hace el trabajo que la gente resuelve con modelos gigantes.

La capa que sí necesitará algo más es el juicio semántico fino de la hormiguita
(*"¿estos dos conceptos tienen relación de significado?"*). Pero la utilidad —que
era el bloqueo real— se resuelve leyendo lo que el sistema ya escribe.
