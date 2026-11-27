# Cierre del ciclo H2/4b y lectura científica: por qué falló cada brazo y dónde más puede estar la solución

> **Decisión (Dennys, 26-11):** el ciclo H2/4b se cierra aquí, sin ciclo 3.
> - **T** sigue en el motor sin cambios.
> - **4b-propio** se descarta en su forma actual, con umbral fijo de 0,70.
> - **K7′** se mantiene por sueño, como se aprobó; el costo por recuerdo activo se informa como métrica secundaria.
>
> Este documento **no reabre el ciclo** ni cambia ningún veredicto. Cumple la otra mitad de la indicación de Dennys:
> un resultado negativo no se deja ahí. Se pregunta **por qué** falló cada brazo, qué principio general sale y en qué
> otros lados puede estar la solución. Cada vía queda como **hipótesis con condición de reapertura**, para su propio
> ciclo, y solo con OK.
> Marcas: [V] verificado con datos de este repo · [D] deducción · [B] analogía biológica (orienta, no prueba).

## 1. El principio que sale del ciclo [D, apoyado en §3.1 de `RESULTADOS_CICLO2.md`]

**Todo mecanismo de competencia (suma cero) cuyo conjunto de competidores pueda contener a I rompe
F(D, q) = F(D ∪ I, q).** Da igual si es global o local.

| mecanismo | conjunto de competidores | ¿puede entrar I? | resultado [V] |
|---|---|---|---|
| H2 de hoy | todos los activos | siempre | rompe (101→0 de D activos en comprimido) |
| H2-local | la vecindad en el grafo | sí, con **una** arista accidental | rompe (2 aristas de ruido D–I0 → los 2 recuerdos de D que cambian) |
| 4b de hoy | la media de todos los activos | siempre | rompe (cruce del 0,70 por I a 3000) |
| 4b-propio | ninguno (decide cada uno) | no | invariante, pero el umbral fijo actúa como desgaste extra |
| −H2 −4b | ninguno | no | invariante en estado |

**La pregunta útil no es «¿competencia global o local?», sino «¿quién define el conjunto de competidores, y puede
I entrar en él?».** Las vías de §3 nacen de esa pregunta.

## 2. Por qué falló cada brazo (mecanismo, no solo veredicto)

1. **H2-local duerme casi tanto como H2** (cerca del 60–65 % de D) [V].
   - **Causa [D]:** el umbral heredado, 0,8 · |N|, está **por debajo del estado normal** de un recuerdo nuevo (peso
     1,0). Toda vecindad joven «excede» por construcción.
   - Ni H2 ni H2-local fallan por ser globales o locales: fallan porque su umbral confunde el estado de reposo con un
     exceso.
2. **H2-local no aísla D de I** [V en s7/800]: el conjunto de competidores pasa por aristas, y las aristas
   automáticas tienen ruido.
3. **4b-propio** no ganó nada [V].
   - Con H2 encendido, H2 lo tapa en el reloj comprimido.
   - En el diario, el umbral fijo de 0,70 desgasta a todo recuerdo sano.
   - La idea de Turrigiano es un punto de equilibrio **propio de cada neurona**, no uno común para todas [B].
4. **−H2 −4b** cumple el estado. Lo que falla es la **cantidad** de aristas, no su calidad por tipo [V]:

   | ctl, D∪I1 (suma de las 3 semillas) | precisión de `pmi_hebbiano` | precisión total |
   |---|---|---|
   | T, 800 comprimido | 61/475 = 0,128 | 0,830 |
   | −H2 −4b, 800 comprimido | 92/728 = **0,126** | 0,757 |
   | T, 2400 comprimido | 82/1358 = 0,060 | 0,831 |
   | −H2 −4b, 2400 comprimido | 224/2796 = **0,080** | 0,701 |

   - Con más recuerdos despiertos nacen más `pmi_hebbiano`, con la **misma o mejor** precisión por arista. La
     precisión total baja por composición: hay más aristas de un tipo ruidoso.
   - Además, −H2 −4b casi duplica las aristas de puente (61 frente a 34; suma de las 3 semillas, ctl, 800 comprimido, D∪I1) [V].
   - **Ordenar** esas aristas es justo el trabajo de la neurona sináptica (Paso 3/4), no de H2/4b.
5. **La referencia T era degenerada en comprimido** [V]: duerme todo D (0 recuerdos de D visibles, sin listas de
   orden).
   - Comparar K4/K5/K7 contra T premia dormir: con casi nada despierto, cualquier precisión o costo sale «bueno».
   - **Lección de protocolo** para cualquier ciclo futuro: la referencia de calidad debe ser el estado invariante
     (−H2 −4b), y las métricas de cantidad deben fijarse por recuerdo activo, **antes** de medir. En este ciclo no se
     cambia ningún veredicto.

## 3. Dónde más puede estar la solución (hipótesis, cada una con su prueba y su condición de reapertura)

