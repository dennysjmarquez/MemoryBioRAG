# E2b — tolerancia al ruido, temático saturado y limpieza de la QA

**Encargo del auditor:** A) medir R@5 y R@1 con una palabra inexistente añadida a
cada caso de la QA, en snapshot y viva, y desglosar el 0848. B) confirmar la
saturación del temático en la viva. C) que la QA del snapshot corra sobre una copia
temporal. **Sin reparar el ranking.**

**Regla cumplida:** cero código del motor. Todo sobre copias. `casos_qa.jsonl` no
se ha tocado.

---

## 0. Antes de los números: un intento que descarté

Mi primer intento fue copiar el bucle del arnés en un script propio. La copia daba
un baseline peor que el arnés (R@5 clásica 98,3 frente a 100,0 en el snapshot).
**Causa: mi copia no devolvía al estado inicial los 64 nodos que la QA despierta
entre caso y caso.** Una copia del arnés no es el arnés; esos números no se publican.
La medición de abajo sale del **arnés oficial** con una bandera nueva, así que las
condiciones son las de siempre: mismas restauraciones, misma resolución de
etiquetas, mismo trato de las ambiguas.

También descarté un segundo intento: instrumentar `_calcular_score_hibrido` para
ver las señales de cada candidato. **El espía cambiaba el resultado** (el esperado
pasaba de 1.º a 6.º solo por estar espiado), así que sus números no valen. Todo lo
que sigue está medido con la **API pública** del motor o con el arnés oficial, sin
meter mano dentro. El script del intento se ha borrado para que nadie lo reutilice
por error.

Banderas añadidas, **apagadas por defecto**:
- `BIORAG_QA_RUIDO=zzqx` — añade esa palabra **solo a la búsqueda**; `query` queda
  intacta para el control de ambiguas y para los informes.
- `BIORAG_QA_TEMATICO_CENSO=1` — cuenta candidatos y saturación sin cambiar ningún
  valor (envuelve y devuelve el mismo score).

---

## A. Tolerancia al ruido

QA oficial completa (921 casos, `BIORAG_NEURONA=0`), normal contra
`BIORAG_QA_RUIDO=zzqx`. Todo lo demás idéntico.

| | snapshot sin ruido | snapshot con ruido | viva sin ruido | viva con ruido |
|---|---:|---:|---:|---:|
| **clásica R@5** | 100,00 | **96,80** | 99,20 | **95,31** |
| clásica R@1 | 93,14 | 86,63 | 91,09 | 85,71 |
| clásica MRR | 0,9573 | 0,9116 | 0,9432 | 0,8990 |
| fallos (fuera del top-5) | **0** | **28** | **7** | **41** |
| **honesta R@5** | 100,00 (865) | **97,34** (865) | 99,88 (861) | **96,63** (861) |
| honesta R@1 | 95,31 (853) | 88,63 (853) | 93,53 (850) | 88,12 (850) |
| no llegó al 1.º | 40 | **97** | 55 | **101** |
| FP negativos | 0/40 | 0/40 | 0/40 | 0/40 |

**Una sola palabra inexistente cuesta**: −3,20 pp de R@5 y −6,51 pp de R@1 en el
snapshot; −3,89 y −5,38 en la viva. Y **los falsos positivos no se mueven** (0/40
en las cuatro corridas): el ruido no inventa respuestas, solo descoloca las buenas.

### Dónde pega, por categoría (honesta R@5)

| categoría | snapshot | viva |
|---|---:|---:|
| **cruce_idioma** | 100 → **62,5** (−37,50) | 100 → **62,5** (−37,50) |
| **sinonimo** | 100 → **88,89** (−11,11) | 100 → **85,37** (−14,63) |
| variante_gramatical | 100 → 95,38 (−4,62) | 100 → 92,31 (−7,69) |
| typo | 100 → 93,85 (−6,15) | 100 → 96,92 (−3,08) |
| por_tema | 100 → 95,38 (−4,62) | 98,46 → 92,31 (−6,15) |
| doctrina dormido | 100 → 98,46 (−1,54) | 100 → 98,46 (−1,54) |
| pregunta_natural | 100 → 98,46 (−1,54) | 100 → **100,0** (0,00) |
| literal | 100 → 99,38 (−0,62) | 100 → 98,56 (−1,44) |

