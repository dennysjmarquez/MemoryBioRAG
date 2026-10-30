# Experimento: graduar el bono de sinónimos. Resultado NEGATIVO.

**Fecha:** 2026-10-26 · **Base:** la viva del autor (1357 nodos), subida como
`backup_memory_biorag.sql` desde Google Drive y reconstruida localmente.
**Arnés:** `scripts/evaluar_qa.py --con-neurona --si`, 921 casos, mismas
banderas que `run_qa_suite.sh`.

## La pregunta

En la categoría `sinonimo` el nodo correcto casi siempre declara la palabra en
su campo `sinonimos`. Medido sobre los 61 casos: **61 de 61**. Pero la señal es
binaria — `score_simbolico_sinonimos` devuelve 1.0 si la palabra aparece, sin
mirar nada más — y en la base viva **una mediana de 16 nodos** (media 31,4,
máximo 184) declara la misma palabra y puntúa exactamente igual.

Cuando todos empatan, decide BM25, que premia llevar la palabra en el **nombre**
sobre llevarla en el **alias**. De ahí que `perfil` devuelva
`notebooklm_perfil_dennys_id` (0.772) antes que `dennys-identidad-profunda`.

Además el empate **crece con el corpus**. Crecimiento controlado sobre el
snapshot (mismos 61 casos, conservando siempre el nodo correcto, variando solo
el número de distractores, sin neurona):

| nodos | R@1 | R@5 | puesto medio | empatados (mediana) |
|---:|---:|---:|---:|---:|
| 150 | 0.803 | 1.000 | 1.26 | 2 |
| 400 | 0.656 | 0.967 | 1.74 | 8 |
| 866 | 0.525 | 0.902 | 2.43 | 16 |

Sobre la base viva, mismo protocolo (`profundidad='activos'`, `limite=5`):

| nodos | R@1 | R@5 | fallos |
|---:|---:|---:|---:|
| 150 | 0.639 | 0.787 | 13 |
| 400 | 0.541 | 0.787 | 13 |
| 866 | 0.361 | 0.721 | 17 |
| 1357 | 0.361 | 0.656 | 21 |

## La hipótesis

Graduar el bono del piso de sinónimos (`core/memory/scoring.py`, rama
`elif sinonimos_ratio >= 0.95`) por dos hechos que el autor sí escribió:

1. **Rareza** — IDF relativo del alias: `log1p(N/df) / log1p(N)`.
2. **Posición** — el alias en posición *k* vale `1/(1+0.25·(k-1))`.

Se implementó en `core/fallback_simbolico.calidad_sinonimo` y se multiplicó el
bono logit por ese valor, con `calidad=1.0` idéntico al comportamiento anterior.
Bandera `BIORAG_SINONIMOS_CALIDAD`, apagada por defecto.

## La medición

| métrica | antes | después | delta |
|---|---:|---:|---:|
| global R@5 | 99.20 | 98.63 | **−0.57** |
| global R@1 | 92.46 | 92.11 | −0.35 |
| global MRR | 0.9516 | 0.9479 | −0.0037 |
| fallos | 7 | **12** | **+5** |
| `sinonimo` R@5 | 89.09 | **80.00** | **−9.09** |
| `sinonimo` R@1 | 52.73 | 49.09 | −3.64 |
| `sinonimo` fallos | 6 | **11** | **+5** |

El resto de categorías sin cambio (literal, typo, variante, dormido, pregunta
natural, cruce de idioma). La compuerta `[GATE]` **falla**.

## Por qué falló

El bono no es un adorno: es el piso que hace competir a un nodo con alias
perfecto contra un nodo con el nombre exacto. Al graduarlo, **bajé el piso de
todos** — también el del correcto — y los correctos que ya ganaban por el piso
cayeron por debajo de rivales con coincidencia de nombre. Gané gradiente y perdí
altura. El desempate se movió, pero hacia abajo.

## Conclusión

**Revertido.** El árbol queda como estaba; el código del experimento se retiró.

El diagnóstico queda en pie y es el que importa: el número de `sinonimo`
**no es una propiedad del sistema, es una propiedad del sistema × corpus**. La
ecuación está calibrada sobre un corpus concreto (pesos absolutos, señal
binaria) y se degrada sola al crecer la base. Cualquier arreglo tiene que
**conservar el piso y añadir discriminación encima**, no repartir el piso.

