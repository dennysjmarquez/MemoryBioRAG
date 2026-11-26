# R-E0, R-E1 y R-E2: el residual del buscador (2026-11-26). Diagnóstico sintético, nada implementado

> **Resultado final (R-E2, §7):** el residual **no es del buscador ni del PPMI**: es la **Neurona 1**
> (`core/memory/neurona.py`). Aprende en cada sueño con su autoexamen, y en D llega a un campeón que reordena el
> top-5, mientras que en D∪I0 no asciende ningún campeón. El «factor PPMI» de R-E1 la apagaba sin querer: su
> huella del motor cambia con `BIORAG_PPMI_WEIGHT` y descarta el campeón. Las secciones §3–§6 se conservan como se
> escribieron; donde §5–§6 dicen «familia PPMI», léase según §7.

[V] = medido aquí o leído en el código. [D] = deducción sin medir.

## 0. Permisos y alcance
- Aprobado en la revisión del 26-11: R-E0 (lectura estática) y R-E1 (prueba 2×2 sin tocar el código). El resultado
  se informa **antes** de arrancar el ciclo 2.
- Solo el laboratorio sintético: bases en `/tmp` creadas desde cero con `mundo_sintetico.py`. Sin DB viva, sin
  snapshots, sin datos privados, sin UD PUD y sin la QA oficial.
- **Sin cambios** en el motor, los tests ni `laboratorio_h2.py`. Scripts nuevos: `residual_re.py` (R-E0 + R-E1) y
  `residual_re0b.py` (lectura estática de los índices PPMI). Datos en `resultados_residual/`.

## 1. Diseño
- **Brazo y mundos:** −H2 −4b, reloj comprimido, mundos D y D∪I0. I0 no comparte ningún carácter con D.
  Semillas 7, 11 y 23; mundos de 1000 y 3000. 480 consultas fijas por configuración, las mismas de la medición
  anterior.
- **Factor A, cuándo se fija el corte de la cohorte de búsqueda congelada** (`search_baseline_rowid`,
  `growth_stable_fts.py`):
  - «medir»: como en la medición anterior; el corte se fija al abrir la copia para medir, con D∪I dentro;
  - «trasD»: el motor se cierra y se reabre una vez justo después de la fase D, en los dos mundos, así que el corte
    se fija con solo D dentro.
- **Factor B,** solo al medir: `BIORAG_PPMI_WEIGHT` = 0,15 (por defecto) o 0. La construcción es idéntica.
- **Métrica:** consultas cuyo top-5 cambia entre D y D∪I0.

## 2. Controles [V]
- **Reproducibilidad:** con «medir» y 0,15 se obtienen **exactamente** las cifras de la medición anterior
  (5/36/26 a 1000 y 8/11/11 a 3000).
- En todas las celdas:
  - el estado de D (estado e importancia) es idéntico en D y en D∪I0;
  - I0 no entra en ningún top-5, así que todo cambio es de **orden entre recuerdos de D**;
  - cada consulta parte del mismo estado (copia restaurada).
- **El corte se aplicó como se diseñó:**
  - con «medir», en la base construida no queda ningún corte guardado ni FTS de referencia;
  - con «trasD», el corte es 800 o 2400 (= |D|) y el FTS de referencia tiene |D| filas, en los dos mundos.

## 3. R-E1: resultados [V]
Consultas con el top-5 cambiado, de 480 (semillas 7 / 11 / 23):

| mundo | corte «medir», PPMI 0,15 | «medir», PPMI 0 | «trasD», PPMI 0,15 | «trasD», PPMI 0 |
|---|---|---|---|---|
| 1000 | 5 / 36 / 26 | **1 / 3 / 1** | 19 / 28 / 20 | **0 / 1 / 0** |
| 3000 | 8 / 11 / 11 | **0 / 0 / 0** | 7 / 7 / 28 | **0 / 0 / 0** |

Por escritura: 152 de los 153 cambios con PPMI 0,15 son latinos (`lat_a`/`lat_b`) y 1 es japonés. Unas 200 de las
480 consultas no devuelven nada en ninguno de los dos mundos (igual en D y D∪I0; brazo −H2 −4b comprimido).

**Lectura:**
1. **H-R1 (el corte fijado con I dentro) no es la causa principal: queda refutada.** Fijar el corte tras D no hace
   desaparecer el residual con PPMI activo. Lo sube en 2 de las 6 configuraciones (5→19 y 11→28) y lo baja en las
   otras 4.
