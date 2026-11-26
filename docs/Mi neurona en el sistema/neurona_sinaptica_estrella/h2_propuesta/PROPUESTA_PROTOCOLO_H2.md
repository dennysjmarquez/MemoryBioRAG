# H2 y 4b: propuesta de protocolo con criterios previos — v2 corregida (2026-11-26). PARA REVISIÓN, nada implementado

[V] = verificado leyendo el código o en los JSON ya medidos. [D] = deducción o propuesta, sin medir.

## 0. Alcance y salvaguardas (lo que este documento NO hace)
- La evaluación del Paso 2c queda como **diagnóstico**: no autoriza cambios en H2, en 4b ni en el motor.
- **Nada implementado ni cambiado:** ni H2 (inhibición lateral), ni 4b, ni el filtro de pistas, ni el motor, ni los
  tests. E3 sigue abierto; no se avanza a E4.
- La revisión del código y de los tests de este documento es **estática** (lectura). **No se abrió ni copió la DB
  viva, no se usaron snapshots y no se ejecutó la QA oficial** sobre datos reales o privados.
- Toda comprobación de comportamiento futura será **solo con fixtures sintéticas aisladas** (§6), sin modificar los
  tests existentes.
- **Datos externos y preguntas humanas** requieren autorización y procedencia/licencia claras. UD PUD (CC BY-SA 3.0)
  se usó en los Pasos 2b y 2c como diagnóstico. **Decisión de la revisión: en esta etapa, solo mundo sintético**; UD
  PUD no se usa sin una autorización posterior.

## 1. Para quien llega sin contexto
Durante el «sueño» (`ciclo_sueno_consolidacion`) el motor ejecuta, entre otros, dos mecanismos **globales**: miran a
todos los recuerdos activos a la vez para decidir qué hacer con cada uno.
- **H2, inhibición lateral** (`core/memory/consolidation.py` L533–575): pone a dormir recuerdos.
- **4b, escalado global de importancia** (L577–588): multiplica por 0,98 la **importancia de los recuerdos**
  (`largo_plazo.peso_sinaptico`). **No toca los pesos de las aristas de la tabla `sinapsis`**, aunque el código lo
  llame «Synaptic Scaling».
En el Paso 2c, con frases reales y sin uso, H2 dejó dormidos 622 de 839 recuerdos. Añadir recuerdos de temas
ajenos (I) cambió el estado de 177 recuerdos que ya estaban. Eso rompe la NORMA MÁXIMA F(D,q) = F(D∪I,q).
Este documento propone cómo estudiar y, si Dennys lo autoriza, corregir esos mecanismos sin romper nada más.

## 2. Lectura estática del sueño [V]
Orden dentro de `ciclo_sueno_consolidacion` (L335 en adelante):
1. **Fusión** de corto a largo plazo: un recuerdo nuevo entra con importancia 1,0; uno que ya existía, +0,20.
2. **Nacimiento de aristas:** `auto_vincular`, co-ocurrencia de la sesión, DMN y latentes.
3. **LTD** de la importancia (L440–490), escalado por la fracción de noche real desde el sueño anterior (D15).
4. Decaimiento de aristas sin uso en 7 días y poda de aristas con peso < 0,05.
5. **Dormir por peso propio** (L513–531): duerme si la importancia es ≤ 0,05. Es una regla por recuerdo.
6. **H2** (L533–575):
   - `limite_energia = max(10, 0,8 × n_activos)` y `energia_total = Σ importancia de los activos`;
   - si la energía supera el límite, ordena a los activos no inmunes por `peso_sinaptico ASC, ultimo_acceso ASC` y
     duerme desde arriba hasta cubrir el exceso;
   - a cada recuerdo dormido le pone `importancia = max(0,05; round(importancia × 0,9; 2))`.
   El exceso se calcula **una vez por ciclo**.
7. **4b** (L577–588): si `AVG(importancia de los activos) > 0,70`, aplica `importancia = round(importancia × 0,98; 2)`
   a todos los activos no inmunes (incluidos los recién consolidados).
8. Registro, auto-clustering y vaciado de corto plazo.

