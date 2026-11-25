# Experimento 16: protocolo de medición para la neurona sináptica (NS-1), solo con datos sintéticos

**Fecha:** 2026-11-25 · **Rama:** `arena/da3df5df-memorybiorag`.

**Este protocolo se fija y se sube ANTES de medir.** Ningún umbral de este archivo se cambia después de
ver resultados. Si hiciera falta cambiar algo, se escribe un protocolo nuevo con fecha, y lo medido con
este queda tal cual.

## 0. Límites (decisiones de Dennys del 2026-11-25)

| # | Decisión | Cómo se cumple aquí |
|---|---|---|
| 1 | El 20 % es un **conjunto de evaluación sellado**, aparte del entrenamiento. El tope de corrección es otra decisión y **no se fija todavía** | §3. La partición es por tema: ningún par relacionado queda de los dos lados. No hay tope de corrección en este protocolo |
| 2 | **U0:** no se guarda ninguna señal nueva de uso por sinapsis. El canal 2 no cuenta como uso. `ultimo_uso` no es una señal fiable. Sin feedback del agente ni telemetría | Ninguna métrica ni ninguna aguja usa `ultimo_uso`, apariciones en el canal 2 ni feedback |
| 3 | **No se usa** la DB viva, ni recuerdos privados, ni **el snapshot** para entrenar o contar enlaces. `manual` y `desvincular` no son etiquetas | Todo sale de un **generador sintético** con la verdad conocida por construcción. Ninguna etiqueta viene de `manual`, `desvincular` ni Gemini |
| 4 | Las decisiones de la hormiguita y Gemini no son verdad ni datos | No se leen |
| 5 | Agregar recuerdos irrelevantes no debe cambiar la puntuación de un par fijo. Para el canal 2 se define antes qué cambios son legítimos. La neurona nunca oculta, borra ni filtra al recordar. No renacer tras `desvincular` es una regla aparte | §5 (invariancia). La regla de no renacer está en `REGLA_NO_RENACER_TRAS_DESVINCULAR.md`, **sin implementar** |
| — | **No se autorizan F1–F6** ni cambios en pesos, nacimiento, poda, cuarentena, hormiguita, tests o motor. E3 sigue abierto y no se pasa a E4 | Este experimento **no modifica ningún archivo** del motor ni de los tests. Usa el código del motor tal cual, sobre bases sintéticas en `/tmp`, y las borra al terminar |

**Qué se mide en esta etapa.** Solo la **línea base del piso**: cómo nacen hoy las sinapsis, con el
motor sin cambios, en mundos sintéticos. **No se entrena ni se prueba ninguna neurona.** Los criterios
de la neurona (§7) quedan fijados aquí para cuando se autorice esa fase.

**Resultados nuevos frente a históricos.** Todo lo que salga de aquí es **nuevo** y vale solo para
mundos sintéticos. Las cifras de los experimentos 12–15, del mapa verificado y de `uso_como_agente`
salieron del snapshot o de la DB viva: son **históricas**, no se mezclan ni se comparan número a número
con estas.

## 1. El mundo sintético (`mundo.py`)

Es un generador determinista (semilla fija) que imita los rasgos que hacen nacer ruido hoy. La
**verdad** se conoce por construcción.

| Rasgo | Cómo se genera | Qué ruido de hoy imita |
|---|---|---|
| Temas y subtemas | `T = 20` temas × 3 subtemas. Cada tema tiene un vocabulario propio de pseudopalabras (≥ 5 letras, sin significado en ningún idioma, así que no hay licencias ni coincidencias reales) | Contenido real con tema |
| Palabras genéricas | 12 palabras que aparecen en todos los temas (tipo «sistema», «version», «protocolo»), con frecuencia alta | Enlaces por palabras comunes |
| Siglas cortas | 8 tokens de 2–3 letras repartidos al azar sin relación con el tema | Los enlaces accidentales por palabras de ≤ 3 letras |
| Nombres | `palabra_del_tema_palabra_del_subtema_n`; en el 30 % de los casos, además, una palabra genérica | El ruido de `co_nombre` (una palabra de tres) |
| Sinónimos (`syn`) | 6–10: 70 % del tema, 20 % genéricos, 10 % frases de dos palabras | `co_semantica` y `sinonimo_explicito` por `LIKE` |
| Dimensiones | Perfil del tema en 3–5 ejes del catálogo real, con un 20 % de ruido | Dimensiones compartidas |
| Sustantivos clave | 2–4 del núcleo del subtema | La declaración del agente |
| Sesiones | Grupos de 3–6 recuerdos guardados juntos. Con probabilidad 0,6 son del mismo tema; si no, al azar | La co-ocurrencia de sesión |
| Hubs | 4 recuerdos «registro_general_k» con palabras genéricas y de muchos temas. Cada uno se guarda de nuevo 5 veces a lo largo del tiempo | Recuerdos como `version_actual_biorag` |