**El orden es el esperado si la causa es la cobertura de alias**: lo que se rompe
son las consultas donde el nodo se reconoce por **una o dos palabras** (idioma,
sinónimo, variante, typo); lo que aguanta es la consulta larga y literal.

### A2. Qué cambia en el 0848: la causa, medida sin instrumentar el motor

Cinco consultas sobre las mismas copias, con la API pública (`limite=50`,
`profundidad="activos"`, `ignore_peso_sinaptico=True`, el esperado en `activo`).
Todas piden lo mismo; solo cambian las palabras.

**Snapshot**

| consulta | palabras | puesto del esperado | score | candidatos |
|---|---:|---:|---:|---:|
| `semánticas embedding` | 2 | **1** | **0,6143** | 122 |
| `semánticas 849 embedding` (el examen) | 3 | 4 | 0,3861 | 129 |
| `semánticas zzqx embedding` (inventada) | 3 | 4 | 0,3860 | 128 |
| `semánticas embedding julio` (palabra REAL) | 3 | 5 | 0,3949 | 147 |
| `limpieza semántica tabla embedding` | 4 | 1 | 0,8394 | 249 |

**Viva**

| consulta | palabras | puesto del esperado | score | candidatos |
|---|---:|---:|---:|---:|
| `semánticas embedding` | 2 | **1** | **0,6184** | 129 |
| `semánticas 849 embedding` (el examen) | 3 | **6** | 0,3732 | 683 |
| `semánticas zzqx embedding` (inventada) | 3 | **8** | 0,3731 | 683 |
| `semánticas embedding julio` (palabra REAL) | 3 | 4 | 0,4216 | 150 |
| `limpieza semántica tabla embedding` | 4 | 1 | 0,5514 | 299 |

**Lo que dicen estos números, en orden de importancia:**

1. **No es la palabra inventada: es cualquier palabra de más.** Con `julio`, que
   existe en el corpus, el esperado también se cae (puesto 5 en el snapshot).
   El auditor tenía razón y el fenómeno es más general de lo que parecía.
2. **La caída es un acantilado, no una pendiente.** De 0,6143 a 0,3860: −0,228 de
   golpe (−37 %) por una sola palabra. Un nodo que gana por 0,065 pasa a perder.
3. **La causa está en dos umbrales que saltan juntos.** La cobertura de alias es una
   proporción: con dos palabras, acertar las dos es 2/2 = 1,00; acertar dos de tres
   es 0,633.
   - `sinonimos_ratio >= 0.95` → **bono en espacio logit**
     (`core/memory/scoring.py:377-386`). A 0,633 el bono **desaparece entero**.
     Ese bono es el que subía al nodo de 0,39 a 0,61.
   - `sinonimos_ratio < 0.5` → **compuerta del temático**
     (`core/memory/search.py:1749`). A 0,633 la compuerta **le apaga** la señal
     (0,08 de peso, ≈ +0,046 de score).
   O sea: al nodo que casi acierta se le castiga **dos veces** por el mismo token
   — pierde un premio y pierde una señal.
4. **Depende del largo de la consulta, no del tamaño de la base.** Una palabra de
   más en 2 palabras rompe el 33 % de la cobertura; en una consulta de 4 palabras
   (`limpieza semántica tabla embedding`) el nodo sigue en el puesto 1 pese a
   quedarse a 0,84 de cobertura. Las consultas cortas son las frágiles.
5. **Pero el daño sí cambia según la base** (esto es material para E4): con la
   misma palabra inventada, el número de candidatos pasa de 122 a 128 en el
   snapshot (**×1,05**) y de 129 a **683** en la viva (**×5,3**). El mismo token
   inexistente abre la puerta a 554 candidatos más solo en la base grande. `zzqx`
   sola devuelve 0 candidatos en las dos bases: el estropicio aparece al mezclarla
   con palabras que sí existen.

### A3. Por qué gana el rival del 0848

| | gana | esperado |
|---|---|---|
| consulta limpia (snapshot) | — | **0,6143, puesto 1**, 0,065 por encima del segundo |
| con una palabra de más | 0,4006 | **0,3860, puesto 4**, en un pelotón de 0,38–0,40 |