**Quién lee lo que H2 y 4b cambian [V]:**
| lo que cambia | quién lo lee | dónde |
|---|---|---|
| `estado` (dormido) | canal 1 del agente: `recordar` usa `deep=False` → `profundidad="activos"` → filtra `estado='activo'` | `core/mcp_server/search.py` L157/L447; `core/memory/search.py` L371–372 |
| `estado` | canal 2: solo vecinos activos | `core/memory/synapses.py` L510/L537 |
| `estado` | nacimiento: `auto_vincular` (y por eso `pmi_hebbiano`, `co_nombre`, `co_semantica`) solo enlaza con activos | `core/sinapsis.py` (consultas con `l.estado = 'activo'`) |
| `peso_sinaptico` | ranking del canal 1 (`peso_norm = min(1, peso)`), salvo con `ignore_peso_sinaptico=True` | `core/memory/scoring.py` L307 |
| `peso_sinaptico` | orden de candidatos de `auto_vincular` (`0,5 + 0,5·peso`) y pesos de nacimiento (`co_nombre` 0,3·peso, `co_semantica` 0,4·peso, `pmi_hebbiano` 0,25·peso) | `core/sinapsis.py` |
| `peso_sinaptico` | umbral de dormir (≤ 0,05) y orden de H2 del ciclo siguiente | `consolidation.py` |

Consecuencia [V por lectura]: en el motor real, **un recuerdo dormido por H2 desaparece de la búsqueda normal del
agente** (canal 1 sin `deep`) y del canal 2. Despierta si se accede a él (búsqueda profunda o BFS).

## 3. Cómo depende cada mecanismo del crecimiento del corpus (separados)
**H2 (inhibición lateral)** (código: L535–544):
- [V] La condición es `energia_total > max(10, 0,8 × n_activos)`, donde `n_activos` y la energía cuentan a **todos**
  los activos, también a los inmunes.
  - Con `n_activos ≤ 10` no se puede disparar, porque la energía máxima es n × 1,0 ≤ 10.
  - Con 11 o 12 activos hace falta una energía mayor que 10.
  - **Solo con 13 activos o más** equivale a «importancia media de los activos > 0,8».
- [V] El chequeo ocurre **después** del LTD y de dormir por peso propio del mismo ciclo. Por eso **una tanda nueva
  dispara H2 solo si, con ella, la media supera 0,8**. Un recuerdo nuevo entra con 1,0 y sube la media, pero si
  muchos recuerdos ya bajaron de importancia, una tanda pequeña puede no dispararlo. (En la versión anterior de este
  documento dije que «cada tanda dispara H2»: no está demostrado y queda retirado. Se medirá ciclo a ciclo, §7.)
- [V] Cuando se dispara, el recuerdo que se duerme se elige por su **puesto frente a los demás** (menor importancia y
  acceso más antiguo, entre los no inmunes), no por su propio estado. Si llegan recuerdos ajenos, cambia quién queda
  último, así que **qué recuerdo de D se duerme puede depender de I**. Medido en 2c: 177 cambios de estado [V].
- [V] Los inmunes suman energía pero nunca se duermen: si pesan mucho, H2 cae entera sobre los no inmunes.
- [D] Sin uso y con sueños seguidos, la fracción de noche es pequeña y el LTD casi nulo; las importancias quedan
  cerca de 1,0 y es plausible que H2 se dispare en casi todos los ciclos. Coherente con 622/839 dormidos, pero **sin
  verificar**: el registro por ciclo del §7 lo dirá.
- [D] En una base real el uso sube la importancia de lo consultado. El efecto será distinto, pero el mecanismo
  (puesto relativo) es el mismo.

**4b (escalado global de importancia)** (código: L577–588):
- [V] Se dispara si `AVG(importancia de los activos) > 0,70` y multiplica por 0,98 (redondeo a 2 decimales) la
  importancia de los activos no inmunes.
- [V] **El problema de invariancia no es el ×0,98 en sí, sino el disparo.**
  - Si en un ciclo la media supera 0,70 tanto en D como en D∪I, el ×0,98 cae igual sobre los recuerdos de D en los
    dos mundos: no hay diferencia para ellos.
  - La diferencia aparece **en los ciclos en que I hace cruzar el umbral** (D por debajo y D∪I por encima, o al
    revés), y en el **efecto acumulado** de esos ciclos sobre las importancias de D. Además, H2 cambia quién está
    activo y, por tanto, la media sobre la que decide 4b.
- [V] El ×0,98 conserva el orden entre los recuerdos escalados salvo empates por el redondeo. Pero **cambia el orden
  frente a los inmunes** (que no se escalan) y **cambia valores absolutos** que se usan con umbrales (≤ 0,05), sumados
  a otras señales en el ranking (`peso_norm`) y en los pesos de nacimiento.