### V1. Competencia solo por aristas verificadas (H2-local después de la neurona sináptica)
- **Idea:** H2-local compite por la vecindad, pero contando solo aristas que la neurona sináptica haya validado, o las
  del agente.
- **Observación a favor [V]:** H2-local ya actúa como un filtro débil de aristas. La precisión de `pmi_hebbiano` sube
  de 0,128 a 0,218 a 800 comprimido, y de 0,060 a 0,162 a 2400 comprimido. **[D]** Los recuerdos que quedan
  despiertos son más coherentes entre sí.
- **Prueba barata previa:** un brazo **oráculo** en el laboratorio, con H2-local solo sobre aristas cuya verdad es tema
  o puente. Da el techo:
  - si ni con aristas perfectas conserva K4/K5″, la vía se cierra;
  - si los conserva, queda cuantificada la calidad de aristas que la neurona tiene que alcanzar.
- **Reapertura:** cuando el Paso 4 dé puntajes de aristas medidos en la guardia sellada.

### V2. Competencia por cohorte de nacimiento [B: etiquetado sináptico y captura, Frey y Morris 1997]
- **Idea:** los recuerdos consolidados **en el mismo sueño** compiten entre sí, como las memorias codificadas en la
  misma ventana compiten por los mismos recursos de plasticidad.
- **Por qué es invariante por construcción [D]:** un I que llega después nunca entra en la cohorte de D.
- **Riesgo, a medir:** si I llega en la **misma sesión** que D, comparte cohorte. El K8 actual no lo prueba (no mezcla
  dentro de una sesión), así que haría falta un mundo con sesiones mezcladas por dentro.
- **Umbral:** no puede ser 0,8 (ver §2.1); tiene que ser relativo al estado de reposo (V3).
- **Reapertura:** con OK, como ciclo propio.

### V3. Homeostasis con punto de equilibrio propio [B: Turrigiano]
- **Idea:** cada recuerdo regula su peso **contra su propio peso de nacimiento** o su propia historia, nunca contra
  0,70 ni contra la media de todos.
- Es 4b-propio corregido: sin umbral común y sin desgaste para el que está en reposo.
- **Invariante por construcción** (local al recuerdo).
- **Reapertura:** con OK. Se puede probar en el mismo laboratorio, con criterios por recuerdo activo fijados antes.

### V4. La función de H2 sin competencia
- **Idea:** H2 existe para acotar el costo del sueño y el ruido. Con −H2 −4b, el costo por recuerdo activo ya es
  **menor** que en T [V] (s7, ctl: 0,00037 s frente a 0,00072 s a 800 comprimido).
- Lo que crece es el número de activos. Acotar el **trabajo** por sueño (K recuerdos por ciclo, costo fijo, como ya
  prevé el molde de la neurona sináptica) resuelve el costo **sin dormir a nadie por competencia**.
- **Reapertura:** se evalúa junto con E3 (el sueño en modo sombra), no antes.

## 4. Lo que el ciclo encontró fuera de su objetivo (y vale más que un brazo ganador)

1. **La Neurona 1 multiplica el residual del top-k** (32 frente a 6, y 44 frente a 8) sin tocar el estado [V]. Es
   la lección para la Neurona 2, recogida en el protocolo del Paso 3 (§7).
2. **Dos fallos reales del motor**, callados por sus propios `try/except` (`HALLAZGOS_DEL_MOTOR_K8.md`):
   - F-A: alias inexistente en `search.py` L1488, que deja muerto el premio por coincidencia de contenido;
   - F-B: PPMI en bases jóvenes, con 605 de 777 vectores en cero en el reloj comprimido. Es la causa probable del
     «vector nulo» de R-E2.
3. **El laboratorio no tiene recuerdos inmunes** (prioridad 3, valencia 0 y categoría General en todos) [V].
   - Ningún camino de inmunidad se probó en ninguna medición de H2.
   - La diferencia que señaló la auditoría (4b de hoy no excluye la prioridad 0/1; H2 y LTD sí) **no cambió ningún
     número**, pero queda sin probar.
   - Un ciclo futuro debe incluir recuerdos inmunes en el mundo.

## 5. Ticket abierto: invariancia del sueño

| campo | valor |
|---|---|
| estado | abierto, sin trabajo asignado; no frena la neurona sináptica |
| problema | con H2 y 4b de hoy, añadir recuerdos irrelevantes cambia qué recuerdos de D duermen (medición H2 y ciclo 2) |
| lo que se sabe | competencia + conjunto de competidores con posible I ⇒ no invariante (§1); el umbral de 0,8 está por debajo del reposo (§2) |
| vías | V1 (tras el Paso 4), V2, V3 y V4 (con E3) |
| deudas del laboratorio | recuerdos inmunes; sesiones mezcladas por dentro; referencia = estado invariante; métricas por recuerdo activo; arreglar o aislar F-B antes de leer el top-k en comprimido |
