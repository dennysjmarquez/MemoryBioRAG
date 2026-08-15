# Hacia dónde va BioRAG, según su propia lógica

Respuesta a: *"las mejoras tienen que ser propias del sistema; si se va a crear
matemática nueva, que sea nueva, no importada."*

Escrito tras leer el código real en el clon (commit `364a770`). Este documento
corrige el enfoque de mi revisión anterior (`REVISION_MATEMATICA.md`), y explico
abajo exactamente en qué me equivoqué.

---

## 0. Dónde me equivoqué antes

Mi primera revisión te propuso RRF, calibración de Platt, predicción conforme,
Dunning LLR, MMR. **Todo eso es correcto y todo eso es prestado.** Es la caja de
herramientas estándar de information retrieval aplicada encima de BioRAG.

Tenías razón en el diagnóstico: si el proyecto crece así, se convierte en "un RAG
más, pero con vocabulario biológico". Las mejoras que importan tienen que salir
de lo que este sistema tiene y ningún otro tiene.

Lo que sigue vale: los **bugs** (varianza explicada que siempre da 1.0, pesos que
suman 1.34 y saturan el ranking, el radio SDM incoherente, HDC declarado pero no
usado). Un bug es un bug. Pero la *dirección* que propuse era prestada.

---

## 1. Qué tiene BioRAG que nadie más tiene

Esta es la pregunta que decide el rumbo. La respuesta no es "PPMI" ni "SVD" ni
"grafo" — eso lo tiene todo el mundo.

Lo que es exclusivo, verificado en el código:

| Activo | Dónde vive | Por qué es único |
|---|---|---|
| **Los recuerdos mueren** | `memory_store.py:2103` (LTD), `:2223` (umbral 0.05) | Un embedding en FAISS no tiene mortalidad. Aquí `w<=0.05` es una frontera absorbente real. |
| **Trayectoria temporal de cada nodo** | tabla `metricas_cognitivas_nodos` (`peso_anterior`, `peso_nuevo`, `created_at`) | Es una serie temporal por nodo. Ningún RAG guarda la historia de cómo su índice llegó a ser lo que es. |
| **Presupuesto global de atención** | homeostasis, `:2199` (media > 0.70 → ×0.98) | Impone conservación: fortalecer algo obliga a debilitar otra cosa. |
| **Refuerzo con inercia** | `:2455`, Δw = 0.15(1−0.3w) y fallo dividido por `1+ln(1+éxitos)` | El sistema tiene memoria de su propio historial de aciertos. |
| **Actividad sin consulta** | `dmn_engine.py:108` | El índice se modifica solo cuando nadie pregunta. Un índice vectorial es inerte. |

**El objeto matemático propio de BioRAG no es el vector. Es la trayectoria.**

Todo el esfuerzo del proyecto (y toda mi revisión anterior) está puesto en el
espacio de representación — que es territorio ya explorado por medio mundo. La
dinámica temporal de la corteza no la está estudiando nadie, y es lo que este
sistema genera de forma natural.

---

## 2. La matemática que sale de ahí (derivada, no importada)

Implementada y auto-verificada en `core/termodinamica_cortical.py`.

### 2.1 Ley de supervivencia cortical

De las reglas reales del código, en equilibrio entre LTP y LTD:

```
λ · 0.15 · (1 − 0.3·w*)  =  0.05 · d · m
```

de donde el punto fijo `w*` y el umbral crítico `λ*` = accesos por ciclo de sueño
por debajo de los cuales un nodo se apaga. Esto ya da algo que el proyecto no
sabía que tenía: **la vida media de un nodo no accedido es lineal, no
exponencial** (porque el LTD del código es sustractivo), y vale exactamente
`(w − 0.05)/(0.05·d·m)` ciclos. Con `m=1.5` (prioridad NULL, el default): 6 ciclos
desde w=0.5.

### 2.2 El hallazgo real: el punto fijo miente