- [V] H2 y 4b están acoplados: H2 duerme a los de menor importancia → la media de los activos sube → 4b se dispara
  más; 4b baja importancias → cambia el orden de H2 en el ciclo siguiente.
- **2c no separó 4b:** el control C solo apagó H2; 4b estaba activo en T y en C. Nada de 2c se puede atribuir a 4b,
  ni descartarlo. Por eso el protocolo propone cuatro brazos y un registro por ciclo (§7).

## 4. Impacto del aumento de aristas observado en el control [V, de `paso2c_examen_orden_rescate/resultados/examen_2c.json`]
| | es T | es C | en T | en C | zh T = C | ja T = C |
|---|---|---|---|---|---|---|
| aristas (filas) | 643 | **1838** | 679 | **2224** | 566 | 1152 |
| pares no dirigidos | 642 | 1806 | 655 | 2138 | 566 | 1152 |
| `pmi_hebbiano` | 374 | **1576** | 279 | **1845** | 0 | 0 |
| `co_ocurrencia` | 262 | 236 | 391 | 337 | 566 | 1152 |
| pares del mismo documento | **114** | **115** | **143** | **138** | 242 | 299 |
| precisión (mismo documento) | 17,8 % | **6,4 %** | 21,8 % | **6,5 %** | 42,8 % | 25,9 % |
| vecinos medios de A en el examen de orden | 3,9 | 10,8 | 5,2 | 10,6 | 3,5 | 3,9 → 4,9 |

Lectura:
- Al apagar H2, las aristas de es/en casi se triplican, pero **los pares del mismo documento no aumentan** (114 → 115
  y 143 → 138). Casi todo lo nuevo es `pmi_hebbiano` entre documentos distintos, y la precisión del grafo cae de
  ~18–22 % a ~6,5 %.
- [D] Hoy H2 actúa como un **freno accidental** de `pmi_hebbiano`, que solo enlaza con recuerdos activos. Algunas
  aristas nuevas pueden ser puentes temáticos válidos; la métrica del mismo documento no lo distingue. No está
  verificado.
- Las listas del canal 2 se duplican en largo: B compite con más vecinos (el MRR del piso baja de 0,81 y 0,71 a 0,57 y 0,58).
- zh/ja no cambian porque `pmi_semantico` no tokeniza CJK (§9.3 del plan). Si un día lo hace, el mismo efecto
  aparecería allí.
- **Criterio que se deriva:** apagar H2 sin más **no** se acepta a ciegas. Una corrección de H2 no puede comprar la
  invariancia con más aristas **accidentales**. Pero la métrica del mismo documento no separa puentes válidos de
  accidentes, así que K4 se mide en el mundo sintético con las tres clases etiquetadas (§5.2, §8).

## 5. Coincidencia de texto, relevancia y qué es invariancia (definiciones fijadas antes de medir)
En la versión anterior, R0/R1/R2 mezclaban coincidencia de texto con relevancia. Ahora van **separadas**, y la
relevancia viene de una **verdad sintética independiente del texto por construcción** (§6).

**5.1 Coincidencia de texto** (se calcula sobre el texto, sin idioma y sin el motor). Para un recuerdo i frente a una
consulta q:
- **C0 «comparte unidad»:** al menos una unidad exacta en común (palabras entre espacios; bigramas CJK).
- **C1 «cercano»:** ninguna unidad en común, pero:
  - en escritura con espacios, alguna unidad u de q de 4 o más caracteres comparte con una unidad de i un prefijo de
    al menos `max(4, ⌈0,7·|u|⌉)` caracteres;
  - en CJK, comparte un carácter que no es hiragana.
- **C2 «sin coincidencia»:** ni C0 ni C1.
Esto **no dice si i es relevante**: una palabra genérica o un homógrafo dan C0 sin relación alguna.

**5.2 Verdad de relación** (la pone el generador al construir el mundo, no se deduce del texto). Para dos recuerdos,
o para un recuerdo y el recuerdo del que sale la consulta:
- **V-tema:** mismo tema.
- **V-puente:** temas distintos unidos **a propósito** por un rasgo compartido declarado (p. ej. la misma entidad en
  dos historias). Es un puente válido (criterio del usuario del 25-11).
- **V-accidental:** comparten texto sin relación: homógrafos (la misma cadena con dos «sentidos» en temas sin
  relación), palabras función, prefijos casuales.