2. **El residual vive en lo que activa `BIORAG_PPMI_WEIGHT`.** Con el peso en 0 cae de 1–7,5 % a 0–0,6 %.
3. **El corte explica, como mucho, un resto pequeño:** con PPMI 0 pasa de 1/3/1 a 0/1/0 a 1000, y a 3000 ya era 0.

## 4. R-E0 y R-E0b: lectura estática [V]
- En D y en D∪I0 son idénticos los vectores PPMI de los conceptos de D (`nodos`, por hash) y la tabla `tokens`
  (token, frecuencia y vector; 53 filas en s11/1000, por hash).
- `sinapsis_latentes` tiene 0 filas en todas las bases y `adn_firmas` también 0: H-R3 y el ADN quedan descartados
  en el laboratorio.
- Lo que sí difiere es `n_docs` del índice PPMI (`ppmi_hybrid_search.py` L91–92: 773 frente a 973), que pondera el
  vector de consulta con `log((n_docs+1)/(freq+1)) + 1` (L103). **Es un IDF global sin congelar.**
- Pero ese IDF **no explica el residual medido:** con el tokenizador del índice PPMI, solo 8 de las 480 consultas
  tienen vector de consulta (6 `lat_a` y 2 `lat_b`). En esas 8, el vector cambia por `n_docs`: sustituyendo el
  `n_docs` de D desaparece la diferencia. **Ninguna de las 36 consultas que cambian está entre esas 8.**

## 5. Qué queda sin identificar y cómo cerrarlo
- **Verificado:** el residual depende del interruptor `BIORAG_PPMI_WEIGHT`, y ese interruptor no apaga una sola
  señal. Con 0:
  - no se carga `_ppmi_index` (`memory_store.py` L185–191);
  - no se crean ni el neocórtex ni el motor ADN (L193–205);
  - desaparecen el vector de consulta, el campo potencial PPMI (`search.py` L2170–2177), la analogía
    (`scoring.py` L146–170, `search.py` L2151) y la señal #13;
  - cambia el denominador de los pesos (`scoring.py` L328).
- **No identificado:** cuál de esos componentes reacciona a I0 en consultas sin vector PPMI. Candidatos [D], sin
  medir:
  - componentes que leen el índice PPMI entero en la búsqueda (`todos_los_conceptos`, `n_docs`, `contenidos`,
    `grafo_sin` con aristas `pmi_hebbiano`, que pueden diferir entre D y D∪I0 porque su NPMI es global);
  - una diferencia entre el tokenizador del buscador y el del índice PPMI (la comprobación del §4 usa el del índice).
- **R-E2, propuesto y no ejecutado (necesita OK):** instrumentar el buscador **solo en la copia del proceso hijo**
  para volcar, en las consultas que cambian, el valor de cada señal del score en D y en D∪I0. Así se ve qué
  componente difiere. Costo: una configuración (s11/1000), ~4 min.

## 6. Consecuencias para el ciclo 2 [D] (superado por §7)
- El residual **no es un artefacto del laboratorio** por el corte: es una dependencia real del buscador respecto
  del corpus, dentro de la familia PPMI. Sigue informándose como «cambio residual no atribuido» hasta R-E2.
- **Para medir H2/4b sin ese ruido,** el ciclo 2 puede medir con dos pesos PPMI: 0,15, que es lo real, y 0, como
  control que aísla el buscador. Así lo atribuible a H2/4b se separa limpio.
- **Fijar el corte tras D** se recomienda igualmente: así vive una base real, y elimina el resto pequeño.
- En el motor no se toca nada. Si R-E2 encuentra el componente, el arreglo sería otro ciclo con su propia
  autorización. Un ejemplo sería congelar `n_docs` como ya se congeló el BM25; no se propone sin evidencia.

## 7. R-E2: qué componente cambia (aprobado el 26-11; s11, mundo de 1000, corte «medir», PPMI 0,15) [V]
**Método:** `residual_re2.py` instrumenta **solo en el proceso hijo**, sobre copias de las bases sintéticas, con
envoltorios que registran y devuelven el resultado intacto:
- los kwargs y el score de cada candidato en `_calcular_score_hibrido`;
- los componentes de `score_candidato`;
- la página antes y después de la convergencia multicampo, de la Neurona 1 y del ADN.
**Control:** con la instrumentación se reproducen exactamente las 36 consultas cambiadas de R-E1. Datos en
`resultados_residual/re2_s11_n800.json` y `re2_neurona0_s11_n800.json`.