Al simular las reglas exactas (incluido el `ROUND(...,2)` de SQLite) el punto fijo
resultó **fuertemente optimista**. La razón es la frontera absorbente: los accesos
llegan en ráfagas de Poisson, y una racha de silencio mata al nodo aunque su tasa
media de acceso fuera suficiente. Una vez dormido, sale del pool activo — la
muerte es casi permanente.

Esto no es un problema de equilibrio, es un **problema de primer cruce**
(first-passage). El resultado, medido:

| prioridad (mult) | λ* determinista | λ seguro (P(muerte)≤5%) |
|---|---|---|
| 2 (0.5) | 0.169 | 0.323 |
| 3 (1.0) | 0.338 | 0.625 |
| NULL (1.5) | 0.508 | 0.979 |
| 5 (2.5) | 0.846 | 1.652 |

**La brecha ~2x entre las dos columnas es el hallazgo.** El sistema hoy razona
implícitamente con la primera columna; la realidad opera en la segunda. Hay una
banda de nodos que el sistema cree seguros y que en realidad está perdiendo por
azar, no por falta de valor.

> **Nota de método (por qué este número cambió).** En mi primera versión calculé
> `λ seguro` con una aproximación de "rachas de ciclos sin acceso" y reporté 1.195
> para prioridad NULL. El autotest la **refutó**: erraba hasta 0.215 en la zona de
> transición, porque ignora que el peso se recupera parcialmente entre silencios y
> por tanto la muerte no requiere una racha limpia. La reemplacé por la cadena de
> Markov absorbente exacta sobre la grilla real de pesos (que es exacta porque el
> SQL redondea a 2 decimales, así que los estados son genuinamente discretos). El
> error absoluto medio bajó de 0.070 a **0.0147**, dentro del ruido de Monte Carlo
> con 60 réplicas. El número bueno es 0.979; el 1.195 era del método malo.

### 2.3 Capacidad de carga

De la homeostasis: si la media debe quedar ≤0.70 y los pesos viven en [0.05, 1.0],
la fracción máxima de nodos saturados es `(0.70−0.05)/0.95 = 0.684`. Con 900 nodos
activos: **615 saturados como techo duro**.

Esto convierte el olvido en una ley de conservación en vez de un efecto
secundario. La corteza tiene un presupuesto fijo de atención y el sistema puede
saber *antes* de dormir cuántos nodos va a perder, en vez de descubrirlo después.

### 2.4 Lo que esto habilita: que el olvido sea justo

Hoy el olvido depende solo de frecuencia de acceso y prioridad. Pero un nodo puede
ser **estructuralmente crítico y poco consultado**: un puente entre dos islas
semánticas. Si muere, se desconecta una región entera de la corteza — y el sistema
no se entera.

`valor_supervivencia()` cruza el riesgo de extinción con el soporte estructural
(grado sináptico) y afectivo (valencia). Un nodo puente con grado 40 y un nodo
periférico con grado 2, **con exactamente el mismo λ, hoy corren el mismo destino**.
La teoría dice que no deberían.

> **Defecto conocido de esta parte, y no lo voy a maquillar:** el umbral de
> `indice_injusticia > 1.0` que uso para clasificar es arbitrario, y en la demo
> ambos nodos (grado 2 y grado 40) caen del mismo lado, así que el índice tal como
> está **no discrimina bien en ese rango**. El índice es una hipótesis operacional,
> no un resultado. El `log(1+grado)` es una elección de diseño para amortiguar
> hubs, no algo medido. Esto necesita calibrarse contra datos reales antes de
> conectarse a nada que modifique pesos.

---

## 2.5 CORRECCIÓN (2026-08-15): P3 falló, y el fallo enseñó algo mejor

El agente del usuario ejecutó P3 contra la DB real. **Resultado: refutada como
estaba escrita.** Lo reporto tal cual salió.

| Test | Fórmula probada | Resultado |
|---|---|---|
| P3 original | Δw = 0.15(1−0.3w) [LTP] | ❌ error medio 0.158 |
| P3 corregida | Δw = +0.20 fijo, sat. 1.0 [fusión] | ✅ error 0.000 |