**La verdad (relevancia de un par):**
- 2 si son del mismo subtema;
- 1 si son del mismo tema;
- 0 en cualquier otro caso. Los hubs tienen relevancia 0 con todos (son genéricos).

**Mundos medidos:** semillas 1, 2 y 3, con `N = 400` recuerdos cada uno, más los hubs.

**Costo:** 3 mundos × 4 variantes (§5) × una construcción completa con el motor. No usa la QA oficial
(no hay QA para mundos sintéticos).

## 2. Cómo se construye cada mundo con el motor (sin modificarlo)

Por cada recuerdo, en orden de sesión, se repite el camino de `aprender` del MCP
(`core/mcp_server/write.py`, L295–322):
1. `_resolver_dimensiones`;
2. `percibir_corto_plazo`;
3. `auto_vincular`;
4. `vincular_por_sinonimos`.

Además:
- Se llama a `ciclo_sueno_consolidacion()` **cada 50 recuerdos** y una vez al final.
- Se usa una sola instancia del cerebro por mundo, sobre una base nueva en `/tmp`, con
  `HOME` aislado y `PYTHONHASHSEED=1`.

**Lo que no se replica:** los bridges ni los concept hubs (no crean sinapsis), ni `vincular_con`
(manual: decisión 3).

**Limitación declarada:** el tiempo del mundo es el reloj real de la corrida (minutos). El olvido del
sueño apenas actúa, porque se escala por el tiempo real (D15).

## 3. Partición sellada del 20 %

- Un tema `t` queda **sellado** si `int(sha256("tema_%d" % t)[:8], 16) % 5 == 0`.
- Un par es **sellado** si alguno de sus extremos pertenece a un tema sellado. Los hubs no tienen
  tema: un par hub–X sigue la regla de X.
- Como la relevancia > 0 exige el mismo tema, **ningún par relacionado puede quedar de los dos lados**.
- **Entrenamiento futuro:** solo pares con los dos extremos en temas no sellados. **Evaluación:** solo
  pares sellados.
- Para el piso se reportan las métricas sobre **todo** el mundo y sobre la parte sellada, para que
  después se puedan comparar con la neurona.

## 4. Métricas de calidad

La **puntuación del par** es `max(peso a→b, peso b→a)`, o 0 si no hay sinapsis.

| Métrica | Definición |
|---|---|
| **Q1. AUC** | Puntuación de los pares relevantes (rel > 0) contra los irrelevantes (rel = 0), entre todos los pares con al menos una sinapsis automática |
| **Q2. Precisión de nacimiento** | De los pares con sinapsis automática, qué fracción es relevante |
| **Q3. Cobertura** | De los pares con rel = 2, qué fracción tiene alguna sinapsis |
| **Q4. Canal 2** | Para cada recuerdo, la lista visible que devuelve el motor real (`obtener_asociaciones_enriquecidas`, `top_vecinos=5`): precisión@5 media (rel > 0) y cuántos recuerdos quedan sin ninguna asociación visible |
| **Q5. Hubs** | Grado máximo, y cuántos recuerdos tienen más de 3 × la mediana del grado |
| **Q6. Renacimiento** | Al terminar se toman 30 sinapsis con rel = 0 (con semilla fija) y se les aplica `desvincular`. Después se vuelve a guardar su recuerdo de origen (mismo contenido, camino de §2) y se consolida. Se mide qué fracción vuelve a tener sinapsis. Es una medición del sistema de hoy, no una regla |

## 5. Invariancia: definida antes de medir

