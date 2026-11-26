# H2 y 4b: propuesta de protocolo con criterios previos (2026-11-26). PARA REVISIÓN, nada implementado

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
  se usó en los Pasos 2b y 2c como diagnóstico; seguir usándolo requiere el OK explícito. Por ahora, el plan se
  evalúa sintéticamente.

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
**H2 (inhibición lateral):**
- [V] La condición equivale a «importancia media de los activos > 0,8» (cuando hay más de 12 activos). Un recuerdo
  nuevo entra con 1,0, así que **cada tanda de recuerdos nuevos sube la media y dispara H2**.
- [V] El recuerdo que se duerme se elige por su **puesto frente a los demás** (menor importancia y acceso más
  antiguo), no por su propio estado. Si llegan recuerdos ajenos, cambia quién queda último: **qué recuerdo de D se
  duerme depende de I**. Medido en 2c: 177 cambios de estado [V].
- [D] Sin uso y con sueños seguidos (fracción de noche pequeña, LTD casi nulo), las importancias se quedan cerca de
  1,0. Cada ciclo duerme del orden del 20 % de la masa activa, lo que es coherente con 622/839 dormidos tras 17
  ciclos. No lo he verificado numéricamente: se medirá en el mundo sintético (§6).
- [D] En una base real el uso sube la importancia de lo consultado. El efecto será menor, pero el mecanismo (puesto
  relativo) es el mismo.

**4b (escalado global de importancia):**
- [V] Depende de la media global de los activos. Añadir I (que entran con 1,0) sube la media y puede disparar el
  ×0,98 **sobre los recuerdos de D**: su importancia cambia por la llegada de recuerdos ajenos.
- [V] El ×0,98 conserva el orden entre los recuerdos escalados salvo empates por el redondeo a 2 decimales. Pero
  **cambia el orden frente a los inmunes** (que no se escalan) y **cambia valores absolutos** que se usan con
  umbrales (≤ 0,05), sumados a otras señales en el ranking (`peso_norm`) y en los pesos de nacimiento.
- [V] H2 y 4b están acoplados: H2 duerme a los de menor importancia → la media de los activos sube → 4b se dispara
  más; 4b baja importancias → cambia el orden de H2 en el ciclo siguiente.
- **2c no separó 4b:** el control C solo apagó H2; 4b estaba activo en T y en C. Nada de 2c se puede atribuir a 4b,
  ni descartarlo. Por eso el protocolo propone cuatro brazos (§7).

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
- **Criterio que se deriva:** apagar H2 sin más **no** es una solución aceptable. Una corrección de H2 no puede
  comprar la invariancia con una inundación de aristas (criterio K4).

## 5. Qué es invariancia y qué no (definiciones fijadas antes de medir)
En 2c llamé al «orden relativo de D» la forma correcta de la NORMA MÁXIMA. **Eso fue impreciso:** el orden relativo
tolera que entren recuerdos de I, y no comprobé si los que entraban tenían que ver con la consulta. Definición
previa, sin idioma y sin usar el motor, para cada recuerdo i de I frente a una consulta q:
- **R0 «contiene»:** comparte al menos una unidad exacta con q (unidades Unicode: palabras entre espacios; bigramas
  CJK). Puede entrar; la norma no lo protege.
- **R1 «cercano» (zona difusa):** no comparte unidades, pero:
  - en escritura con espacios, alguna unidad u de q de 4 o más caracteres comparte con una unidad de i un prefijo de
    al menos `max(4, ⌈0,7·|u|⌉)` caracteres (p. ej. «elecciones/elección» sí; «elección/electricidad» no);
  - en CJK, comparte un carácter que no es hiragana con una unidad de q.
- **R2 «irrelevante»:** ni R0 ni R1.

Medidas (se informan siempre por separado, nunca mezcladas):
| id | qué mide | sobre qué pistas |
|---|---|---|
| M1 | **Invariancia estricta** (NORMA MÁXIMA): top-k idéntico en D y D∪I | pistas para las que **todo** I es R2 |
| M2 | **Orden relativo de D** (no es invariancia completa: admite inserciones) | pistas sin ningún I en R0 |
| M3 | Inserciones de I en el top-k, clasificadas en R1 y R2. En el mundo sintético hay verdad de tema: un R1 del mismo tema es una **coincidencia difusa legítima**; uno de otro tema es un **falso positivo difuso**; un R2 que entra es una **violación** | todas |

Las inserciones R1 y R2 son propiedades del **buscador** (canal 1), no del sueño. En este ciclo solo se exige que no
empeoren; corregirlas, si hace falta, sería otro ciclo.

## 6. Mundo de evaluación: solo sintético, aislado (propuesta) [D]
Generador procedimental en el laboratorio, sin datos reales:
- **Semillas 7, 11 y 23** (las de la GUIA). Solo vale lo que se repite en las tres.
- **Cuatro escrituras:** latina con diacríticos (dos «lenguas» con inventarios de sílabas distintos), ideogramas y
  japonés mixto (kanji + kana). Hangul opcional como quinta, informada aparte.
- **Vocabulario:**
  - palabras aleatorias por escritura con frecuencias de Zipf;
  - palabras «función» de alta frecuencia compartidas por todos los temas (imitan a las palabras vacías, sin
    ninguna lista real);
  - vocabulario propio de cada tema;
  - **variantes morfológicas** (mismo prefijo, distinto sufijo), sembradas a propósito dentro de un tema y entre
    temas, para que R1 tenga casos de los dos tipos con verdad conocida.