- **V-ajeno:** ninguna de las anteriores.
El generador pone los puentes y los homógrafos de forma que el texto **no** permita distinguirlos: un puente y un
accidente pueden ser C0 los dos. Así la verdad no se filtra por el texto.

**5.3 Invariancia: una exigencia estricta y métricas aparte**
- **I verdaderamente irrelevante** para una consulta q, que sale de un recuerdo de D: todo recuerdo de I es V-ajeno
  frente a todo D (temas de I disjuntos, sin puentes con D, sin homógrafos compartidos con D) **y** es C2 frente a q.
  El motor no tiene ninguna razón legítima para cambiar nada.
- **S1, invariancia estricta del sueño:** con I verdaderamente irrelevante y sin uso, **0** cambios en el estado y en
  la importancia de los recuerdos de D, y **0** cambios en el top-k de esas consultas atribuibles a H2 o 4b. Es una
  exigencia de cero, no un porcentaje.
- **Atribución:** un cambio del top-k «atribuible a H2/4b» es uno que no aparece en el brazo −H2 −4b (§7). Los
  cambios que sí aparecen con los dos mecanismos apagados son del **buscador** (p. ej. estadísticas del corpus): se
  informan aparte, se miden igual y no se cargan a este ciclo.
- **Métricas agregadas, que no son invariancia y se informan siempre por separado:**
  | id | qué mide | sobre qué consultas |
  |---|---|---|
  | M1 | Fracción de top-k idénticos en D y D∪I | consultas con I verdaderamente irrelevante |
  | M2 | Fracción con el orden relativo de D conservado (admite inserciones) | consultas sin ningún I C0 |
  | M3 | Inserciones de I en el top-k, cruzando texto (C0/C1/C2) con verdad (tema, puente, accidental, ajeno) | todas |
  Lectura de M3: un I V-tema o V-puente que entra es una inserción legítima. Uno V-accidental es un **falso positivo
  difuso**. Uno V-ajeno y C2 que entra es una **violación** (y cuenta en S1 si es atribuible a H2/4b).

Las inserciones del buscador (C1 y C2) son propiedades del canal 1, no del sueño. En este ciclo solo se exige que no
empeoren; corregirlas sería otro ciclo.

## 6. Mundo de evaluación: solo sintético, aislado (propuesta) [D]
Decisión de la revisión: **solo mundo sintético** en esta etapa. UD PUD no se usa sin una autorización posterior.
Generador procedimental en el laboratorio, sin datos reales:
- **Semillas 7, 11 y 23** (las de la GUIA). Solo vale lo que se repite en las tres.
- **Cuatro escrituras:** latina con diacríticos (dos «lenguas» con inventarios de sílabas distintos), ideogramas y
  japonés mixto (kanji + kana). Hangul opcional como quinta, informada aparte.
- **Vocabulario:**
  - palabras aleatorias por escritura con frecuencias de Zipf;
  - palabras «función» de alta frecuencia compartidas por todos los temas (imitan a las palabras vacías, sin ninguna
    lista real);
  - vocabulario propio de cada tema;
  - variantes morfológicas (mismo prefijo, distinto sufijo) dentro de un tema y entre temas.
- **Verdad por construcción** (§5.2):
  - **temas** de 1 a 5 recuerdos, como PUD, más algunos largos;
  - **puentes:** pares de temas declarados que comparten una entidad rara en algunos recuerdos de cada uno;
  - **homógrafos:** cadenas idénticas asignadas a dos temas sin relación, con contextos distintos;
  - **prefijos casuales** entre temas.
  Cada par de recuerdos queda etiquetado tema / puente / accidental / ajeno en un archivo aparte que **el motor no
  ve**.
- **Partición D/I:**
  - un I **verdaderamente irrelevante** (temas disjuntos, sin puentes ni homógrafos con D) para S1 y M1;
  - un I′ **con** puentes y homógrafos hacia D, para M2, M3 y para ver cómo crece el grafo con relaciones reales.
  Tamaños de 1000 y 3000 recuerdos, para medir la dependencia del crecimiento.
- **Reloj controlado,** dos regímenes: (a) comprimido (sueños seguidos, como el laboratorio); (b) un sueño por día
  simulado.
- **Sin uso** (decisión U0 de Dennys).
- Bases en `/tmp`, con fixtures creadas desde cero. Nunca la DB viva ni snapshots.