En la consulta limpia el esperado gana por el bono de alias. Al desaparecer el
bono, queda dentro del pelotón y lo decide el desempate: BM25 y el temático. Ahí
pierde, porque el temático **se le apaga a él** (ratio alto) y **no a los demás**.

---

## B. El temático está saturado

Censo medido dentro de la QA oficial, candidato a candidato (bandera
`BIORAG_QA_TEMATICO_CENSO=1`, que no altera ningún valor):

| base | candidatos puntuados | cobran el temático | saturados a **exactamente 1,0** | a 0 con `sinonimos_ratio >= 0.5` |
|---|---:|---:|---:|---:|
| snapshot | 293.768 | 204.781 | **204.781 (100,00 %)** | 2.544 |
| viva | 773.259 | 559.586 | **559.586 (100,00 %)** | 3.201 |

Medido en las corridas **con** la palabra de ruido (que infla el número de
candidatos, sobre todo en la viva: ahí el censo es 2,6 veces el del snapshot).
El conteo exacto depende de dónde se enganche el espía; el hecho —**saturación
del 100 % en las dos bases**— sale igual que en la cuenta del auditor
(145.744 / 5.442): no hay un solo candidato que cobre la señal sin cobrarla al
máximo.

**El 100 % de los que cobran la señal la cobran al máximo.** No gradúa nada: es un
+0,08 fijo para quien pasa la compuerta y un 0 para quien no. Y el que queda fuera
es, precisamente, el que mejor coincide en alias.

Es decir: la señal que se llama «temática» **no mide parecido temático**, mide
«¿pasaste la compuerta?». Mientras siga saturada, no ordena: solo reparte un
premio fijo y un castigo oculto.

---

## C. Higiene: la QA ya no toca la base que mide

**Qué pasaba:** al medir el snapshot, la copia se hacía abriendo el original con
`mode=ro`. SQLite, para leer una base en WAL, **crea el `-shm`** al lado del
fichero: la QA dejaba basura junto al snapshot.

**Qué se hizo** (`scripts/evaluar_qa.py`, solo QA):
- `mode=ro&immutable=1` cuando no hay `-wal` → SQLite no escribe nada al lado.
- Si hay `-wal`, se abre con `mode=ro` (con `immutable` se perderían esas
  transacciones) y **se borran al terminar solo los sidecars que ha creado la QA**;
  los que ya estaban se respetan.
- La copia de trabajo pasa a un **temporal del sistema**, no al repo.
- Se comprueba el sha256 del original antes y después y se imprime; si cambia,
  avisa en voz alta.

**Verificado:** el snapshot sale con el mismo sha `104dd2902aaf` y **sin sidecars**
al terminar. Dos pruebas nuevas lo cubren (base limpia y base con `-wal` vivo).

---

## D. Qué queda apuntado para las etapas siguientes

- **E3/E4 (léxico y dependencia de la base):** el mismo token inexistente abre
  ×1,05 de candidatos en el snapshot y ×5,3 en la viva. Es la primera medida
  concreta de que el daño del ruido **sí depende de la base**, no solo del largo
  de la consulta. Ahí hay trabajo para E4.
- **La reparación que Dennys tiene que decidir** (no ejecutada): quitar el castigo
  oculto del temático. Las dos opciones que se ven desde aquí, sin tocar el resto:
  1. que la compuerta no mire `sinonimos_ratio` (que un nodo con buen alias sea el
     que MÁS cobra, no el que no cobra); o
  2. dejar el temático sin compuerta y que el propio `tematico_score` gradúe
     (hoy sería igual, porque está saturado: primero habría que hacer que gradúe).
  La opción 1 es un cambio de una línea y la QA es el juez. **No se toca sin OK.**
- **El acantilado del bono de alias (0,95)** es un segundo candidato, más
  ambicioso: convertir ese umbral en una rampa. No se propone para esta entrega.

## Resumen para Dennys

1. El ruido no es un caso del examen: **cualquier palabra de más tira al recuerdo
   bueno**, sea inventada o real.
2. La causa es que **la cobertura de alias y el temático usan umbrales de todo o
   nada**, y un token los cruza en los dos sentidos.
3. El temático **vale lo mismo para todos** (1,0 exacto): no ordena, solo premia a
   los que pasan la compuerta y castiga al de mejor alias.
4. La QA ya **no deja basura** junto al snapshot.