**Variantes de cada mundo:**
- `D`: solo el mundo.
- `D∪I_puro`: se agregan 400 recuerdos de 10 temas nuevos, con vocabulario propio, **sin** palabras
  genéricas ni siglas compartidas.
- `D∪I_real`: lo mismo, pero los recuerdos irrelevantes **sí** usan las palabras genéricas y las siglas,
  como pasa en una memoria real.
- `D_orden`: los mismos recuerdos de `D`, con el orden de las sesiones permutado (semilla fija). Mide
  la sensibilidad al orden de almacenamiento.

Los recuerdos de `I` se **intercalan** en la línea de tiempo (con semilla fija), no van al final.

**Qué es irrelevante:** todo recuerdo de `I`, por construcción (relevancia 0 con todo `D`).

**Contrato para un par fijo** `(a, b)`, con `a` y `b` en `D`: su puntuación debe ser igual en `D` y en
`D∪I`.
- **Tolerancia: |Δ| ≤ 1e-9**, es decir, igualdad numérica.
- **I1:** fracción de pares de `D` (con sinapsis en alguna de las dos variantes) que violan el
  contrato.
- **I2:** mayor |Δ| observado.
- **I3:** pares que **existen solo en una** de las dos variantes (aparecen o desaparecen).

**Contrato para el canal 2** de cada recuerdo de `D`:
- **Legítimo:** ningún cambio, porque `I` es irrelevante por construcción.
- **Violación:**
  - que un recuerdo de `I` ocupe un lugar en la lista de un recuerdo de `D` (**I4**: fracción de
    lugares ocupados por recuerdos de `I`);
  - que cambie el orden o el contenido de la lista entre recuerdos de `D` (**I5**: fracción de
    recuerdos de `D` cuya lista cambió).

**Orden:** I1–I5 se calculan también entre `D` y `D_orden`. En ese caso la tolerancia también es
igualdad, porque la reproducibilidad con las mismas entradas es obligatoria (norma máxima de
AGENTS.md) y el orden de almacenamiento está declarado irrelevante.

**Para el piso** no hay aprobado ni reprobado: se **reporta** el valor. Si viola el contrato, queda
como un **hallazgo**, y ese hallazgo bloquea que la neurona herede esas agujas tal cual (ver §7).

## 6. Determinismo

Cada mundo `D` se construye **dos veces** con la misma semilla.
- **R1:** las dos tablas `sinapsis` (origen, destino, tipo, peso) deben ser idénticas.
- Si no lo son, se reporta y todas las métricas de ese mundo se marcan como «no reproducibles».

## 7. Criterios para la neurona (fijados hoy, para una fase futura que hay que autorizar)

Sobre la **parte sellada**, en las 3 semillas, la neurona **pasa** solo si cumple **todo**:

1. **Q1:** AUC ≥ AUC del piso + 0,05, y ≥ 0,80.
2. **Q4:** precisión@5 ≥ la del piso + 10 puntos, y recuerdos sin asociaciones ≤ los del piso.
3. **Q3:** cobertura ≥ la del piso. Que nazca menos no puede costar relaciones reales.
4. **Invariancia:** I1 = 0, I3 = 0, I4 = 0 e I5 = 0 en `I_puro`, `I_real` y `D_orden`.
5. **Determinismo:** R1 idéntico.
6. **Calibración:** error de calibración esperado (ECE, 10 bins) ≤ 0,05 sobre la parte sellada.
7. **Costo:** el tiempo por decisión con `N = 1600` es ≤ 1,5 × el tiempo con `N = 400`.
8. **Generalización:** en un mundo de **otra familia** de parámetros, que no se use para entrenar
   (`T = 35`, 5 subtemas, 25 % de palabras genéricas), el AUC sellado debe ser ≥ AUC del piso + 0,03.

**Se descarta** si falla cualquiera de los ocho. No hay «casi pasa».

**Lo que este protocolo no puede medir:** el recall en la QA oficial. Eso necesita el corpus real, y
hoy está fuera de alcance por la decisión 3. Antes de cualquier integración haría falta una
autorización aparte.

## 8. Salidas

- `resultados/piso_semilla{1,2,3}.json`: todas las métricas por variante.
- `RESULTADOS.md`: las tablas y su lectura, separando lo medido de lo interpretado.
- Las bases se crean en `/tmp/exp16` y se borran al terminar. No se sube ninguna base.