## 7. Brazos de diagnóstico y registro por ciclo (laboratorio, sin tocar el repositorio)
Como el control de 2c: una copia del código del sueño en el proceso hijo, con la condición del bloque cambiada a
`if False:` y una comprobación de que el marcador aparece exactamente una vez.
| brazo | H2 | 4b |
|---|---|---|
| T | sí | sí |
| −H2 | no | sí |
| −4b | sí | no |
| −H2 −4b | no | no |
Los brazos **no son propuestas**: sirven para atribuir cada efecto a su mecanismo.

**Registro por ciclo, en cada brazo y en cada mundo (D, D∪I, D∪I′):**
- n_activos (total e inmunes), energía y límite;
- si H2 se disparó, cuántos recuerdos durmió y cuáles;
- `AVG` de importancia antes de 4b y si 4b se disparó.
Se obtiene con una **instrumentación de solo lectura** en la misma copia del código fuente: una línea de registro
justo después de `energia_total = …` y de `peso_medio_activo = …`, que no cambia ninguna decisión. Se comprueba que
la base final es idéntica con y sin registro (sha256 por tabla).

Con ese registro se informa, sin suponer nada:
- **en qué ciclos concretos se dispara H2** en cada brazo y mundo;
- **en qué ciclos 4b cruza el umbral 0,70** en D∪I y no en D (o al revés);
- **el efecto acumulado** de esos ciclos sobre la importancia de los recuerdos de D: suma de |Δ importancia| y
  número de recuerdos de D con importancia distinta al final.

**Diseños candidatos [D]**, para conversar con Dennys antes de medir ninguno (norma 12). H2 y 4b son
**controles/hipótesis a evaluar**: ni intocables ni retirables sin evidencia (decisión de la revisión). Cada diseño
sería un cambio aislado, en su propio ciclo:
- H2-a: retirar H2 y dejar dormir solo por el peso propio (la regla 5 ya existe).
- H2-b: homeostasis **por recuerdo**: el presupuesto de cada recuerdo depende de su propia historia, no de su puesto
  frente a los demás.
- 4b-a: escalado por recuerdo (cada importancia tiende a su propio objetivo, sin mirar la media global).
- Cualquiera de ellos, combinado con un control de las aristas accidentales (K4), que podría venir del nacimiento
  (`pmi_hebbiano`) y no del sueño. Sería otro ciclo, para no mezclar cambios.

## 8. Criterios fijados antes (para cualquier cambio futuro en H2 o 4b)
Todos en el mundo sintético, en las 4 escrituras, con las 3 semillas, en los dos tamaños y en los dos regímenes de
reloj. **Exigencias** (hay que cumplirlas):
| id | criterio | umbral |
|---|---|---|
| K1 = S1 | Invariancia estricta del sueño con I verdaderamente irrelevante y sin uso: cambios de estado y de importancia en D; cambios del top-k atribuibles a H2/4b | **0** (no es un porcentaje) |
| K2 | Métricas agregadas M1, M2 e inserciones M3 | no peores que en T. Informadas por separado, con su número exacto, sin «≥ 98 %» que oculte casos |
| K3 | Examen de orden con I verdaderamente irrelevante: preguntas comunes que cambian de puesto relativo; preguntas que faltan | **0** y **0** |
| K4 | Aristas, separadas por verdad: **temáticas** ≥ T; **puentes válidos** ≥ T; **accidentales** ≤ T; precisión (temáticas + puentes) / total ≥ T; grado medio ≤ 1,25 × T | todas |
| K5 | Canal 2 visible (top-5 por recuerdo): fracción temática + puente | ≥ la de T |
| K6 | Dormir solo por el propio recuerdo: todo recuerdo dormido cumple la regla por peso propio | 100 % |
| K7 | Crecimiento: K1–K5 en 1000 y en 3000; costo por sueño | ≤ 1,2 × el de T por recuerdo nuevo |
| K8 | Ciclo desde DB vacía (5 recuerdos por sesión, 80 sesiones, GUIA §8.8): sin excepciones ni oscilaciones de estado; K1 al final | sí |
| K9 | Regresión: `pytest` completo en verde **sin modificar tests existentes**, más tests nuevos sintéticos para K1, K6 y el disparo de 4b | sí |

**Se informan, sin umbral** (para entender el mecanismo):
- el registro por ciclo del §7 (disparos de H2 y 4b, ciclos de cruce de 0,70, efecto acumulado);
- los cambios del buscador que aparecen con −H2 −4b (atribuidos al canal 1, no a este ciclo).