**El error fue mío**, y es exactamente el tipo de error que P3 existía para
detectar: asumí que `metricas_cognitivas_nodos` registraba el LTP. No lo hace.
Verifiqué en el código que `aplicar_refuerzo_dopaminergico` (líneas 2433-2487) no
escribe en esa tabla, y que su único INSERT (línea 2338) ocurre dentro del ciclo
de sueño. `accion='actualizado'` es **fusión de contenido duplicado**
(línea 2011, +0.20 fijo). El diagnóstico del agente es correcto en todos sus puntos.

### Pero al verificarlo encontré algo que cambia la teoría

Revisando todas las rutas que suben el peso aparecieron **tres reglas distintas**,
no una:

| # | Regla | Δw | ¿Logueada? | Cuándo |
|---|---|---|---|---|
| a | Fusión (`:2011`) | +0.20 fijo | **sí** (`actualizado`) | guardar concepto existente |
| b | Despertar (`:1591`, `:4790`, `:5196`) | +0.15 / +0.3 | no | solo si `estado=='dormido'` y `profundidad=='profundo'` |
| c | Feedback dopaminérgico (`:2454`) | 0.15(1−0.3w) | no | solo desde `mcp_server.py:2094` |

**Lo decisivo: leer un nodo ACTIVO no le sube el peso.** No hay LTP por lectura
para nodos ya activos. Eso invalida un supuesto central de mi versión anterior,
donde traté λ como "tasa de acceso".

> **λ no es la tasa de consulta. Es la tasa de feedback explícito.**

Un nodo puede ser el más consultado del sistema y dormirse igual, si nadie llama a
la herramienta de feedback. Aritmética directa sobre el LTD del código: un nodo
**saturado en w=1.0** con `mult=1.5` tarda **13 ciclos de sueño** en apagarse sin
feedback. Con w=0.5, son 6.

Esto no debilita la teoría: la agrava. λ es una variable mucho más escasa de lo que
supuse, así que la extinción es **más** probable, no menos.

De ahí sale una predicción nueva y barata, **P4**: *la mayoría de los nodos
dormidos tendrá `exitos_dopamina == 0`*. Si se confirma, el olvido en BioRAG no
está gobernado por "poco valor" sino por **"nadie dio feedback"** — que es una
patología del bucle de refuerzo, no de la memoria. Y eso se arregla en el bucle,
no tocando las constantes de decaimiento.

---

## 3. Estado de validación (importante)

**No hay ninguna base de datos en el repo clonado.** `scripts/snapshot_prf_real.db`
que menciona el README no viene en el clon; solo hay ficheros `-wal`/`-shm`
huérfanos en `MemoryBioRAG_Data/`. Lo verifiqué explícitamente.

Por lo tanto:

- Lo que **sí** está hecho: derivación algebraica desde el código real, cadena de
  Markov exacta, y validación contra simulación de las reglas exactas
  (error medio 0.0147). Eso se sostiene solo.
- Lo que **no** está hecho: ninguna medición sobre datos de producción. Cero.

Ningún número de este documento es una medición de tu sistema real. Son teoría y
simulación de las reglas que están escritas en tu código.

El experimento que lo confirmaría o lo tumbaría está especificado en
`experimento_eddington()` con predicciones fijadas *antes* de ver los datos:

- **P1**: los nodos que se durmieron tendrán λ de **feedback** previo por debajo de
  `lambda_seguro` en ≥80% de los casos.
- **P2**: existirá un subconjunto no vacío de nodos dormidos con alto grado
  sináptico y bajo feedback (olvidos estructuralmente costosos).
- ~~**P3**~~: **ejecutada y refutada como estaba escrita** (ver §2.5). Validó sin
  saberlo la fórmula de fusión (+0.20), no la de LTP. El LTP dopaminérgico **no
  tiene logging** y por tanto no es medible directamente con el esquema actual;
  solo inferible desde `exitos_dopamina` + `peso_sinaptico`.