Variante propuesta para la próxima medición (una sola, aislada): mantener
`target = 0.70 + 0.10·ppmi` igual para todos los que declaran el alias, y sumar
un extra pequeño proporcional a la calidad (`bonus += c · calidad`, con `c` ≤ 0.1
en logit). Todos conservan su altura; el alias mejor escrito recibe un empujón
que los demás no tienen.

## Intento 2: el piso igual para todos, empujón encima (TAMBIÉN NEGATIVO)

Variante medida en la base viva, `scripts/barrido_bonus_sinonimos.py`, sobre
`sinonimo` (61 casos) y `por_tema` (65):

    bonus = logit(0.70 + 0.10·ppmi) + extra · calidad

con `extra` en espacio logit, `calidad` = rareza del alias × posición.

| extra | sinonimo R@5 | sinonimo R@1 | fallos | por_tema R@5 |
|---:|---:|---:|---:|---:|
| −3.0 | 0.443 | 0.328 | 34 | 0.785 |
| **0.0 (actual)** | **0.656** | **0.361** | **21** | 0.785 |
| +1.0 | 0.623 | 0.328 | 23 | 0.785 |
| +2.0 | 0.623 | 0.295 | 23 | 0.785 |
| +3.0 | 0.623 | 0.311 | 23 | 0.785 |

`por_tema` no se mueve en ningún valor: el cambio es local a `sinonimo`.

### Por qué también falla

El bono se aplica en logit y el score se recorta a 1.0. Sumar a todos **acerca a
todos al techo**, y cerca del techo la logística aplana: se pierde gradiente otra
vez, ahora por saturación. Restar (`extra` negativo) es peor todavía, porque el
piso es lo que hace visible al nodo de alias puro.

Conclusión: **el piso de sinónimos ya está en su punto.** No es una perilla
descalibrada, es una perilla agotada. Dos experimentos independientes lo
confirman (repartir el piso, y sumar encima del piso).

## Lo que esto significa para el diagnóstico

El bono de sinónimos no es el cuello de botella. El cuello está en otro sitio:

- Con el motor desnudo y `profundidad='activos'`, el nodo correcto **no entra al
  top-5 en 21 de 61 casos** (R@5 0.656). No está mal puntuado: no llega.
- Con la neurona de ranking, la QA real sube a R@5 0.8909 en esa categoría. O
  sea: **la neurona ya es la que rescata estos casos**, no la ecuación a mano.
- Los 491 nodos nuevos de la base viva comparten vocabulario con los viejos, así
  que la colisión crece. A igual tamaño (866 nodos), la base viva falla 17 y el
  snapshot 3.

La siguiente palanca no es "puntuar mejor el alias": es **dar a la neurona el
hecho que la ecuación no puede usar**. La calidad del alias (rareza × posición)
es un rasgo disponible y hoy no se le ofrece. Como rasgo, si no aporta, el
entrenamiento deja su peso en cero y no hay regresión; si aporta, la neurona lo
usa donde la fórmula global no llega. Eso es exactamente "neurona donde el código
no llegaría".


- `scripts/experimento_crecimiento_corpus.py` — crecimiento controlado.
- `scripts/crecimiento_corpus_resultado.json` — curva del snapshot.
- `scripts/crecimiento_viva_resultado.json` — curva de la base viva.
- `scripts/barrido_bonus_sinonimos.py` — barrido del extra de sinónimos (intento 2).

---

## 3. Auditoría externa: la medición definitiva (2026-10-26)

Un auditor revisó esta rama y señaló que el punto 11 del informe anterior era
imposible. Tenía razón. Medido y verificado:

### 3.1 La neurona no puede cambiar el R@5

`core/memory/search.py:2288` — `neurona.reordenar(...)` recibe
`pagina_resultados`, que ya está recortada a `limite`. Sus propias palabras:
«reordena SOLO el top-5 final (mismos nodos, mismos scores reasignados)». No
cambia QUIÉN entra; cambia el orden de los que ya entraron.

QA oficial sobre la base viva (1357 nodos, 921 casos):

| | sin neurona (`BIORAG_NEURONA=0`) | con neurona |
|---|---:|---:|
| global R@5 | 99.20 | 99.20 |
| global R@1 | 91.09 | 92.46 |
| global MRR | 0.9432 | 0.9516 |
| global fallos | 7 | 7 |
| **sinonimo** R@5 | **89.09** | **89.09** |
| **sinonimo** R@1 | **52.73** | **52.73** |
| sinonimo fallos | 6 | 6 |