**Resultados:**
1. **La pista del revisor se cumple, pero no es la causa.** En las 36 consultas el vector de consulta es
   `np.zeros(100)`, así que se entra en `score_candidato`. Pero `s_ppmi`, `s_idf`, `s_hop`, el total y el tamaño del
   pool son **idénticos** en D y en D∪I0, en todas las consultas (cambiadas o no).
2. **El ADN no está listo** (`adn_firmas` vacía) y no reordena ninguna consulta. El neocórtex existe en los dos
   mundos.
3. **La Neurona 1 explica 35 de las 36.**
   - En D hay campeón y reordena 37 consultas; en D∪I0 no hay campeón y no reordena ninguna.
   - En las 35, el orden de D **antes** de la neurona es exactamente el top-5 final de D∪I0.
   - Estado guardado (`neurona_estado`, leído en modo solo lectura): en D, 22 ciclos, **3 ascensos**, guardia del
     campeón 0,9506 frente a 0,9259 a mano. En D∪I0, 22 ciclos, **0 ascensos**, 9 reinicios y 9 ciclos sin mejora
     (el retador saca 0,9268 en la guardia frente a 0,939 a mano).
   - La neurona se examina con los recuerdos recién consolidados, que en D∪I0 incluyen I0, así que aprende otra cosa.
4. **La que queda (1 de 36) viene del corte:** `bm25_norm` difiere en milésimas entre los dos mundos (0,2708 frente a
   0,2703), porque con el corte «medir» la cohorte BM25 congelada incluye a I0. La convergencia multicampo convierte
   ese empate casi exacto en un cambio de orden. En total, `bm25_norm` difiere en 20 de las 36 consultas, pero solo
   decide en esta.
5. **Por qué el «factor PPMI» apagaba la neurona** (código):
   - `huella_motor` (`neurona.py` L214–235) resume la salida de `_calcular_score_hibrido` con entradas fijas;
   - esa salida depende de `PPMI_VECTOR_WEIGHT`, que está en el denominador (`scoring.py` L328);
   - con 0 al medir, la huella no coincide con la guardada, `_cargar` descarta lo aprendido (`neurona.py` L392–397)
     y no hay campeón en ningún mundo.
6. **Confirmación:** con `BIORAG_NEURONA=0` solo al medir (PPMI 0,15, corte «medir»), el residual baja de **36 a 2**,
   y las 2 son las de bm25 (x1100121|2 y x1100234|2).

**Lectura:**
- **Lo que llamábamos «residual del buscador» es la Neurona 1:** un reordenador aprendido en vivo a partir del
  corpus.
- **Hace lo que dice su diseño** (aprende de los recuerdos nuevos, con piso, techo y guardia). Pero eso significa
  que **F(D,q) ≠ F(D∪I0,q) cuando el campeón difiere**, aunque I0 no comparta ni un carácter con D.
- Con el corte tras D, el resto de BM25 desaparece (R-E1: «trasD» y PPMI 0 da 0/1/0 y 0/0/0).
- El resto de la familia PPMI (`n_docs`, el campo potencial y la analogía) no cambió ninguna consulta en esta
  configuración.

## 8. Ajuste de control para el ciclo 2 (propuesta, no ejecutada) [D]
- **Configuraciones:**
  - **real:** Neurona 1 activa, PPMI 0,15;
  - **control:** `BIORAG_NEURONA=0` **durante toda la corrida** (construcción y medición), no `BIORAG_PPMI_WEIGHT=0`.
    El peso PPMI cambia la fórmula a mano; apagar la neurona aísla H2/4b sin tocar la fórmula.
- **Corte fijado tras D** en los dos brazos, para eliminar el resto de BM25.
- **Registrar por mundo el estado de la Neurona 1** (campeón sí/no, ascensos, huella), para que un cambio del top-5
  se pueda atribuir a la neurona y no a H2/4b.
- **Sobre la medición anterior:** su (b), el cambio total del top-k, incluye el efecto de la Neurona 1. Los
  hallazgos de estado (H2 duerme D, cruces de 4b, K4, K6 y K8) no dependen del buscador y siguen en pie. Los
  atribuibles del top-k (K1) pueden contener efecto de la neurona, porque su campeón puede diferir entre brazos.
- **Neurona 1:** no se toca (regla vigente). Que dependa del corpus queda documentado como hallazgo, para que
  Dennys decida si se estudia aparte.