La QA oficial sobre la DB real **no la corro yo**: la corre Dennys (GUIA §8.11), si él lo decide.
Lectura en 2c, para calibrar las expectativas: con la métrica vieja de «mismo documento», el control C cumplía K1
pero las aristas fuera del documento pasaban de 528 a 1691 en es. Con K4 nuevo eso se juzga separando puentes de
accidentes, que en el mundo sintético están etiquetados.

## 9. Adaptación de la GUIA al examen de la neurona sináptica (canal 2)
Adaptar, no copiar: el canal 2 ordena los vecinos de un recuerdo A, no los resultados de una búsqueda.
| regla de la GUIA | ¿aplica al canal 2? | adaptación | cómo se prueba (sintético) |
|---|---|---|---|
| Agujas (PASO 4): 0–1, regla fija, universal, barata, determinista, auto-regulada, signo fijo, rareza | Sí, entera | Agujas del **par (A, B)**. **Sin bucle**: no leen la arista que juzgan ni el grafo sin copia limpia. Invariantes según la NORMA MÁXIMA. Candidatas en §9.0b del plan | AUC con la verdad sintética (tema / puente / accidental / ajeno); D frente a D∪I idéntico; dos corridas idénticas con `PYTHONHASHSEED=1`; ms por par |
| Semillas 7/11/23 | Sí | Se siembran el generador del mundo, las particiones y el entrenamiento; solo cuenta lo que se repite en las tres | Informe por semilla; una puerta pasa solo si pasa en las tres |
| Guardia (20 %, `sha256(nombre)[:8] % 5 == 0`) | Sí, cambiada | La unidad es el **par**: partición por **tema de B** en estudio / validación / guardia sellada (§8.3 y §9.2). Sin pares relacionados a ambos lados (decisión de Dennys): se excluyen los pares con A y B en partes distintas | Comprobación automática de que ningún tema cae en dos partes y de que no hay pares que crucen |
| Ciclo de DB vacía (norma 5, §8.8) | Sí | Sin examen suficiente no hay campeón: el canal 2 queda **idéntico al piso** (orden por prioridad de tipo) | Crecimiento sintético desde cero: canal 2 idéntico al piso hasta juntar el mínimo; se registra cuándo lo junta |
| Solo permuta lo que el motor eligió | Sí | La neurona solo reordena la lista del canal 2; no añade ni quita; manuales primero; ≤ 2 `sinonimo_explicito`; nunca oculta | Mismo conjunto antes y después; manuales en cabeza |
| Mismos números por posición; permutar mapas del MCP | **No** tal cual | En el canal 2 el agente lee el tipo y la fuerza de **cada arista**: los atributos viajan con su arista y no se reasignan por posición. El canal 2 no pasa por GABA ni por los FP del canal 1 | Cada vecino conserva su `tipo_sinapsis` y su `fuerza_arista` |
| Regla de identidad | Adaptada | Los enlaces `manual` y `sinonimo_explicito` mantienen su prioridad | Test de orden de prioridad |
| Guardia que nunca se estudia + anti-memorización | Sí | Igual, con guardia por tema | Reinicio si estudio sube y guardia no |
| Piso por categoría y camino | Adaptado | Piso por escritura/idioma, por tipo de arista y por tipo de cuerpo (§9.2.4) | Ninguna celda por debajo del piso |
| Campeón τ = 1 y margen ε «primero no dañar» | Sí | Igual, sobre R@1/MRR de B en la lista de A | Puertas de ascenso |
| DB cambió → recalibrar; `huella_motor` | Sí | La huella incluye la versión del nacimiento y del sueño (H1, H2, 4b) | Cambiar la huella fuerza a reaprender |
| NaN/Inf, divergencia, estado corrupto | Sí | Igual | Tests de `_sano`, carga corrupta → piso |
| Silencio por hilo | Sí, y más | Las búsquedas del examen no escriben log, ACT-R ni DMN, **y no crean aristas** | sha256 por tabla antes y después (como C6 de 2c) |
| Candado, multi-proceso, disyuntor | Sí | Igual | Tests de concurrencia sintéticos |
| Costo fijo | Sí | Número fijo de preguntas por sueño y presupuesto de tiempo | Costo constante con 1000 y 3000 recuerdos |
| Un recuerdo acapara el examen | Sí | Tope por A (O3) y por B | Puerta de hubs |
| Purga de olvidados | Sí, con cuidado | Un B dormido sale del examen; con H2 tal cual se purgaría el 74 %: otra razón para resolver H2 antes | Purga sintética |
| Interruptor | Sí | `BIORAG_NEURONA_SINAPTICA=0` → canal 2 idéntico al piso | Test de identidad |
| Dos caminos (agente/crudo), desfase 0 | Adaptado | El canal 2 tiene un solo camino (`obtener_asociaciones_enriquecidas`); el examen debe usar exactamente esa función | Mismo resultado en el examen y en el MCP |
| Preguntas humanas (§8.7) | Pendiente | Requieren autorización y licencia clara | — |