**El 89.09 % lo logra la fórmula, no la neurona.** En `sinonimo` la neurona no
aporta nada, ni en R@1. Donde sí aporta es en el global (R@1 +1.37, MRR +0.0084).

El «65.6 % sin neurona» del informe anterior **no es comparable**: salía de un
script propio con 61 casos (la QA resuelve 3 etiquetas contradictorias y quedan
55), búsqueda con 50 resultados y otra profundidad. Mezclar ambas cifras fue un
error de método.

### 3.2 Los 6 fallos están fuera del alcance de la neurona

Puesto real del nodo correcto, `PYTHONHASHSEED=1`, hasta 200 resultados:

| ID | consulta | estado | puesto (activos) | puesto (profundo) |
|---|---|---|---:|---:|
| 0514 | perfil | activo | 9 | 9 |
| 0674 | filtro-arquitecto-prolijo | activo | 18 | 18 |
| 0692 | metodologia | activo | 6 | 5 |
| 0710 | agente | activo | 6 | 6 |
| 0734 | regla | **dormido** | fuera | 21 |
| 0805 | cv | activo | 13 | 13 |

Ninguno está en el top-5. La neurona solo ve el top-5. **No puede arreglar
ninguno de los 6.** El problema de `sinonimo` es de GENERACIÓN (quién llega),
no de ORDEN. La guía lo dice en la sección 10: «La neurona solo reordena lo que
llegó. Si la respuesta no entra al pool, encontrarla es trabajo de otra pieza».

### 3.3 El dato propuesto no separa a los empatados

La rareza del alias es un único número por palabra: los 17 nodos que declaran
`perfil` reciben exactamente el mismo. Solo variaba la posición en la lista.
Medido antes de implementar: correcto solo en el tope pasa de 21/61 a 26/61 —
cinco casos, y 32 seguían empatados. Insuficiente para justificar el coste.

### 3.4 Añadir una aguja NO es gratis: borra todas las neuronas

`core/memory/neurona.py:234` incluye `rasgos(kw)` en `huella_motor`, y
`neurona.py:391` descarta los pesos guardados si la huella no coincide. Una aguja
nueva cambia `rasgos()` → cambia la huella → **todas las bases reentrenan**. El
«es lo único que se toca» del informe anterior era falso.

### 3.5 Defecto de reproducibilidad, corregido

`scripts/barrido_bonus_sinonimos.py` escribía siempre el mismo JSON: la segunda
corrida sobreescribió la primera y quedaron 2 de los 5 valores que reporta este
documento. Corregido: cada corrida deja un fichero con fecha y con si la neurona
estaba activa o no.

### 3.6 Qué queda en pie

- El diagnóstico: el número de `sinonimo` depende del contenido de la base
  (a 150 nodos ya falla 13 de 61; el tamaño pesa menos que el solapamiento).
- Los dos experimentos negativos y sus reversiones.
- El cambio de objetivo: **no es el orden, es la generación**. Antes de tocar la
  neurona hay que hacer que el correcto entre al top-5.

---

## 4. Diagnóstico de los 6 fallos. Condiciones de la QA (veredicto P1 del auditor)

### 4.0 Correcciones aceptadas

- **0734 «regla» no estaba dormido en la QA.** `evaluar_qa.py` pone el nodo
  esperado en `activo` antes de preguntar (`UPDATE ... SET estado='activo'`) y
  restaura el estado después de cada caso. La medición anterior no lo hacía, así
  que los puestos de la tabla 3.2 no eran comparables. Repetidos aquí con el
  mismo protocolo: 0734 sube a puesto **21**, no «fuera».
- **«13 de 61 a 150 nodos» salió de un script propio, no de la QA oficial.**
  Queda como indicio, no como cifra. No se corre la QA de 13 minutos porque no
  cambia ninguna decisión (indicación del auditor).
- No se propone que la neurona vea más allá del top-5: ya se probó y se descartó.

### 4.1 No todos los fallos son iguales

Censo sobre la base viva (1357 nodos): cuántos recuerdos declaran la palabra en
el nombre y cuántos en el alias.

