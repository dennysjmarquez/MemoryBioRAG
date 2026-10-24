# Experimento 10 — Las neuronas del motor (la base de todo)

> **Idea (Dennys):** *"Convertir el propio motor en un cerebro modular."* Poner neuronas pequeñas en
> puntos clave del motor de búsqueda — cada una hecha con el mismo método que la neurona del
> ranking — para que el sistema esté **vivo**, aprenda solo y algún día **no necesite ninguna IA
> externa**.
>
> **Este documento es la base.** Junta todo lo que hablamos: la teoría, las normas, el molde de una
> neurona BioRAG, el banco de calibración, el mapa del motor y de la base de datos, las mediciones
> que hicimos, las correcciones de honestidad, las ideas de Dennys y el orden de trabajo.
>
> **Estado:** estudio y plan. **No se cambió ni una línea del motor. No se tocó ninguna DB real.**
> Todas las mediciones se hicieron sobre una **copia** del snapshot, solo lectura de resultados.
>
> **Primer candidato elegido por Dennys:** la **neurona de sinapsis**, la que reemplaza a la
> hormiguita (el daemon que hoy usa Gemini para limpiar el grafo). Sección 9.

---

## Índice

0. [En una línea por hallazgo](#0-en-una-línea-por-hallazgo)
1. [De dónde sale esta idea](#1-de-dónde-sale-esta-idea)
2. [Las normas (las reglas de Dennys)](#2-las-normas-las-reglas-de-dennys)
3. [El molde: cómo es una neurona BioRAG](#3-el-molde-cómo-es-una-neurona-biorag)
4. [El banco de calibración (las agujas)](#4-el-banco-de-calibración-las-agujas)
5. [Mapa del motor y de la base de datos](#5-mapa-del-motor-y-de-la-base-de-datos)
6. [Mediciones de esta etapa (A, B, C, D)](#6-mediciones-de-esta-etapa-a-b-c-d)
7. [Dónde poner neuronas (candidatos)](#7-dónde-poner-neuronas-candidatos)
8. [Lo que enseña la historia de BioRAG (lo que NO hay que repetir)](#8-lo-que-enseña-la-historia-de-biorag)
9. [Primer candidato: la neurona de sinapsis (adiós hormiguita)](#9-primer-candidato-la-neurona-de-sinapsis)
10. [Ideas grandes para después (sistema vivo)](#10-ideas-grandes-para-después-sistema-vivo)
11. [Correcciones de honestidad](#11-correcciones-de-honestidad)
12. [Orden de trabajo](#12-orden-de-trabajo)
13. [Preguntas abiertas para Dennys](#13-preguntas-abiertas-para-dennys)
14. [Cómo reproducir las mediciones](#14-cómo-reproducir-las-mediciones)
15. [La neurona asociativa (aporte de la conversación con Manus)](#15-la-neurona-asociativa-aporte-de-la-conversación-con-manus)

16. [Lo que queda claro: la neurona asociativa en una página](#16-lo-que-queda-claro-la-neurona-asociativa-en-una-página)
17. [La neurona como intermediaria, y cómo lo hace el hipocampo](#17-la-neurona-como-intermediaria-y-cómo-lo-hace-el-hipocampo)

Anexos: [A — Conversación completa Dennys ↔ Manus](anexo_A_conversacion_dennys_manus.md) · [B — Segunda parte: neurona universal y momento de la sinapsis](anexo_B_conversacion_dennys_manus_2.md)

---

## 0. En una línea por hallazgo

1. **El ranking no se toca.** Las neuronas nuevas van en el **motor** (cómo se juntan los
   candidatos y el grafo), no en cómo se ordenan.
2. **Toda neurona nueva nace igual que la del ranking:** primero una **fórmula a mano**, calibrada
   en un banco de pruebas (= el piso). Encima, la neurona que aprende, con **techo** y **examen**.
3. **El motor crudo ya trae casi todas las respuestas:** con el autoexamen, la respuesta correcta está en
   el top-10 en el **93.7 %** de las preguntas; en la QA oficial, en el top-5 en el **98.8 %**.
   Lo que falta, falta **cerca**: de las respuestas que no llegan, el **41 %** está a 1 salto de
   grafo y el **50 %** a 2 saltos.
4. **Pero el grafo está muy tupido:** ~**33 conexiones por recuerdo**. Un salto "a ciegas" trae
   ~215 candidatos para encontrar 1. Por eso **la neurona de saltos y la neurona de sinapsis son
   dos mitades del mismo circuito**: una sola no sirve.
5. **La hormiguita (Gemini) ya se equivocó mucho:** de las **6,870** conexiones que mandó a
   cuarentena, **2,681 (39 %)** tuvieron que volver porque el propio examen de seguridad vio que la
   memoria empeoraba. Y su **confianza no predice si acierta**: las cortadas con confianza 1.0 son
   las que **más** volvieron (54 %).
6. **"No tiene relación de significado" ≠ "no sirve".** Como en el cerebro humano, una asociación
   rara puede ser la que te lleva al recuerdo. Por eso la neurona de sinapsis **no juzga por
   significado, juzga por utilidad medida**: ¿esta conexión ayuda a llegar a respuestas correctas o
   solo trae ruido? (Sección 9.4.)
7. **Nada se borra.** La neurona de sinapsis solo **atenúa** o manda a **cuarentena reversible**.
   Las conexiones que el usuario declaró (`manual`, `sinonimo_explicito`) quedan protegidas.
8. **La utilidad se mide y separa bien (medición D):** por cada 1,000 conexiones miradas, una
   `manual` lleva a la respuesta correcta **13.2** veces, una `co_semantica` **8.3**, una
   `pmi_hebbiano` **1.8** y el azar **1.2**. Las que la hormiguita tiene en cuarentena: **1.6**
   (la mitad que las activas, pero no cero: 192 veces habrían unido un resultado con la respuesta).
9. **La neurona de sinapsis crece y pasa a ser la neurona asociativa** (sección 15, aporte de la
   conversación con Manus): además de sanar conexiones, decide **cuáles deben formarse**, por varias
   características compartidas y por experiencia. El inventario muestra que el motor ya da muchas
   agujas **de parecido**, pero las **estructurales** (entidades núcleo, relaciones quién-qué-a-qué,
   episodio, contradicción) están vacías o no existen: ahí va el cambio del MCP que propuso Dennys.
10. **Una neurona pre-entrenada en el corpus de Dennys no es garantía para otro corpus.** Ya lo
   medimos en el Exp 08: un campeón transferido **perjudicó**. Puede viajar de fábrica como
   **retadora**, pero solo trabaja si **gana el examen local**.

---

## 1. De dónde sale esta idea

Después de la v34.1 (la neurona del ranking aprende sola), Dennys propuso dar el siguiente paso.
Estas son sus ideas, en sus palabras o casi:

| # | Idea de Dennys | Qué significa para el diseño |
|---|---|---|
| 1 | *"Neuronas modulares en puntos clave del motor."* | Varias neuronas chicas, cada una con UNA tarea, no una red grande. |
| 2 | *"Respetar la velocidad del motor; SQLite + Python es rápido. Nada de redes neuronales pesadas."* | Cada neurona cuesta **tiempo constante** por consulta y por consolidación. |
| 3 | *"El ranking no se toca."* | La fórmula a mano + la neurona del ranking (v34) quedan exactamente igual. |
| 4 | *"Primero pesos a mano calibrados, como hice yo con el ranking. Después la neurona que aprende arriba."* | El **molde** (sección 3). |
| 5 | *"Las agujas tienen que llegar calibradas a mano; yo elijo las agujas."* | El **banco de calibración** (sección 4). Dennys aprueba cada entrada. |
| 6 | *"Quiero el sistema vivo. Que nazcan neuronas, que se repliquen solas."* | Neurogénesis controlada (sección 10). Para después. |
| 7 | *"Una neurona pre-entrenada con mi corpus sirve para cualquier corpus, es el mismo motor."* | Parcialmente cierto: ver sección 11 (corrección honesta). |
| 8 | *"Quiero sacar a la hormiguita; que el sistema no dependa de una IA externa."* | Primer candidato (sección 9). |
| 9 | *"Cuidado: a lo mejor sinapsis que parecen sin relación son asociaciones legítimas, como en el cerebro humano. No dañar, potenciar."* | Juzgar por **utilidad**, no por significado (9.4). Cuarentena, nunca borrar. |
| 10 | *"Tienes libertad para encontrar mejores lugares."* | Lista de candidatos (sección 7). |
| 11 | *"Una sola mente: el agente y BioRAG son un solo cerebro."* | Las neuronas no le piden trabajo extra al agente ni usan feedback. |

Resumen de Manus que Dennys aprobó: *"convertir el propio motor en un cerebro modular"*.

---

## 2. Las normas (las reglas de Dennys)

Estas reglas valen para **todas** las neuronas del motor. Si una propuesta rompe una, se descarta.

**Sobre el sistema**

1. **El recall nunca baja.** La tabla de QA de Dennys es el **piso**: ningún valor puede quedar
   por debajo. Hoy (después del despertar): R@5 **100**, R@1 **94.06**, MRR **.964**.
2. **El ranking no se toca.**
3. **Velocidad:** cada operación en **tiempo constante**. Nada que recorra toda la DB en cada
   consulta.
4. **Sin feedback del agente.** No se usa `feedback`, no se registra qué usó el agente, no se le
   pide trabajo extra.
5. **Funciona desde una DB vacía** para terceros que nunca van a correr la QA.
6. **Se vende solo el motor.** La neurona tiene que aprender en la máquina del cliente.
7. **Nunca se borran recuerdos.** Para conexiones: cuarentena reversible, nunca borrado directo.
8. **Ninguna DB real se toca en experimentos.** Todo en una copia del snapshot.

**Sobre cada neurona**

9. **Piso a mano:** primero una fórmula/tabla calibrada a mano. La neurona que aprende nunca
   puede quedar por debajo de ese piso.
10. **Techo:** aprende hasta un límite y para (aprender, no memorizar). Si el rendimiento baja,
    vuelve a aprender.
11. **Aprende en vivo, de a poco**, con su propio autoexamen (preguntas generadas de los propios
    recuerdos, con respuesta conocida). Nada de etiquetas externas.
12. **Campeón / guardia / techo**, igual que la v34: la neurona nueva solo reemplaza a la vieja si
    **gana el examen de control**.
13. **Tiene que ser perfecta:** probar todos los modos de falla; si falta una capa de protección,
    se crea.

**Sobre cómo trabajamos**

14. **Primero se conversa, después se mide.** Ninguna medición de una idea nueva sin hablarlo.
15. **Primero medir el piso, después cambiar, después medir de nuevo.** Un cambio aislado por vez.
16. **Rama propia, PR, y Dennys audita y hace el merge.** Ningún agente hace merge a master.
17. **Resultados presentables a un auditor:** números exactos, scripts incluidos, sin exagerar.

---

## 3. El molde: cómo es una neurona BioRAG

Cada neurona del motor se construye con las mismas 7 piezas. Es exactamente lo que ya funciona en
la neurona del ranking (v34/v34.1), pero generalizado.

```
            ┌──────────────────────────────────────────────────────────┐
  agujas    │ 1. ENTRADAS (agujas)  calibradas a mano en el banco       │
  ────────► │ 2. PISO               fórmula / tabla a mano (Dennys)     │
            │ 3. NEURONA            pesos chicos que aprenden ENCIMA    │
            │ 4. AUTOEXAMEN         preguntas con respuesta conocida    │
            │ 5. CAMPEÓN            solo gana si mejora el control      │
            │ 6. TECHO              deja de aprender al llegar          │
            │ 7. COSTO FIJO         tiempo constante, siempre           │
            └──────────────────────────────────────────────────────────┘
                                   │
                                   ▼  decisión (mantener / ajustar / cuarentena)
```

| Pieza | Qué es | En la neurona del ranking (ya existe) |
|---|---|---|
| 1. Agujas | Las señales de entrada, cada una en una escala conocida (0–1). | 6 señales: BM25, PPMI, temática, etc. |
| 2. Piso | La fórmula a mano. Si la neurona no está lista, **manda el piso**. | Los pesos a mano de Dennys. |
| 3. Neurona | Unos pocos pesos que corrigen al piso según el contexto. | Pesos por contexto, softmax, 30 pasos Adam. |
| 4. Autoexamen | Preguntas generadas de los recuerdos (`neurona_examen.preguntas`). Estudio + control (sha256 % 5 == 0). | 150 de estudio + 40 de control mínimo. |
| 5. Campeón | La neurona nueva se promueve solo si gana al campeón en control (`_calibrar`). | Piso del campeón (Exp 08). |
| 6. Techo | Límite de práctica por recuerdo y meseta: para de aprender. | `tope_nodo` 4, meseta. |
| 7. Costo fijo | Presupuesto de tiempo y tamaño constante. | 1 práctica por consolidación, ≤ 3 s, 8×7 preguntas a lo ancho. |

**Regla de oro del molde:** si cualquier pieza falla (no hay examen suficiente, el control baja, se
acaba el tiempo), la neurona **se apaga sola y queda el piso**. El sistema nunca queda peor que la
fórmula a mano.

---

## 4. El banco de calibración (las agujas)

Antes de que una neurona aprenda, Dennys calibra a mano sus entradas, igual que hizo con el
ranking. El banco es un script que, para cada aguja candidata:

1. **Muestra su distribución** en la copia del snapshot (mínimo, máximo, cuartiles).
2. **La normaliza a 0–1** con una regla simple y fija (sin aprender nada).
3. **Mide cuánto separa lo bueno de lo malo** con las preguntas del autoexamen (por ejemplo: en las
   conexiones que llevan a la respuesta correcta vs. las que no).
4. **Mide su costo** (milisegundos por consulta o por consolidación).
5. **Dennys decide:** entra, no entra, o cambia la regla.

Con las agujas aprobadas, Dennys arma la **fórmula a mano** (el piso). Recién después se enciende la
neurona que aprende.

> El banco **no cambia nada del motor**: lee una copia y escribe un informe. Así se puede correr
> todas las veces que haga falta sin riesgo.

---

## 5. Mapa del motor y de la base de datos

### 5.1 La base de datos (copia del snapshot)

| Tabla | Filas | Para qué sirve |
|---|---:|---|
| `largo_plazo` | 866 | Los recuerdos (851 activos). |
| `sinapsis` | 13,920 | Conexiones directas entre recuerdos. |
| `sinapsis_latentes` | 8,893 | Conexiones "de dos pasos" calculadas (A–B–C ⇒ A~C). |
| `sinapsis_cuarentena` | 6,870 | Conexiones que la hormiguita sacó (reversibles). |
| `largo_plazo_dimensiones` | 5,535 | Dimensiones semánticas por recuerdo. |
| `nodo_grupos_semanticos` | 101,028 | Pertenencia a 45 grupos semánticos. |
| `tokens` | 8,083 | Vocabulario. |
| `log_busquedas` | 4,243 | Búsquedas recientes (7 días). |
| `nodo_accesos_historial` | 8,262 | Accesos a recuerdos. |
| `metricas_cognitivas_nodos` | 14,526 | Métricas por recuerdo. |

**Tipos de sinapsis** (quién las crea y con qué peso promedio):

| Tipo | Cantidad | Peso prom. | Quién la crea |
|---|---:|---:|---|
| `sinonimo_explicito` | 5,863 | .88 | El usuario declara sinónimos → se unen recuerdos que los comparten (`sinapsis.vincular_por_sinonimos`). |
| `pmi_hebbiano` | 2,359 | .50 | Palabras que aparecen juntas en el corpus (NPMI ≥ .35) → recuerdos con esas palabras (`sinapsis.py` L318–356). |
| `co_ocurrencia` | 2,108 | .67 | Contenido parecido (Jaccard ≥ .4 con cierre triádico, `auto_vincular`) y recuerdos usados en la misma sesión (`consolidation.py` L102/L159). |
| `co_nombre` | 1,558 | .42 | Recuerdos cuyo **nombre** comparte palabras (`sinapsis.py` L196–230). |
| `co_semantica` | 1,226 | .57 | Recuerdos con sinónimos en común (`sinapsis.py` L255–290). |
| `manual` | 575 | .50 | El usuario/agente las une con `vincular`. |
| `latente_confirmada` | 120 | .40 | Latentes que se confirmaron. |
| `dmn_synthesized` | 72 | .30 | Las sintetiza el DMN (`dmn_engine.py`). |
| `legacy_csv`, `manual_v7`, `test` | 39 | — | Históricas. |

Además: la **ráfaga** crea `rafaga_rememb` (peso .6) cuando una búsqueda acierta por una palabra
que también es un recuerdo (`rafaga.py` L349). Y cada consolidación **debilita** ×0.95 las
sinapsis sin uso por 7+ días y **borra** las que caen bajo .05 (`consolidation.py` L432–451). O sea:
el motor ya tiene un "olvido" mecánico de conexiones; la hormiguita es una segunda poda, encima.

### 5.2 Para qué se usan las sinapsis (por qué cortarlas tiene efectos lejanos)

Las sinapsis no solo sirven para "saltar" de un recuerdo a otro. **Alimentan varias piezas del
motor**, y por eso cortar una puede bajar el recall en lugares inesperados:

| Pieza | Cómo usa las sinapsis |
|---|---|
| **Vectores PPMI** (`ppmi_vectorizer.py` L161) | Se construyen **con** las sinapsis `sinonimo_explicito`, `pmi_hebbiano`, `co_semantica`, `manual`. Cortar sinapsis **cambia los vectores** de búsqueda. |
| **Búsqueda híbrida PPMI** (`ppmi_hybrid_search.py` L29) | Salta por esos 4 tipos (`TIPOS_HOP`). |
| **Similitud latente** (search.py, Fallback 1.8) | Compara vecinos de grafo. |
| **Evocación en cadena** (1.9) y **spreading activation** (2.2, precálculo L1563) | Recorren el grafo. |
| **SDM** (2.5) | Su índice se recalcula con los vecinos ("dirty" al crear sinapsis). |
| **Contexto para el agente** (MCP, BFS en `mcp_server/search.py` L684) | Muestra vecinos. |
| **Sinapsis latentes y DMN** | Se calculan a partir de las directas. |
| **Auto-clustering** (`auto_clustering.py`) | Agrupa por sinapsis con peso ≥ .1. |

> Esto explica una parte de por qué la hormiguita tuvo que devolver tantas: no es solo "un camino
> menos", es **un vector distinto** para muchas búsquedas.

### 5.3 Cómo busca el motor (capas de `core/memory/search.py`)

`buscar_por_frase` (L40) junta candidatos en capas, y al final el **ranking** (que no se toca) los
ordena:

| Capa | Línea | Qué hace |
|---|---:|---|
| 2 LIKE | 437 | Coincidencia directa de palabras. |
| 1.0 FTS AND | 513 | Búsqueda de texto completo. |
| Términos protegidos | 546 | Palabras que no se pueden perder. |
| 1.4 Prefijo | 599 | Palabras cortadas. |
| 1.7 Trigramas | 628 | Errores de tipeo. |
| 1.8 Latente | 687 | Parecido por vecinos. |
| 2.0 Substring | 790 | Partes de palabra. |
| Recientes | 815 | Lo último que se guardó. |
| 1.9 Cadena | 834 | Evocación por el grafo. |
| 2.1 Simbólica | 897 | Predicados. |
| 2.2 Spreading | 946 | Activación que se propaga. |
| 2.5 SDM | 972 | Memoria distribuida. |
| Merge | 1008 | Se juntan. |
| 4 Sinónimos | 1024 | Expansión por sinónimos. |
| Dimensional | 1263 | Por dimensiones. |
| 5 Grupos | 1415 | Por grupos semánticos. |

Umbrales que dependen de la **escala** de los scores (por eso el ranking no se toca): abstención
.6212, GABA .80, ráfaga < .5, certeza .60/.35, léxico .88, dashboard .55. El camino del MCP da
scores más "planos" que el camino de la QA, y redondea a 4 decimales.

---

## 6. Mediciones de esta etapa (A, B, C, D)

Todas sobre una copia del snapshot, con `BIORAG_NEURONA=0` (motor crudo), top-10.
Scripts y resultados en [`resultados/`](resultados/).

### A — ¿Cuánta basura trae la lista? (QA oficial, 816 casos)

La respuesta está en el puesto 1 en **737**, en el top-5 en **806** y en el top-10 en **812**. La
lista trae en promedio **8.32** resultados.

¿Y si se recorta la lista a "los que tienen al menos ρ × el score del primero"?

| ρ | Resultados promedio | Respuestas del top-5 perdidas (de 816) |
|---:|---:|---:|
| 0.5 | 3.14 | 0 |
| 0.6 | 2.93 | 0 |
| 0.7 | 2.60 | 2 |
| 0.8 | 1.95 | 7 |
| 0.9 | 1.32 | 24 |

### B — ¿Dónde están las respuestas que no llegan? (autoexamen, 300 recuerdos, semilla 7)

**2,060** preguntas. La respuesta está en el top-10 en **1,931 (93.7 %)**. Faltan **129**:

| De las 129 que faltan | Cantidad | % |
|---|---:|---:|
| A 1 salto de grafo de algún resultado | 53 | 41.1 |
| A 2 saltos | 64 | 49.6 |
| No alcanzable en 2 saltos | 12 | 9.3 |

Pero el costo: un salto desde el top-10 trae una **mediana de 215 candidatos** (2 saltos: **578**)
de 851. Con ~33 conexiones por recuerdo, **un salto ciego es buscar una aguja en un pajar**.

Por categoría de pregunta (faltan / a 1 salto / a 2 saltos): contenido 46/21/19 · sinónimo 22/16/6 ·
variante 31/7/21 · por_tema 19/5/12 · typo 10/3/6 · cruce 1/1/0 · pnat 0.

### C — ¿Sirve un recorte fijo en el camino del MCP?

En el camino MCP los scores son más planos. Con ρ = 0.6: en la QA no literal quedan 5.69 resultados
y **0** perdidos del top-5; pero en el autoexamen se pierden **5 (0.5 %)**, y con ρ = 0.8, **36**.
**Conclusión:** un recorte fijo no es seguro; si alguna vez se recorta, lo tiene que decidir una
neurona con examen, no una constante.

### D — ¿Las conexiones que cortó la hormiguita llevaban a respuestas correctas?

Mismas 2,060 preguntas del autoexamen que en B (300 recuerdos, semilla 7). Para cada pregunta se
miran los resultados del top-10 (sin contar la respuesta) y **todas sus conexiones**. Una conexión
es **"útil"** en esa pregunta si une un resultado con la **respuesta correcta**. Se cuenta cuántas
veces pasa, por cada 1,000 conexiones miradas.

**Referencia del azar:** si una conexión apuntara a un recuerdo cualquiera, acertaría ~**1.2 por
mil** (1 de 850).

| Grupo de conexiones | Miradas | Útiles | Útiles por mil | vs. azar |
|---|---:|---:|---:|---:|
| `manual` (activas) | 9,290 | 123 | **13.24** | ×11 |
| `co_semantica` (activas) | 22,037 | 183 | **8.30** | ×7 |
| `co_nombre` (activas) | 46,865 | 297 | 6.34 | ×5 |
| `dmn_synthesized` (activas) | 2,023 | 12 | 5.93 | ×5 |
| `sinonimo_explicito` (activas) | 210,628 | 780 | 3.70 | ×3 |
| **Todas las activas** | 620,031 | 2,144 | **3.46** | ×3 |
| `co_ocurrencia` (activas) | 251,170 | 617 | 2.46 | ×2 |
| `pmi_hebbiano` (activas) | 70,299 | 124 | 1.76 | ×1.5 |
| `latente_confirmada` (activas) | 6,006 | 6 | 1.00 | ≈ azar |
| **En cuarentena (siguen afuera)** | 120,130 | 192 | **1.60** | ×1.3 |
| · directas | 82,770 | 150 | 1.81 | |
| · latentes | 37,360 | 42 | 1.12 | |
| **Devueltas y hoy no activas** | 40,101 | 36 | 0.90 | ≈ azar |

(`legacy_csv`, `manual_v7` y `test` tienen muy pocas miradas para concluir.)

**Lectura simple:**

1. **La utilidad se puede medir sin IA externa, y separa muy bien.** Una conexión `manual` lleva a
   la respuesta 7 veces más seguido que una `pmi_hebbiano`. Esa es la señal que necesita la neurona
   de sinapsis.
2. **En promedio, la hormiguita no cortó a ciegas:** lo que está en cuarentena es la mitad de útil
   que lo activo (1.60 vs. 3.46), parecido a las `pmi_hebbiano` activas.
3. **Pero no era basura:** esas conexiones cortadas habrían unido un resultado con la respuesta
   correcta **192 veces** en estas 2,060 preguntas. Por eso cortar "por significado" daña: la
   media está bien, pero cada corte individual es una apuesta.
4. **El pajar es real:** incluso las activas aciertan ~3.5 de cada 1,000. Casi todas las
   conexiones, en una pregunta dada, no llevan a la respuesta. Por eso un salto necesita un juez
   (sección 6B) y por eso la neurona de sinapsis tiene que juzgar con **muchas** preguntas, no con
   una.

**Límites de esta medición (honestidad):**
- "Útil" cuenta también cuando la respuesta **ya estaba** en el top-10 (la conexión es un camino
  más, no siempre un rescate).
- Si un par está a la vez en `sinapsis` y en la cuarentena, se cuenta como **activo**. Por eso
  "devueltas y hoy no activas" son solo las que volvieron y después se perdieron por otro motivo.
- Es una sola copia del snapshot y una sola semilla (7). Sirve para decidir el diseño, no como
  número final.

---

## 7. Dónde poner neuronas (candidatos)

| # | Neurona | Qué decide | Piso a mano posible | De dónde aprende | Riesgo |
|---|---|---|---|---|---|
| **1** | **Sinapsis** (elegida) | Mantener / reforzar / atenuar / cuarentena de cada conexión | Las reglas que la hormiguita ya tiene escritas (`_pre_filtrar_conexiones`) + utilidad medida | Autoexamen: ¿la conexión lleva a la respuesta o trae ruido? | Medio: toca el grafo → **cuarentena + examen + protegidas** |
| 2 | Saltos | Qué vecinos de grafo vale la pena traer como candidatos extra | Peso de la sinapsis × tipo × posición de la semilla | Autoexamen (las 117 respuestas a 1–2 saltos) | Alto si va sola (pajar). Va **después** de la de sinapsis. |
| 3 | Largo de lista | Cuántos resultados devolver | ρ relativo (medición A) | Autoexamen | Medio en MCP (medición C) |
| 4 | Capas | Qué capas del motor vale la pena correr para cada consulta (ahorro de tiempo) | Tabla a mano por tipo de consulta | Qué capa trajo la respuesta en el autoexamen | Bajo si solo **ordena**, alto si **apaga** capas |
| 5 | Sinónimos/dimensiones | Proponer sinónimos o dimensiones faltantes (lo otro que hace la hormiguita) | PMI + co-ocurrencia | Autoexamen (categoría sinónimo) | Medio |

**Por qué empezar por la sinapsis:** (1) quita la única dependencia externa (Gemini); (2) arregla
el pajar de la sección 6B, que es lo que hoy impide la neurona de saltos; (3) tiene un "maestro"
gratis: las 6,870 decisiones de la hormiguita con 2,681 errores ya marcados por el examen.

---

## 8. Lo que enseña la historia de BioRAG

Cosas que ya se probaron y fallaron. No repetir.

| Qué se probó | Qué pasó | Lección para las neuronas del motor |
|---|---|---|
| Umbral **absoluto** de score por ítem (`de9e062`) | R@5 96 → 73.4; se perdían 194 buenos para sacar 6 malos | Nada de cortes absolutos. |
| PPR (PageRank personalizado) | 0 % de ganancia, +100–190 ms | El grafo "a lo bruto" no ayuda. |
| Expansión de grafo a 1 salto con peso global | `por_tema` 13 → 1 de 21 | Un salto sin juez trae ruido. |
| Recorte relativo fijo en MCP | Pierde respuestas (medición C) | Recortes, solo con examen. |
| Campeón transferido de otra DB (Exp 08) | Perjudicó | La pre-entrenada solo como retadora. |
| Abstención E13, arranque en frío .65 | Descartados | — |
| Hormiguita: poda por "significado" | 39 % devuelto por el examen | El significado no basta; manda la utilidad. |

---

## 9. Primer candidato: la neurona de sinapsis

### 9.1 Qué hace hoy la hormiguita (`core/dmn_reflexion.py`, v24.1, 2,132 líneas)

Es un daemon que recorre el grafo nodo por nodo y le pregunta a Gemini qué conexiones sobran.

**1. Elige un nodo** (`_seleccionar_semilla`, L1370), en este orden:
   - **Urgente:** nodos con más de 5 sinapsis `pmi_hebbiano`.
   - **Reciente:** nodos tocados en las últimas 24 h.
   - **Barrido:** el nodo más viejo sin visitar.
   - Después expande la frontera 1 salto (`_expandir_frontera`, L1427).

**2. Arma el paquete para Gemini** (`_construir_payload_nodo`, L385):
   - del nodo: contenido, categoría, peso, valencia, sinónimos, dimensiones, lexnames de WordNet;
   - **todas** sus sinapsis directas (tipo, peso, contenido del destino hasta 3,000 caracteres);
   - sus latentes con el camino reconstruido (A → puente → C);
   - los catálogos completos de dimensiones y categorías;
   - en lotes de 10 sinapsis.

**3. Gemini responde con un veredicto por conexión** (`PROMPT_SISTEMA`, L126–229). Reglas
principales del prompt:
   - eliminar si los contenidos "hablan de cosas distintas" o comparten solo palabras genéricas;
   - **estricto con `pmi_hebbiano`: ante la duda, eliminar**;
   - para lo demás, ante la duda, "ignorar";
   - confianza calibrada .70–1.00;
   - no eliminar la última conexión temática del nodo salvo confianza ≥ .90;
   - además puede proponer dimensiones, sinónimos, categoría, enriquecer contenido o fusionar
     (la fusión va a revisión humana).

**4. Aplica con seguridad** (`_aplicar_veredicto_nodo`, L1060):
   - acepta con confianza ≥ .75, elimina con ≥ .70;
   - **nunca deja un nodo con menos de 5 conexiones**;
   - latentes: "dos strikes" (primero baja el peso ×0.5, a la segunda va a cuarentena; con ≥ .90 va
     directo);
   - lo "eliminado" va a `sinapsis_cuarentena` (`_mover_a_cuarentena`, L845), no se borra;
   - la cuarentena se purga a los **30 días** (`_purgar_cuarentena`, L951). ⚠️ O sea, a los 30 días
     sí se pierde.

**5. Examen de seguridad** (`_benchmark_gate`, L967): cada 25 nodos mide recall@5 con 40 casos de QA.
Si bajó más de 2 puntos, **devuelve todo** lo cortado desde el último examen bueno.

**6. Pre-filtro determinista** (`_pre_filtrar_conexiones`, L253) — **existe pero está apagado**
(`BIORAG_HORMIGA_PRE_FILTRO=0`). Es una fórmula a mano:
   - mantener si peso ≥ .80, si es `sinonimo_explicito`, o si Jaccard de contenidos ≥ .30;
   - cortar si es `pmi_hebbiano` con peso < .20;
   - el resto, a Gemini.

> Por estar apagado, Gemini terminó cortando **1,423 `sinonimo_explicito`**, que el propio
> pre-filtro consideraba "siempre válidas". La mitad volvió (745).

### 9.2 Lo que hizo, en números (la cuarentena de la copia del snapshot)

**Total: 6,870** conexiones en cuarentena.

| Origen | En cuarentena | Devueltas por el examen | % devuelto |
|---|---:|---:|---:|
| Sinapsis directas (daemon) | 3,197 | 2,201 | 40.4 % (de 5,446) |
| Sinapsis directas (a pedido) | 48 | — | |
| Latentes (daemon) | 923 | 480 | 33.7 % (de 1,424) |
| Latentes (a pedido) | 21 | — | |
| **Total** | | **2,681** | **39.0 %** |

**Por tipo de conexión** (cortadas / devueltas):

| Tipo | Cortadas | Devueltas | % devuelto |
|---|---:|---:|---:|
| `pmi_hebbiano` | 1,677 | 483 | 28.8 % |
| latente | 1,424 | 480 | 33.7 % |
| `sinonimo_explicito` | 1,423 | 745 | **52.4 %** |
| `co_ocurrencia` | 1,310 | 647 | **49.4 %** |
| `co_semantica` | 504 | 99 | 19.6 % |
| `co_nombre` | 455 | 190 | 41.8 % |
| `latente_confirmada` | 60 | 30 | 50.0 % |
| `manual` / `manual_v7` / `legacy_csv` | 17 | 7 | — |

**Por confianza de Gemini** (cortadas / devueltas):

| Confianza | Cortadas | Devueltas | % devuelto |
|---:|---:|---:|---:|
| .7 | 948 | 381 | 40.2 % |
| .8 | 1,856 | 745 | 40.1 % |
| .9 | 3,374 | 1,183 | 35.1 % |
| 1.0 | 692 | 372 | **53.8 %** |

**Lectura simple:**
- Gemini se equivocó (según el propio examen) en ~4 de cada 10 cortes.
- **Estar "100 % seguro" no lo hacía acertar más**: con confianza 1.0 se equivocó más que nunca.
- Los tipos que más volvieron son justo los que vienen del usuario (`sinonimo_explicito`) o del uso
  real (`co_ocurrencia`). Los que menos volvieron son `co_semantica` y `pmi_hebbiano`.
- Hoy, **1,911** de las 2,681 devueltas siguen activas en `sinapsis`.

> **Cuidado (honestidad):** el examen devuelve **en bloque** todo lo cortado desde el último examen
> bueno. Entonces "devuelta" significa "estaba en un grupo de cortes que hizo bajar la memoria", no
> que esa conexión, sola, fuera imprescindible. Igual, el patrón es claro: cortar por significado
> daña con frecuencia.

### 9.3 Por qué Gemini se equivoca (y una neurona chica también lo haría si copiara a Gemini)

1. **Mira el significado, no el uso.** Pregunta "¿estos dos textos hablan de lo mismo?". Pero el
   motor no usa la sinapsis para "entender", la usa para **llegar** (saltos, vectores PPMI,
   spreading). Una conexión puede "no tener sentido" y aun así ser el camino a la respuesta.
2. **No ve los efectos lejanos.** No sabe que una sinapsis `sinonimo_explicito` entra a los
   vectores PPMI y cambia cientos de búsquedas (sección 5.2).
3. **El prompt la empuja a cortar** `pmi_hebbiano` ante la duda.
4. **Su confianza no está calibrada** con la realidad del motor (tabla de confianza).
5. **Cuesta dinero y depende de internet y de claves**, y su criterio cambia cuando cambia el modelo.

### 9.4 La duda de Dennys: ¿y si las conexiones "sin relación" son asociaciones legítimas?

**Respuesta: sí, muchas lo son, y la neurona tiene que respetarlas.**

En el cerebro humano, oír "playa" te puede traer el nombre de un amigo, aunque "playa" y "Juan" no
signifiquen lo mismo: fueron juntos a la playa. Esa conexión no es "semántica", es **episódica**, y
es valiosa. En BioRAG pasa igual: `co_ocurrencia` y `pmi_hebbiano` nacen del uso y del corpus, no
del diccionario.

Por eso el criterio de la neurona de sinapsis es otro:

> **No se pregunta "¿tienen relación de significado?". Se pregunta "¿esta conexión ayuda a la
> memoria a encontrar cosas, o la estorba?".**

Y eso se puede **medir** sin IA externa, con el autoexamen que ya existe:

- **Útil:** en una pregunta del autoexamen, la conexión une un resultado traído por el motor con la
  respuesta correcta (por ahí se llega).
- **Ruido:** la conexión sale de los resultados y lleva a recuerdos que nunca son la respuesta,
  una y otra vez.
- **Neutra:** no aparece en ningún examen. **Se deja en paz** (no hay evidencia para tocarla).

Así, una asociación "rara" que sirve **se queda y hasta se refuerza**; solo se atenúan las que la
evidencia muestra que estorban. Eso es **potenciar** el cerebro, no recortarlo.

### 9.5 Diseño de la neurona de sinapsis (propuesta, para conversar)

**Qué decide:** para cada conexión que aparece en el autoexamen: **reforzar**, **dejar**,
**atenuar** (bajar el peso un poco) o, con mucha evidencia, **cuarentena** (reversible).
**Nunca borra.**

**Protegidas (no las toca nunca, salvo que Dennys diga otra cosa):** `manual`, `manual_v7`,
`sinonimo_explicito` (las declaró el usuario/agente), y la conexión que dejaría a un recuerdo con
menos de 5 conexiones.

**Agujas candidatas** (Dennys elige cuáles entran; todas baratas y locales):

| Aguja | Qué mide | Costo |
|---|---|---|
| Utilidad en el autoexamen | Veces que la conexión llevó a la respuesta correcta | Se acumula durante la práctica (ya corre) |
| Ruido en el autoexamen | Veces que trajo recuerdos que no eran la respuesta | Ídem |
| Tipo de sinapsis | De dónde nació (tabla 5.1) | 0 |
| Peso actual | La fuerza que ya tiene | 0 |
| Último uso / edad | Si se usa o está olvidada | 0 |
| Parecido de contenido (Jaccard) | Ya lo calcula el pre-filtro de la hormiguita | Bajo |
| Vecinos en común (cierre triádico) | Ya existe en `sinapsis._vecinos_comunes` | Bajo |
| Dimensiones en común | Ya existe en `sinapsis._dimensiones_comunes` | Bajo |
| Grado de los dos nodos | Nodos "hub" con cientos de conexiones son los que hacen el pajar | Bajo |

**Piso a mano (ejemplo para que Dennys lo ajuste):** las reglas del pre-filtro que la hormiguita ya
tiene escritas (mantener peso ≥ .80 / sinónimo explícito / Jaccard ≥ .30), **más** una regla de
utilidad: *"solo se atenúa una conexión si en el autoexamen trajo ruido muchas veces y nunca llevó a
una respuesta"*. Si no hay evidencia, no se toca.

**Neurona encima:** aprende cuánto pesa cada aguja para predecir "útil vs. ruido", con el mismo
motor de aprendizaje de la v34 (pesos chicos, techo, campeón).

**Examen de seguridad (más estricto que el de la hormiguita):**
1. Toda decisión se prueba en las preguntas de **control** antes de aplicarse: si alguna pregunta de
   control que antes acertaba deja de acertar, la decisión se revierte.
2. Cambios **chicos** por ciclo (pocas conexiones por consolidación) → costo fijo y fácil de
   revertir.
3. La QA de Dennys como piso antes de cualquier PR.
4. La cuarentena de la neurona **no se purga sola** (a diferencia de los 30 días de la hormiguita),
   salvo que Dennys lo decida.

**Maestros gratis:**
- Las **6,870** decisiones de la hormiguita: 2,681 marcadas como error por el examen → ejemplos de
  "esto NO se corta".
- El autoexamen (ya existe, ya corre en cada consolidación).

### 9.6 Cómo se retira la hormiguita (sin saltos al vacío)

| Etapa | Qué pasa | Cuándo se pasa a la siguiente |
|---|---|---|
| **1. Aprendiz** | La hormiguita sigue igual. La neurona solo **mira** y anota qué habría hecho. No cambia nada. | Cuando su acuerdo con los cortes que **sobrevivieron** al examen es alto, y casi nunca coincide con los que fueron devueltos. |
| **2. Relevo** | La neurona decide; la hormiguita queda apagada pero instalada, por si hay que volver. | Cuando la QA de Dennys queda igual o mejor por varias versiones. |
| **3. Retiro** | Se quita la dependencia de Gemini del camino normal. El código de la hormiguita queda como herramienta opcional. | Decisión de Dennys. |

---

## 10. Ideas grandes para después (sistema vivo)

Estas ideas no se implementan ahora. Quedan escritas para no perderlas.

1. **Una práctica alimenta a todas.** El autoexamen ya corre en cada consolidación; todas las
   neuronas del motor pueden aprender de las **mismas** preguntas (costo casi cero por neurona extra).
2. **Retadora de fábrica.** El producto puede traer una neurona entrenada en el corpus de Dennys,
   pero entra como **retadora**: solo trabaja si gana el examen local. Si no, manda el piso.
3. **Mielina.** Las conexiones que muchas veces llevan a la respuesta se "mielinizan": se recorren
   primero y más barato.
4. **Neurogénesis controlada.** Cuando una neurona ve que un tipo de consulta le va mal siempre,
   puede nacer una "neurona hija" especializada (por ejemplo, solo para typos). Nace como retadora,
   con su propio piso, y muere si no gana su examen.
5. **Paginación de costo fijo** para millones de recuerdos: cada neurona mira siempre K cosas por
   ciclo (por ejemplo, 50 conexiones), no importa el tamaño de la DB.
6. **El circuito saltos + sinapsis:** cuando el grafo esté limpio por utilidad, la neurona de saltos
   puede traer las respuestas que están a 1–2 saltos (sección 6B) sin traer el pajar.

---

## 11. Correcciones de honestidad

Cosas que se dijeron (por mí, por otras IAs o como idea) y que hay que corregir para no exagerar:

1. **"Una neurona pre-entrenada sirve para cualquier corpus."** No está demostrado, y el Exp 08
   mostró lo contrario para el campeón del ranking. El motor es el mismo, pero los datos no.
   → Solo como retadora.
2. **"Una neurona chica puede leer el significado como Gemini."** No. No entiende textos. Juzga por
   **evidencia de uso**. Y eso es justamente lo que conviene (sección 9.4).
3. **"Filtrar en SQL con WHERE/UDF es gratis y saca el ruido."** No: recorrer todas las filas cuesta,
   y no saca todo el ruido.
4. **"Recortar la lista con un umbral fijo es seguro."** No en el camino MCP (medición C).
5. **"Un salto de grafo trae lo que falta."** Sí lo trae, pero junto con ~215 candidatos más
   (medición B). Sin juez, empeora.
6. **"La hormiguita mejora el grafo."** A veces; pero 39 % de sus cortes volvieron por dañar la
   memoria (sección 9.2), con la salvedad de que la devolución es en bloque.
7. **Sobre la v34.1:** en el snapshot la QA queda **igual**; la ganancia es para DBs nuevas.
8. **Nunca decir "R@5 100 % en ambos caminos"**: el MCP queda en 99.66.

---

## 12. Orden de trabajo

| Paso | Qué | Entrega | Riesgo para el motor |
|---|---|---|---|
| 0 | Este documento | Base escrita | Ninguno |
| 1 | **Banco de calibración** de las agujas de sinapsis (solo lectura, copia) | Informe por aguja; Dennys elige | Ninguno |
| 2 | **Piso a mano** de la neurona de sinapsis, en modo **aprendiz** (solo anota) | Tabla de acuerdo vs. hormiguita y vs. examen | Ninguno (no cambia el grafo) |
| 3 | Neurona que aprende encima, todavía en modo aprendiz | Curva de aprendizaje, control | Ninguno |
| 4 | Modo **relevo** en la copia del snapshot: aplica cambios con examen | QA de Dennys antes/después, diff, salida textual | Medio, solo en copia |
| 5 | PR para que Dennys audite | PR (Dennys hace el merge) | — |
| 6 | Neurona de saltos (aprovechando el grafo limpio) | Nuevo experimento | — |
| 7 | Retiro de la hormiguita | Decisión de Dennys | — |

Cada paso: **primero se conversa**, después se mide.

---

## 13. Preguntas abiertas para Dennys

1. ¿Qué **agujas** entran en el banco de la neurona de sinapsis? (tabla de 9.5)
2. ¿Las **protegidas** son `manual` + `sinonimo_explicito`? ¿Alguna más (`co_ocurrencia` de sesión)?
3. ¿La neurona puede **reforzar** (subir peso) además de atenuar, o solo atenuar al principio?
4. ¿La cuarentena de la neurona debe tener vencimiento, o se queda para siempre?
5. Mientras tanto, ¿la hormiguita sigue corriendo en tu DB viva, o la pausamos durante el
   aprendizaje?
6. ¿Prender el pre-filtro determinista de la hormiguita (ya existe, apagado) como primer piso
   mientras tanto? Evitaría que Gemini vuelva a cortar `sinonimo_explicito`.
7. ¿Qué **nombre** lleva: Neurona Asociativa, de Salud Sináptica o de Plasticidad del Grafo?
8. ¿Puedes correr en tu DB viva (solo lectura) el conteo de cobertura de `sustantivos_clave` y
   `predicados`? (Te paso el comando.)
9. Para las agujas estructurales que faltan: ¿**cambiar** un parámetro del MCP que no aporte, o
   **volver obligatorio** `predicados`? (La norma dice "sin trabajo extra para el agente".)
10. ¿Se crea una tabla aparte de **sinapsis candidatas** (zona de crecimiento), o se usa un campo de
    estado en `sinapsis`?
11. ¿Las nuevas ideas (neurona de consolidación, de contradicción, de abstención) entran a la lista
    de candidatos?

---

## 14. Cómo reproducir las mediciones

Requisitos: el venv del proyecto y una **copia** del snapshot (nunca la DB viva).

```bash
mkdir -p /tmp/q/m
cp <ruta_snapshot>/biorag.db /tmp/q/m/b.db       # COPIA, nunca la DB real
cd "<repo>/docs/Mi neurona en el sistema/experimento_10_neuronas_del_motor/resultados"
python medir.py      # A y B  →  A.json, B.json   (~30 min)
python medir_c.py    # C      →  C.json           (~15 min)
python medir_d.py    # D      →  D.json           (~30 min)
```

Los scripts usan la ruta fija `/tmp/q/m/b.db` y el repo en `/home/user/MemoryBioRAG`; cambiar esas
dos líneas si se corre en otra máquina. Todos apagan la neurona (`BIORAG_NEURONA=0`) para medir el
motor crudo. **No modifican el motor.**

> **Salvedad (honestidad):** buscar no es 100 % solo lectura: el motor escribe su log de búsquedas,
> accesos y, a veces, la ráfaga crea una conexión `rafaga_rememb`. Estas mediciones corrieron una
> detrás de otra sobre la **misma** copia (A → B → C → D). El efecto es mínimo, pero para una
> auditoría estricta conviene usar una copia fresca por script.

Conteo de cobertura de agujas (sección 15.3). Es **solo lectura**; Dennys lo puede correr en su DB
viva sin riesgo (abre la base en modo `ro`):

```bash
python3 - <<'PY'
import sqlite3
c = sqlite3.connect("file:RUTA/A/biorag.db?mode=ro", uri=True)   # mode=ro: no escribe nada
q = lambda s: c.execute(s).fetchone()[0]
A = "estado='activo'"
print("activos          ", q(f"SELECT COUNT(*) FROM largo_plazo WHERE {A}"))
print("sustantivos_clave", q(f"SELECT COUNT(*) FROM largo_plazo WHERE {A} AND COALESCE(sustantivos_clave,'') NOT IN ('','[]')"))
print("predicados       ", q(f"SELECT COUNT(DISTINCT p.concepto) FROM predicados p JOIN largo_plazo l ON l.concepto=p.concepto WHERE l.{A}"))
print("dimensiones      ", q(f"SELECT COUNT(DISTINCT d.concepto) FROM largo_plazo_dimensiones d JOIN largo_plazo l ON l.concepto=d.concepto WHERE l.{A}"))
print("sinonimos        ", q(f"SELECT COUNT(*) FROM largo_plazo WHERE {A} AND COALESCE(sinonimos,'')<>''"))
print("valencia         ", q(f"SELECT COUNT(*) FROM largo_plazo WHERE {A} AND COALESCE(valencia_somatica,0)<>0"))
PY
```

Consultas usadas para la sección 9.2 (sobre la copia, solo lectura):

```sql
SELECT tipo, COUNT(*), SUM(restaurado), ROUND(AVG(confianza),2)
  FROM sinapsis_cuarentena GROUP BY tipo ORDER BY 2 DESC;
SELECT ROUND(confianza,1), COUNT(*), SUM(restaurado)
  FROM sinapsis_cuarentena GROUP BY 1;
SELECT COUNT(*) FROM sinapsis_cuarentena q
 WHERE restaurado = 1
   AND EXISTS (SELECT 1 FROM sinapsis s WHERE s.origen = q.origen AND s.destino = q.destino);
```

---

## 15. La neurona asociativa (aporte de la conversación con Manus)

> Fuente: conversación de Dennys con Manus AI, 2026-10-24, guardada **completa** en
> [`anexo_A_conversacion_dennys_manus.md`](anexo_A_conversacion_dennys_manus.md).
> Dennys la trajo como información de primera mano. Aquí va el análisis científico: qué se adopta,
> qué ya existe en BioRAG (medido en la copia del snapshot), qué falta y qué hay que ajustar a las
> normas del proyecto.

### 15.1 La idea en una frase

> **Que las sinapsis se formen y se mantengan como en un cerebro: por varias características
> compartidas a la vez y por experiencia, no por una palabra suelta ni por reglas mecánicas.**

Con esto la neurona de sinapsis de la sección 9 crece y pasa a tener **dos mitades**:

| Mitad | Qué decide | Equivale a |
|---|---|---|
| **Salud sináptica** | ¿Esta conexión que ya existe ayuda o estorba? → reforzar / dejar / atenuar / cuarentena | Poda sináptica (lo que hoy hace la hormiguita con Gemini) |
| **Asociación** | ¿Estos dos recuerdos deberían conectarse? → proponer / probar / consolidar / rechazar | Plasticidad hebbiana (lo que hoy hacen reglas fijas: `co_nombre`, `pmi_hebbiano`, etc.) |

Nombres propuestos por Manus: **Neurona de Salud Sináptica**, **Neurona de Plasticidad del Grafo**,
**Neurona Asociativa**. El nombre lo elige Dennys.

### 15.2 La intuición clave de Dennys (y por qué los datos le dan la razón)

Dennys: *"Una neurona humana no conecta por una palabra, ni dos, ni tres, sino por ciertas
características únicas que dicen 'esto tiene que ver con esto'. Si mi motor no ofrece esas
características, estamos jodidos. Entonces agarro el MCP, quito un parámetro que no sirve o meto
otro, pongo en cada fila los datos que hacen falta, y encima mis pesos en duro y la neurona."*

Manus lo confirmó con la frase que resume todo: **"una neurona solo puede aprender sobre las agujas
que recibe; si las agujas son pobres, solo aprenderá ruido con apariencia de inteligencia."**

Los datos del motor lo confirman:

- Hoy casi todas las sinapsis nacen de **coincidencia de palabras** (`co_nombre`: palabras del
  nombre; `co_ocurrencia`: Jaccard de contenido; `pmi_hebbiano`: palabras que salen juntas en el
  corpus; `co_semantica`: sinónimos compartidos). Son reglas mecánicas con un umbral fijo.
- En la medición D, las conexiones `pmi_hebbiano` llevan a la respuesta apenas **1.5 veces más que
  el azar**, y `latente_confirmada` **igual que el azar**. Las que puso una persona (`manual`),
  **11 veces más**. O sea: **cuando la conexión la decide alguien que entiende, sirve mucho más**.
  Eso es lo que la neurona asociativa tiene que aprender a imitar con evidencia local.

### 15.3 Inventario: ¿qué características ya le da el motor a una neurona asociativa?

Se tomó la lista de características que propuso Manus, `X(A, B)`, y se buscó cada una en el código y
en la copia del snapshot (851 recuerdos activos; solo conteos, solo lectura).

| Característica (Manus) | ¿Existe en BioRAG? | Dónde | ¿Cuántos recuerdos la tienen? |
|---|---|---|---|
| Similitud de contenido | **Sí** | Jaccard con IDF (`sinapsis._peso_similitud`), FTS5 | 851 / 851 |
| Similitud PPMI | **Sí** | Vectores PPMI (`ppmi_vectorizer.py`) | todos |
| Sinónimos compartidos | **Sí** | `largo_plazo.sinonimos` | 821 / 851 (96 %) |
| Dimensiones en común | **Sí** | `largo_plazo_dimensiones` (`_dimensiones_comunes`) | 762 / 851 (90 %) |
| Vecinos en común (cierre triádico) | **Sí** | `sinapsis._vecinos_comunes` | todos los conectados |
| Misma categoría | **Sí** | `largo_plazo.categoria` (11 categorías) | 851 / 851 |
| Grado de A y de B (sobreconexión) | **Sí**, se calcula | `sinapsis` | todos |
| Distancia en el grafo | **Sí**, se calcula | `sinapsis` / `sinapsis_latentes.saltos` | todos |
| Peso actual, tipo, último uso | **Sí** | `sinapsis.peso/tipo/ultimo_uso` | último uso: 3,457 / 13,920 sinapsis (25 %) |
| Reciprocidad | **Se puede calcular** | `sinapsis` guarda origen→destino; mirar si existe la vuelta | todos |
| Proximidad temporal / mismo episodio | **Parcial** | `creado_en`; `episodes._expandir_episodio_temporal` (ventana de horas). No hay "id de episodio". | `creado_en`: 850 / 851 |
| Coactivación (recuperados juntos) | **Parcial** | `log_busquedas.conceptos_top` (top de cada búsqueda, 7 días), `nodo_accesos_historial`, sesión de consolidación | se llena con el uso |
| Frecuencia conjunta | **No guardada** | Se podría contar desde `log_busquedas` | — |
| **Entidades / conceptos núcleo** | **Casi vacía** | `largo_plazo.sustantivos_clave` (se guarda desde v25) | **6 / 851 (0.7 %)** |
| **Relaciones / predicados** (quién hizo qué a qué) | **Escasa** | tabla `predicados` (sujeto, acción, objeto, contexto) | **102 / 851 (12 %)** |
| Valencia (importancia emocional) | Escasa | `largo_plazo.valencia_somatica` | 95 / 851 (11 %) |
| Utilidad / ruido observado | **Medible, no guardada** | Autoexamen (medición D) | — |
| **Contradicción entre A y B** | **No existe** | Solo es una instrucción al agente en el prompt del MCP | — |
| Justificación de la IA externa | Histórica | `sinapsis_cuarentena.motivo` (hormiguita) | 6,870 decisiones |

**Lectura científica:**

1. **Dennys tenía razón:** el motor ya da muchas agujas **de parecido** (contenido, PPMI, sinónimos,
   dimensiones, vecinos), pero las agujas **estructurales** — las que dicen *"esto tiene que ver con
   esto"*: entidades núcleo, relaciones quién-qué-a-qué, episodio, contradicción — están **vacías,
   escasas o no existen**. Con solo agujas de parecido, la neurona aprendería "una versión
   sofisticada de la coincidencia de palabras" (Manus).
2. **Ojo con el snapshot:** `sustantivos_clave` se guarda recién desde la v25 y casi todos los
   recuerdos del snapshot son anteriores; en la DB viva de Dennys la cobertura puede ser mayor.
   Hay que medirlo antes de decidir (Dennys corre el conteo, no se toca su DB desde aquí).
3. Los parámetros **ya existen en el MCP** (`sustantivos_clave` es obligatorio al guardar desde v25;
   `predicados` existe y es opcional). El problema no es que falten, es que **no se llenan siempre**.

### 15.4 ¿Los datos nuevos entran por el MCP o los calcula el motor?

Dennys propuso tocar el MCP (cambiar parámetros, agregar datos por fila). Manus propuso que las
características se calculen dentro del motor y el MCP solo muestre el resultado. **Los dos tienen
razón, en capas distintas:**

| Capa | Qué es | Quién la produce |
|---|---|---|
| **Dato crudo** del recuerdo (sus entidades, su relación quién-qué-a-qué, su episodio) | Lo que **solo el agente sabe** en el momento de guardar | **MCP** (`aprender`) — es la "una sola mente": el agente aporta lo que entiende |
| **Característica del par** A–B (¿comparten entidades?, ¿misma relación?, ¿mismo episodio?) | Una comparación entre dos filas | **Motor** (un módulo tipo `rasgos_de_asociacion(a, b)`) |
| **Decisión** (conectar, reforzar, atenuar) | La neurona | **Motor** |

**Choque con una norma, para decidir Dennys:** la regla dice *"nada de trabajo extra para el
agente"*. Agregar parámetros sería trabajo extra. La salida que el mismo Dennys propuso: **cambiar
un parámetro que no sirve por uno que sí** (trabajo neto cero), o **hacer obligatorio uno que ya
existe** (`predicados`). Antes hay que medir qué parámetros del MCP casi no aportan.

### 15.5 Lo que se adopta de Manus (encaja con el molde)

1. **Pesos duros + corrección aprendida:** `salud_final = salud_base + corrección`. Es exactamente
   el molde de la sección 3. Las fórmulas de ejemplo de Manus (0.25 · contenido + 0.20 · PPMI …) son
   **solo ejemplos**: el piso real sale del banco de calibración y lo firma Dennys.
2. **Dos salidas: fuerza y confianza.** `A ── peso 0.82, confianza 0.91 ── B`. Útil: una conexión
   nueva puede tener fuerza alta pero confianza baja (poca evidencia) y quedarse "en prueba".
3. **Estados progresivos de una conexión:**
   `observada → propuesta → en prueba (cuarentena) → activa débil → consolidada / reforzada`, y hacia
   atrás `activa → debilitada → cuarentena → bloqueada`. Una mala evaluación nunca borra una conexión
   histórica.
4. **Observar en la búsqueda, decidir en la consolidación ("sueño").** Una consulta aislada no
   deforma la memoria. Esto ya es la regla de la v34.1: 1 práctica por consolidación.
5. **Zona de crecimiento separada:** una tabla tipo `sinapsis_candidatas` (con `veces_observada`,
   `veces_util`, `veces_ruido`, `estado`, `confianza`) para que `sinapsis` siga siendo la memoria
   estable. **Es un cambio de esquema → lo decide Dennys.**
6. **La IA externa pasa a ser solo una proponente.** Si la hormiguita queda como herramienta
   opcional, Gemini **propone** y la neurona local **decide** con evidencia de esta DB. Nunca más
   autoridad final.
7. **Aprender también lo negativo:** pares útiles, coincidencias superficiales, contradicciones,
   relaciones posibles pero irrelevantes. **Ya tenemos ejemplos gratis:** las 2,681 que la hormiguita
   cortó y el examen devolvió ("esto no se corta"), y la medición D (útil / ruido por tipo).
8. **El ranking queda intacto.** La neurona asociativa trabaja **antes**: limpia y hace crecer el
   material que usa el motor.

### 15.6 Lo que hay que ajustar a las normas de BioRAG (honestidad científica)

| Lo que se dijo | Ajuste |
|---|---|
| Manus: "eliminar" / "bloqueada o eliminada" | Norma de Dennys: **nunca borrar**. Lo máximo es **cuarentena o bloqueo reversible**. |
| Dennys: "nunca va a haber ruido" | El propio Manus lo corrigió: se puede **reducir mucho**, no eliminar. Y en una pregunta dada, hasta las mejores conexiones (`manual`) llevan a la respuesta 13 de cada 1,000 veces (medición D): siempre habrá conexiones que **en esa pregunta** no sirven. La meta es **menos ruido, medido**, sin perder recall. |
| Manus: aprender de "¿la respuesta fue útil?" en búsquedas reales | Norma: **sin feedback** del agente. Se reemplaza por el **autoexamen** (preguntas con respuesta conocida), que ya corre. `log_busquedas.util` **no** se usa. |
| Manus: "29 entradas → 6 ocultas → 1 decisión" | Es la imagen de referencia que Dennys mostró. La forma exacta de la neurona asociativa se define después del banco, con costo fijo. |
| Fórmulas con pesos de ejemplo | No son un piso. El piso sale del banco. |

### 15.7 El sistema terminado (la visión, tal como la dibujaron Dennys y Manus)

```
CONSULTA
   │
   ▼
Neurona de enrutamiento ── ¿qué rutas/capas activar?           (sección 7, candidato 4)
   │
   ├── FTS5/BM25 ── PPMI ── Grafo sináptico (sano, plástico)
   ▼
Unión de candidatos
   │
   ▼
Neurona de admisión ── ¿qué evidencia sirve? ¿cuántos?          (sección 7, candidato 3)
   │
   ▼
Ranking actual (intacto) ──► Neurona de reranking v34 (intacta)
   │
   ▼
Contexto para el agente (MCP)

En paralelo, durante la consolidación ("sueño"):
autoexamen ──► práctica ──► neurona de ranking · neurona asociativa · neurona de consolidación
                                     │
                                     ▼
                         grafo plástico y corregible
```

**Familia de neuronas** que se nombró (cada una con el molde completo: agujas, piso, corrección,
examen, guardia, techo, memoria propia, huella de compatibilidad, capacidad de retirarse):

| Neurona | Estado en este plan |
|---|---|
| Ranking (v34) | **Existe.** No se toca. |
| Asociativa (salud + asociación) | **Primera en construirse** (sección 9 + esta sección). |
| Saltos / expansión de contexto | Candidato 2. Después de la asociativa. |
| Admisión (largo de lista) | Candidato 3. |
| Enrutamiento (qué capas correr) | Candidato 4. |
| Sinónimos / dimensiones | Candidato 5 (lo otro que hace la hormiguita). |
| Consolidación | Nueva idea: qué pasa de corto a largo plazo. |
| Contradicción | Nueva idea: necesita primero la aguja "contradicción", que hoy no existe. |
| Abstención | Nueva idea (ojo: E13 de abstención fue descartado antes; revisar por qué). |

### 15.8 ¿A qué se parece? (la analogía, para presentar el proyecto)

Manus lo describió así, y encaja con lo que BioRAG ya tiene:

> **"Un hipocampo artificial simbólico, apoyado por un grafo de memoria plástico, con pequeñas
> neuronas aprendidas que controlan recuperación, asociación, consolidación y poda."**
>
> Técnicamente: **"un sistema neurosimbólico de memoria asociativa con plasticidad local y grafo
> persistente."**
>
> En simple: **"una memoria artificial que no solo guarda recuerdos, sino que aprende qué recuerdos
> se relacionan, qué caminos sirven para encontrarlos y qué conexiones deben desaparecer."**

| Función del cerebro | Qué hace | Pieza de BioRAG que **ya existe** | Lo que agrega la neurona asociativa |
|---|---|---|---|
| Hipocampo: completar un recuerdo desde una pista parcial | Recuperar "aquello del servidor que fallaba" | Capas de búsqueda, trigramas, sinónimos, **SDM** (memoria distribuida dispersa) | — |
| Memoria asociativa / ensambles | Un recuerdo trae a otro | Sinapsis, **spreading activation**, evocación en cadena | Que las conexiones sean **aprendidas** |
| Plasticidad hebbiana | Lo que se activa junto se conecta | `pmi_hebbiano`, `co_ocurrencia` de sesión, `rafaga_rememb` (reglas fijas) | Decidir **con evidencia** si conectar |
| Poda sináptica | Lo que no sirve se debilita | LTD de sinapsis (×0.95, borra < .05), hormiguita | Podar por **utilidad**, no por significado |
| Consolidación en el sueño | De provisional a estable | Corto → largo plazo, `sueno`, DMN | La práctica de todas las neuronas |
| Inhibición | Frenar el ruido | GABA, umbrales | Atenuar conexiones ruidosas |
| Olvido | Dormir lo que no se usa | LTD de nodos, estado dormido | — |

Límite honesto (lo dijo Manus y se mantiene): **el parecido es funcional, no físico**. *"Como un
avión: no tiene plumas, pero reproduce el principio del vuelo de otra manera."*

### 15.9 La visión de Dennys (registrada tal cual)

> *"Esto es como un cerebro, por lo menos la parte del cerebro que guarda información. Como si
> agarraras la mecánica del cerebro humano y la tuvieras ahí usando el mismo motor, la velocidad del
> motor, siendo modular y colocando donde tienen que ir las piezas clave. […] Las RAM embebidas serán
> para consultar documentos estáticos; para una memoria y un cerebro —guardar y recuperar
> información— lo voy a lograr. Y creo que somos los primeros. […] Puede llegar a ser un estándar
> para las memorias. […] Quién sabe si mañana le metemos un chip más que guarde información así,
> documentos completos tipo modular."* — Dennys

Lo que Manus agregó como dirección técnica para que sea un **estándar de memoria para máquinas**
(agentes personales, robots, embebidos, industria, asistentes offline, memorias de empresa):

- **Formalizar:** el formato de memoria, la interfaz de las neuronas, las características de las
  sinapsis, el proceso de consolidación, la protección contra ruido, la persistencia y la
  interoperabilidad entre módulos.
- **Memoria estática** (manuales, documentos fijos) **+ memoria dinámica** (experiencias,
  preferencias, eventos) en el mismo motor.
- **Documentos guardados de forma modular:** identidad, conceptos, episodios, relaciones,
  fragmentos, vectores, metadatos, historial de utilidad; poder recuperar el documento entero, un
  módulo, el concepto, el episodio, los recuerdos conectados **y por qué se recuperó**.
- *"Almacenamiento: guarda y devuelve. Memoria: guarda, relaciona, recuerda, refuerza, distingue,
  recupera y olvida."*

Nota de la científica del proyecto: el **formato de memoria** y la **interfaz de las neuronas** ya
están empezando a existir en este experimento (el molde de la sección 3 es, en la práctica, la
primera versión de esa interfaz). Cada neurona nueva que siga el molde suma a ese estándar.

### 15.10 Cómo cambia el orden de trabajo

El paso 1 de la sección 12 (banco de calibración) se amplía:

1. **Inventario de agujas** (hecho en 15.3 sobre el snapshot) → falta que **Dennys** corra el mismo
   conteo en su DB viva (solo lectura) para ver la cobertura real de `sustantivos_clave` y
   `predicados`.
2. **Banco de agujas del par A–B:** medir cuánto separa cada característica las conexiones útiles de
   las de ruido (con los datos de la medición D como etiqueta).
3. **Propuesta de cambio en el MCP** (si el banco muestra que faltan agujas estructurales): cambiar
   un parámetro que no aporta por uno que sí, o volver obligatorio uno existente. **Dennys lo habla
   con su agente y decide.**
4. Recién después: piso a mano → modo aprendiz → neurona encima → relevo (sección 12, pasos 2–7).

---

## 16. Lo que queda claro: la neurona asociativa en una página

> Después de la segunda parte de la conversación con Manus ([Anexo B](anexo_B_conversacion_dennys_manus_2.md)),
> Dennys cerró esa vía y pidió aclarar todo entre él y su agente, **claro, preciso y conciso**.
> Esta sección es la versión limpia: lo que se queda, lo que se descarta y por qué.

### 16.1 La neurona, en una frase

> **Una sola neurona, dentro del motor, que mira dos recuerdos (A y B) a través de sus agujas y
> decide: conectar, reforzar, dejar, debilitar o mandar a cuarentena. Reemplaza para siempre a la
> hormiguita. El agente y el MCP quedan igual (salvo algún parámetro que la neurona necesite).**

### 16.2 Los 4 enchufes (no hay que inventar momentos nuevos)

El motor **ya tiene** los lugares donde nacen y se revisan las sinapsis. La neurona se enchufa en
ellos, reemplazando las reglas fijas ("si se parecen ≥ 0.4, conectar"):

| Momento | Qué pasa hoy | Qué hace la neurona | ¿Escribe en el grafo? |
|---|---|---|---|
| **1. Al guardar** (consolidar a largo plazo) | `auto_vincular` y compañía conectan por reglas fijas (Jaccard, nombre, PMI, sinónimos) | El motor trae pocos candidatos (como ya hace); la neurona decide cuáles se conectan y con qué fuerza | Sí, pero **como propuesta** (peso bajo) |
| **2. Al buscar** | Ráfaga y spreading recorren el grafo | Solo usa la decisión ya tomada: no expande por conexiones que la neurona marcó como ruido | **No** (buscar no cambia la memoria) |
| **3. En el sueño / consolidación** | LTD baja ×0.95 las conexiones sin uso | Con la evidencia del autoexamen, refuerza o debilita propuestas y conexiones viejas | Sí, pocas por ciclo (costo fijo) |
| **4. Saneamiento** (lo que hacía la hormiguita) | Gemini decide "padre-hijo, ¿sí o no?" | La neurona revisa padre + hijos, por lotes, en el sueño | Sí: debilitar o **cuarentena**, nunca borrar |

**La misma neurona en los 4:** lo que no merece estar conectado tampoco se expande en una búsqueda
(idea de Manus que se queda: coherencia entre guardar y recuperar).

### 16.3 La neurona "de fábrica" y los pesos en duro (cómo encaja con el molde)

Dennys: *"puede venir preentrenada, pero sí, tiene que tener sus pesos en duro"*. Se ordena así:

```
1. Piso a mano (Dennys)        ← reglas que ya existen + las que Dennys calibre en el banco
2. Pesos de fábrica            ← entrenados en el corpus de Dennys, SOLO con agujas universales
3. Ajuste local con techo      ← cada DB aprende un poco encima, con su autoexamen
4. Guardia                     ← si 2 o 3 no ganan el examen local, manda el piso
```

**Por qué puede servir para cualquier corpus:** si las agujas son **universales y normalizadas**
(parecido 0–1, ¿comparten entidades?, ¿mismo episodio?, ¿se activan juntos?, ¿ayudó?, ¿trajo
ruido?) y **nunca palabras** ("servidor", "memoria"), la neurona aprende *cómo se ve una asociación*,
no *de qué habla tu corpus*. Eso sí viaja.

**La prueba que hay que hacer (no basta con creerlo):** entrenar en el corpus de Dennys y medir en
otro corpus distinto. El Exp 08 mostró que el campeón del ranking **no** viajó bien, pero ese
aprendía cosas del corpus; esta neurona solo vería agujas universales, así que tiene mejor chance.
La guardia queda igual: si de fábrica no gana el examen local, no trabaja.

### 16.4 Lo que se descarta de lo que se habló

| Se dijo | Se descarta porque |
|---|---|
| "Eliminar" conexiones (Manus) | Norma: nunca borrar. Máximo: cuarentena reversible. |
| Registrar en cada búsqueda "qué fue útil" (Manus) | Norma: sin feedback y sin registrar lo que usó el agente. La evidencia sale del **autoexamen**. |
| Expandir automáticamente "todo lo relacionado" en cada búsqueda | Primero la neurona limpia el grafo; la expansión (neurona de saltos) va después y **solo si no baja el recall**. Hoy un salto ciego trae ~215 candidatos (medición B). |
| "Nunca habrá ruido" / "perfección absoluta" | Se mantiene como **meta**; la medida es: menos ruido, medido, sin perder recall. |
| Neuronas de enrutamiento, admisión, etc. | No se descartan, pero **no ahora**: primero esta. |

### 16.5 Qué tiene que dar Dennys a la neurona (el "agua correcta")

Lo que hoy **ya hay** y sirve: parecido de contenido, PPMI, sinónimos, dimensiones, vecinos en
común, categoría, grado, peso y tipo de la conexión, utilidad medible por autoexamen.

Lo que **falta** para que conecte "como un cerebro" (sección 15.3): **entidades núcleo**
(`sustantivos_clave`, casi vacío en el snapshot), **relaciones quién-qué-a-qué** (`predicados`, 12 %),
**episodio** (no hay id de episodio) y **contradicción** (no existe). Esas son las que, si hace falta,
entran por el MCP.

### 16.6 Próximo paso (para conversar antes de hacer)

**Banco de agujas del par A–B**, solo lectura sobre la copia: para cada aguja, cuánto separa las
conexiones útiles de las de ruido (usando la medición D como etiqueta). Con eso Dennys elige las
agujas y arma el piso. Nada del motor cambia en ese paso.

---

## 17. La neurona como intermediaria, y cómo lo hace el hipocampo

> Dennys: *"Cuando se hace la sinapsis por detrás, le pasas la información a la neurona y ella ve con
> qué puede asociarlo, como la intermediaria. El motor busca asociaciones y la neurona dice sí o no,
> según las agujas que ya tiene conectadas, igual que un humano. Hay que buscar la réplica de cómo
> funciona esa parte del hipocampo."*

### 17.1 La regla: el motor busca, la neurona decide

Hoy, en **cada** lugar donde nace una sinapsis, el motor hace dos cosas seguidas:

```
1. BUSCAR candidatos   (rápido: FTS, sinónimos, nombre, PMI, vecinos…)
2. DECIDIR con una regla fija   ("si se parecen ≥ 0.4 → conectar")
```

La neurona **reemplaza solo el paso 2**. El paso 1 (la velocidad del motor) queda igual. Ella es la
**intermediaria**: recibe A + cada candidato B con sus agujas, y responde sí / no / con qué fuerza.

### 17.2 Dónde nacen hoy las sinapsis (los puntos donde se enchufa)

**Dos familias:** las **directas** (`sinapsis`, 13,920) y las **latentes** — las "paralelas" que
recordaba Dennys — (`sinapsis_latentes`, 8,893): conexiones de dos pasos que el motor deduce
(A–B y B–C ⇒ A~C), con peso atenuado.

| Dónde nace | Archivo | Tipo que crea | Regla fija de hoy |
|---|---|---|---|
| Al pasar a largo plazo | `core/sinapsis.py` (`auto_vincular`) | `co_ocurrencia`, `co_nombre`, `co_semantica`, `pmi_hebbiano` | Jaccard ≥ .4 + cierre triádico; nombre ≥ 30 %; sinónimos; NPMI ≥ .35 |
| Sinónimos declarados | `core/sinapsis.py` (`vincular_por_sinonimos`) | `sinonimo_explicito` | Comparten un sinónimo |
| En la misma sesión | `core/memory/consolidation.py` L102/L159 | `co_ocurrencia` (0.4) | Se guardaron juntos |
| Durante una búsqueda | `core/memory/rafaga.py` L349 | `rafaga_rememb` (0.6) | La palabra buscada es también un recuerdo |
| Aprendizaje léxico | `core/lexical_learning.py` L317 | léxica | Formas de la misma palabra |
| Sueño (vacíos) | `core/sueno_vacios.py` L280/L307 | directas y latentes | Candidatos de un mismo hueco |
| DMN | `core/dmn_engine.py` L128/L331/L339 | `dmn_synthesized`, latentes | Síntesis del DMN |
| Inferencia transitiva | `core/inferencia_transitiva.py` L238 | latentes | Caminos de 2 pasos |
| El usuario / agente | `core/memory/synapses.py` (`vincular`) | `manual` | Decisión humana → **la neurona no la toca** |

### 17.3 Cómo lo hace el hipocampo (versión simple y fiel)

| Parte del hipocampo | Qué hace | En BioRAG |
|---|---|---|
| **Corteza entorrinal** (la entrada) | Entrega al hipocampo los rasgos ya procesados de la experiencia: qué, dónde, cuándo | Las **agujas** (calculadas por el motor) |
| **Giro dentado** | **Separa** recuerdos parecidos para que no se mezclen: dos recuerdos que comparten una palabra no quedan pegados | **Falta.** Hoy una palabra compartida basta para conectar. La neurona tiene que aprender a **no** conectar por coincidencias superficiales (penalizar palabras comunes y nodos "hub") |
| **CA3** | Red **autoasociativa**: une lo que se activa junto y **completa** un recuerdo desde una pista parcial | Las sinapsis, el spreading, la cadena, la SDM (**ya existe**) |
| **CA1** | **Compara** lo que CA3 propone con lo que llega de afuera; si no coincide, frena (detector de novedad / desajuste) | **La neurona**: compara la conexión propuesta contra la evidencia (agujas) y decide |
| **Regla de Hebb + tercer factor** (dopamina/novedad) | Una conexión se fortalece si se activan juntos **y** además "importó" | Coactivación **+ utilidad medida en el autoexamen** |
| **Repetición en el sueño** (*replay*) | De noche repasa lo del día: refuerza lo útil, pasa a memoria estable | Consolidación / sueño + autoexamen (**ya existe**) |

**Conclusión:** BioRAG ya tiene la "CA3" (conectar y completar) y el "sueño". Le faltan el **giro
dentado** (separar lo parecido pero distinto) y la **CA1** (el juez que compara propuesta vs.
evidencia). **La neurona asociativa es esas dos piezas**, enchufada en los puntos de la tabla 17.2,
aprendiendo con la regla de Hebb **más un tercer factor** (la utilidad del autoexamen).

Límite honesto: es una réplica **funcional** (qué hace cada parte), no física.