## 10. Revisión estática de los tests [V]
- **Ningún test cubre H2 ni 4b.** En `tests/` no aparece `energia_total`, `limite_energia`, `peso_medio_activo`, el
  umbral 0,70 ni «Inhibición». Hoy se puede cambiar cualquiera de los dos sin que falle ningún test.
- Tests que corren el sueño completo, y que un cambio en H2/4b podría afectar:
  - `test_enlaces_del_agente_intocables.py`
  - `test_neurona.py`
  - `test_sustantivos_clave_instalacion.py`
  - `test_sustantivos_clave_schema.py`
  - `test_ltd_por_tiempo_y_sinonimos_estables.py`
  - `test_manual_intocable_en_nacimiento.py`
  - `test_sinonimos_coincidencia_exacta.py`
- Tests que dependen del estado dormido, y fijan contratos que deben seguir en verde:
  - `test_bfs_wake_on_access.py` (despertar al acceder);
  - `test_escala.py` (dormidos fuera del índice activo);
  - `test_multihop_expansion.py` (un vecino dormido nunca entra);
  - `test_neurona.py` (sin dormidos en el examen);
  - `test_metricas_historial.py` (columna `nodos_dormidos_ciclo`).
- **Propuesta (no escrita, porque no está autorizado):** tests nuevos y sintéticos para:
  - K1: estado invariante al añadir I irrelevante;
  - K6: dormir solo por peso propio;
  - el disparo de 4b por la media global.
  Se escribirán **solo** si se aprueba el ciclo de cambio, y sin tocar los existentes.

## 11. Correcciones de redacción a 2c
- En 2c escribí «H2 es la única causa real de la falta de invariancia». Más preciso: **H2 explica la diferencia
  entre T y C** (cambios de estado y reordenamientos que desaparecen al apagarla). 4b no se aisló, y las inserciones
  de I no se clasificaron por texto (C0/C1/C2) ni por verdad (tema, puente, accidental, ajeno).
- «El orden relativo de D es la forma correcta de la NORMA MÁXIMA» → es una **métrica agregada (M2)** que admite
  inserciones. La invariancia estricta es S1: 0 cambios frente a I verdaderamente irrelevante (§5.3).
Ambas notas quedan añadidas al RESULTADOS de 2c y al plan.

## 12. Decisiones de la revisión del 2026-11-26 (registradas)
1. **Protocolo:** queda como borrador. Medir se aprobará solo después de revisar esta versión corregida.
2. **H2 y 4b:** son controles/hipótesis a evaluar, ni intocables ni retirables sin evidencia.
3. **Definiciones y criterios:** ajustados:
   - texto separado de la verdad (§5.1–5.2);
   - invariancia estricta = 0, aparte de las métricas agregadas (§5.3, K1, K2);
   - K4 separa aristas temáticas, puentes válidos y accidentales.
4. **Corpus:** solo mundo sintético en esta etapa; UD PUD no se usa sin una autorización posterior.
Sin cambios en H2, 4b, filtro, motor ni tests. E3 sigue abierto; no se avanza a E4.

## 13. Registro de cambios
- **v1** (`01f719f`): primera propuesta.
- **v2** (este documento), cuatro correcciones de la revisión:
  1. relevancia ≠ coincidencia de texto (C0/C1/C2 frente a la verdad sintética tema / puente / accidental / ajeno);
  2. la invariancia estricta es 0 cambios frente a I verdaderamente irrelevante; M1/M2 son métricas aparte;
  3. K4 deja de castigar los puentes válidos;
  4. H2 descrito con su condición exacta (≥ 13 activos, después del LTD) y registro por ciclo de los disparos de H2
     y de los cruces de 0,70 de 4b.