- **P4** (nueva, la más barata de todas): la mayoría de nodos dormidos tendrá
  `exitos_dopamina == 0`. Es una sola consulta SQL.

**P4 es ahora el test más importante.** Si se confirma, el problema no está en las
constantes de decaimiento sino en que el bucle de feedback casi nunca se cierra —
y eso es accionable de inmediato.

Si P1 falla, el olvido está dominado por inhibición lateral u homeostasis y no por
LTD pasivo, y las secciones 2.1–2.2 hay que reescribirlas.

**Instrumentación que falta** (y que P3 dejó al descubierto): el `CHECK` del
esquema solo admite `'nuevo','actualizado','dormido','eliminado'`. No hay forma de
registrar un refuerzo. Añadir `'reforzado'` y loguear desde
`aplicar_refuerzo_dopaminergico` convertiría el LTP en medible en vez de inferible.

---

## 4. Hacia dónde va el proyecto, honestamente

Si sigo la lógica interna del sistema hasta el final, el destino no es "mejor
recuperación". Es esto:

**BioRAG es un sistema donde el conocimiento tiene una economía: nace, se refuerza,
compite por un presupuesto fijo y muere.** El RAG es solo la interfaz de lectura de
esa economía.

Lo que hoy está sin explorar, y que es todo territorio propio:

1. **Termodinámica de la corteza** (empezado aquí). Θ como variable de estado, con
   ecuación de evolución propia. ¿Hay transiciones de fase? La homeostasis en 0.70
   con la frontera en 0.05 huele a un sistema con dos regímenes.
2. **El sueño como operador, no como mantenimiento.** El ciclo de sueño es una
   transformación T aplicada al estado completo. Sus propiedades espectrales —
   ¿converge?, ¿a qué?, ¿tiene ciclos límite? — son estudiables y nadie las estudió.
3. **Conservación y coste de oportunidad.** Si el presupuesto es fijo, cada
   escritura tiene un precio pagado por otro nodo. Eso se puede hacer explícito:
   qué se desplazó al recordar esto.
4. **El DMN como generador de estructura.** Hoy elige nodos con `random.choice`
   (lo verifiqué, `dmn_engine.py:141,172`). Podría dirigirse por dónde la corteza
   tiene tensión estructural — regiones cuyos puentes están por morir. Ahí el DMN
   deja de ser decorativo y pasa a ser reparación dirigida.
5. **La honestidad epistémica como conservación**, no como umbral: el sistema sabe
   qué zonas de su corteza están frías o se están apagando, y puede decir "esto lo
   supe y lo estoy perdiendo" — que es una forma de no-saber que ningún RAG puede
   expresar.

---

## 5. Qué haría ahora, en orden

1. **Correr P3** contra la DB de producción. Es una consulta SQL y un ajuste. Si la
   teoría no describe el código real, nada de lo demás importa. (Barato: minutos.)
2. **Correr P1 y P2.** Requiere estimar λ por nodo desde `ultimo_acceso` y los
   contadores de dopamina. Si P2 encuentra nodos puente muertos, hay un problema
   real y medible que hoy nadie ve.
3. **Solo entonces** tocar código: reasignación de `prioridad` según riesgo
   estructural, con benchmark antes/después y un cambio a la vez.
4. En paralelo, y aparte: arreglar los bugs de la revisión anterior. Son
   independientes de todo esto y no requieren teoría nueva.

Mi nivel de confianza: **alto (~0.9)** en las derivaciones y en la validación por
simulación — eso lo ejecuté y el error es 0.0147. **Bajo (~0.4)** en que las
predicciones P1/P2 se confirmen contra datos reales, porque no he visto un solo
dato de producción. Y **explícitamente bajo (~0.3)** en el índice de injusticia de
la sección 2.4, que tiene el defecto de discriminación que documenté arriba.

La parte imaginativa está hecha. La parte del eclipse, no.