- **Temas:** tamaños de 1 a 5 recuerdos como PUD, más algunos largos. Verdad = mismo tema.
- **Partición:** D/I por tema (80/20; I con temas disjuntos de D). Tamaños de 1000 y 3000 recuerdos, para medir
  la dependencia del crecimiento.
- **Reloj controlado,** dos regímenes: (a) comprimido (sueños seguidos, como el laboratorio); (b) un sueño por día
  simulado. LTD depende de la fracción de noche, y H2 y 4b de las importancias resultantes.
- **Sin uso** (decisión U0 de Dennys: ninguna señal de uso nueva).
- Bases en `/tmp`, con fixtures creadas desde cero. Nunca la DB viva ni snapshots.

## 7. Brazos de diagnóstico (laboratorio, sin tocar el repositorio)
Como el control de 2c: una copia del código del sueño en el proceso hijo, con la condición del bloque cambiada a
`if False:` y una comprobación de que el marcador aparece exactamente una vez.
| brazo | H2 | 4b |
|---|---|---|
| T | sí | sí |
| −H2 | no | sí |
| −4b | sí | no |
| −H2 −4b | no | no |
Los brazos **no son propuestas**: sirven para atribuir cada efecto a su mecanismo.

**Diseños candidatos [D]**, para conversar con Dennys antes de medir ninguno (norma 12). Cada uno sería un cambio
aislado, en su propio ciclo:
- H2-a: retirar H2 y dejar dormir solo por el peso propio (la regla 5 ya existe).
- H2-b: homeostasis **por recuerdo**: el presupuesto de cada recuerdo depende de su propia historia, no de su puesto
  frente a los demás.
- 4b-a: escalado por recuerdo (cada importancia tiende a su propio objetivo, sin mirar la media global).
- Cualquiera de ellos, combinado con un control de la inundación de aristas (K4), que podría venir del nacimiento
  (`pmi_hebbiano`) y no del sueño. Sería otro ciclo, para no mezclar cambios.

## 8. Criterios fijados antes (para cualquier cambio futuro en H2 o 4b)
Todos en el mundo sintético, en las 4 escrituras, con las 3 semillas, en los dos tamaños y en los dos regímenes de
reloj:
| id | criterio | umbral |
|---|---|---|
| K1 | Estado invariante: recuerdos de D que cambian de estado al añadir I irrelevante, sin uso | 0 |
| K2 | M1 ≥ 98 %; M2 ≥ 98 %; inserciones R2 y falsos positivos difusos (R1 de otro tema) | M1, M2 ≥ 98 %; inserciones ≤ las de T |
| K3 | Examen de orden: ninguna pregunta común cambia de puesto relativo; preguntas que faltan en D∪I | 0 cambios; faltan ≤ 2 % |
| K4 | Grafo sin inundación ni pérdida: aristas del mismo tema ≥ las de T **y** precisión del grafo ≥ la de T **y** grado medio ≤ 1,25 × el de T | las tres |
| K5 | Canal 2 visible (top-5 por recuerdo): fracción del mismo tema | ≥ la de T |
| K6 | Dormir solo por el propio recuerdo: todo recuerdo dormido cumple la regla por peso propio | 100 % |
| K7 | Crecimiento: K1–K5 se cumplen en 1000 y en 3000; costo por sueño | ≤ 1,2 × el de T por recuerdo nuevo |
| K8 | Ciclo desde DB vacía (5 recuerdos por sesión, 80 sesiones, GUIA §8.8): sin excepciones ni oscilaciones de estado; K1 al final | sí |
| K9 | Regresión: `pytest` completo en verde **sin modificar tests existentes**, más tests nuevos sintéticos para K1, K2 y K6 | sí |
La QA oficial sobre la DB real **no la corro yo**: la corre Dennys (GUIA §8.11), si él lo decide.
Lectura en 2c, para calibrar las expectativas: el control C habría cumplido K1, y M2 en las 4 lenguas, pero **habría
fallado K4** (precisión 6,4 % frente a 17,8 %).

## 9. Adaptación de la GUIA al examen de la neurona sináptica (canal 2)
Adaptar, no copiar: el canal 2 ordena los vecinos de un recuerdo A, no los resultados de una búsqueda.
| regla de la GUIA | ¿aplica al canal 2? | adaptación | cómo se prueba (sintético) |
|---|---|---|---|
| Agujas (PASO 4): 0–1, regla fija, universal, barata, determinista, auto-regulada, signo fijo, rareza | Sí, entera | Agujas del **par (A, B)**. **Sin bucle**: no leen la arista que juzgan ni el grafo sin copia limpia. Invariantes según la NORMA MÁXIMA. Candidatas en §9.0b del plan | AUC con verdad de tema; D frente a D∪I idéntico; dos corridas idénticas con `PYTHONHASHSEED=1`; ms por par |
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
  de I no se clasificaron como R1 o R2.
- «El orden relativo de D es la forma correcta de la NORMA MÁXIMA» → es una **medida parcial (M2)** que admite
  inserciones; la invariancia estricta es M1 (§5).
Ambas notas quedan añadidas al RESULTADOS de 2c y al plan.

## 12. Decisiones que pido en la revisión
1. ¿Se aprueba este protocolo (mundo sintético, brazos T/−H2/−4b/−H2−4b, criterios K1–K9) como paso siguiente,
   todavía sin cambiar el motor?
2. ¿H2 representa una intención de diseño que hay que conservar (un presupuesto de energía), o se puede proponer
   retirarla (H2-a)? La misma pregunta para 4b.
3. ¿Se aceptan las definiciones R0/R1/R2 y los umbrales de K2 y K4?
4. ¿Se autoriza seguir usando UD PUD (público, CC BY-SA 3.0) como segundo banco, o queda solo el sintético?