| ID | consulta | en nombre | en alias | veredicto |
|---|---|---:|---:|---|
| 0514 | perfil | 19 | 25 | **ambiguo**, no forzable |
| 0692 | metodologia | 7 | 14 | **ambiguo**, no forzable |
| 0710 | agente | 33 | 110 | **ambiguo**, no forzable |
| 0734 | regla | 30 | 73 | **ambiguo**, no forzable |
| 0805 | cv | 20 | 34 | **ambiguo**, no forzable |
| 0674 | filtro-arquitecto-prolijo | 0 | 0 | **fallo real** |

Los cinco primeros son una palabra suelta que decenas de recuerdos declaran. Con
`agente` y nada más, 110 recuerdos son respuestas legítimas. Pedir R@1 ahí es un
defecto del banco, no del cerebro.

### 4.2 Puesto real, con el protocolo de la QA

| ID | consulta | puesto | esperado |
|---|---|---:|---|
| 0514 | perfil | 9 | dennys-identidad-profunda |
| 0674 | filtro-arquitecto-prolijo | 18 | compuerta-pre-validacion |
| 0692 | metodologia | 6 | dennys-working-style |
| 0710 | agente | 6 | aforismo_criterio_agente |
| 0734 | regla | 21 | plan_mode_biorag |
| 0805 | cv | 13 | cv_seccion_d_test_vinculacion |

### 4.3 0674: el fallo real, y por qué pierde

La consulta `filtro-arquitecto-prolijo` contra el nodo `compuerta-pre-validacion`
(nombre: `compuerta-pre-validacion`; alias: `pre-validacion,compuerta,juicio-accion,filtro-de-impacto`).

Desglose de los 5 primeros:

| # | concepto | score | bm25 | concepto | sinónimo | grupo |
|---|---|---:|---:|---:|---:|---:|
| 1 | v13_filtro_temporal_pre_hoc_indices | 0.290 | 0.000 | **0.333** | 0.333 | 1.000 |
| 2 | bio_profesional_dennys_arquitecto_frontend | 0.287 | 0.000 | **0.333** | 0.333 | 1.000 |
| 3 | sesgos_ats_pantalla_filtrado_candidatos | 0.270 | 0.000 | 0.250 | 0.333 | 1.000 |
| 4 | identidad_dennys_perfil_completo | 0.241 | 0.000 | 0.000 | 0.333 | 1.000 |
| 5 | ajuste_tejedora_valencia_desempate_fase1 | 0.234 | 0.000 | 0.000 | 0.333 | 1.000 |
| **18** | **compuerta-pre-validacion** | **0.187** | **0.000** | **0.000** | 0.333 | 1.000 |

La causa, medida palabra por palabra:

| palabra | en nombre | en alias | en texto |
|---|---:|---:|---:|
| filtro | 1 | 14 | 81 |
| arquitecto | 1 | 4 | 9 |
| **prolijo** | **0** | **0** | **0** |

- **`prolijo` no existe en la base, en ninguna forma.** El motor tiene que decidir
  con 2 de 3 palabras.
- El «filtro» del nodo correcto vive en el **alias** (`filtro-de-impacto`);
  el de sus rivales vive en el **nombre**. `concepto_ratio` mira el nombre, así
  que el correcto saca 0.000 y los rivales 0.333. Eso decide el orden.
- `grupo` vale **1.000 en los cinco**. No distingue nada.

**Conclusión honesta:** 0674 no es un empate ambiguo, pero tampoco se arregla
reordenando ni con la neurona (puesto 18). Se arregla si (a) el nodo declara el
alias que la persona usa, o (b) algo une `prolijo` con `juicio-accion` /
`filtro-de-impacto`. Es un problema de puente léxico, no de orden.

### 4.4 Banco de agujas: dos señales están saturadas (295 candidatos top-5, 61 casos)

| señal | al máximo | % |
|---|---:|---:|
| `sinonimos_ratio` | 194 | **65.8 %** |
| `grupo_score` | 189 | **64.1 %** |
| `concepto_ratio` | 96 | 32.5 % |

Dos de las agujas valen lo mismo para dos tercios de los candidatos. Esto es la
explicación medible de por qué el resultado depende de la base: cuando dos
tercios empatan en las dos señales principales, decide la tercera, y la tercera
premia el nombre sobre el alias. La guía lo advierte (paso 4): señales que no
separan producen «ruido con apariencia de inteligencia».
