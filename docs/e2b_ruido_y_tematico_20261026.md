# E2b — tolerancia al ruido, temático saturado y limpieza de la QA

**Encargo del auditor:** A) medir R@5 y R@1 con una palabra inexistente añadida a
cada caso de la QA, en snapshot y viva, y desglosar el 0848. B) confirmar la
saturación del temático en la viva. C) que la QA del snapshot corra sobre una copia
temporal. **Sin reparar el ranking.**

**Regla cumplida:** cero código del motor. Todo sobre copias. `casos_qa.jsonl` no
se ha tocado.

**Revisión del auditor (27-10-2026): APROBADO CON CAMBIOS.** Esta actualización
corrige solo el informe; no cambia la QA ni el motor.

---

## 0. Antes de los números: dos intentos descartados

Mi primer intento fue copiar el bucle del arnés en un script propio. La copia daba
un baseline peor que el arnés (R@5 clásica 98,3 frente a 100,0 en el snapshot).
**Causa: mi copia no devolvía al estado inicial los 64 nodos que la QA despierta
entre caso y caso.** Una copia del arnés no es el arnés; esos números no se publican.
La medición de abajo sale del **arnés oficial** con una bandera nueva, así que las
condiciones son las de siempre: mismas restauraciones, misma resolución de
etiquetas, mismo trato de las ambiguas.

También descarté un segundo intento: instrumentar `_calcular_score_hibrido` para
ver las señales de cada candidato. En esa prueba el esperado salió 6.º en vez de
1.º. **Causa no identificada; script descartado** y sus cifras no se usan. No se
puede concluir que envolver la fórmula, por sí solo, cambie el resultado: el
auditor comprobó que el envoltorio usado para el censo **no cambia la QA**.
Las cifras publicadas proceden de la API pública o del arnés oficial; el censo de
este último sí envuelve la fórmula y devuelve su mismo valor.

Banderas añadidas, **apagadas por defecto**:
- `BIORAG_QA_RUIDO=zzqx` — añade esa palabra **solo a la búsqueda**; `query` queda
  intacta para el control de ambiguas y para los informes.
- `BIORAG_QA_TEMATICO_CENSO=1` — cuenta llamadas a la fórmula y saturación sin
  cambiar el valor devuelto.

---

## A. Tolerancia al ruido

QA oficial completa (921 casos, `BIORAG_NEURONA=0`), normal contra
`BIORAG_QA_RUIDO=zzqx`. Las dos corridas **con ruido**, snapshot y viva, llevaron
además el censo temático activo; las de referencia sin ruido no lo llevaban.

El auditor comparó en el **snapshot con ruido** el censo activo y apagado:
obtuvo las mismas métricas y los mismos **32 registros de fallos**. Son los
**28** del resumen clásico de la tabla más **4 ambiguos**, que la QA muestra
aparte y excluye del recall global. No son 32 fallos del recall clásico.

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
snapshot; −3,89 y −5,38 en la viva. En estos controles **los falsos positivos no
se mueven**: 0/40 en las cuatro corridas.

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

1. **No hace falta que la palabra sea inventada.** Con `julio`, que existe en el
   corpus, el esperado también cae (puesto 5 en el snapshot). Eso no demuestra
   que ocurra con cualquier palabra adicional.
2. **La caída observada es grande.** De 0,6143 a 0,3860: −0,228 de golpe (−37 %)
   por una palabra de ruido. Un nodo que gana por 0,065 pasa a perder.
3. **La consulta limpia gana rozando el límite del premio.** En el alias del
   esperado, `semánticas` frente a `semántica` coincide con 0,90 y `embedding`
   con 1,00: **(0,90 + 1,00) / 2 = 0,95**, no 2/2 = 1,00. Con `zzqx`, la
   cobertura baja a **0,6333**. Lo comprobé con la función simbólica y el alias
   del snapshot abierto en lectura inmutable.
   - `sinonimos_ratio >= 0.95` → **bono en espacio logit**
     (`core/memory/scoring.py:377-386`). La consulta limpia lo alcanza justo; con
     0,6333 el bono **desaparece entero**. No se ha aislado cuánto de la caída
     total del score corresponde al bono y cuánto a otras señales.
   - `sinonimos_ratio < 0.5` → **compuerta del temático**
     (`core/memory/search.py:1749`). Tanto 0,95 como 0,6333 quedan fuera: para
     este nodo el temático ya estaba apagado en la consulta limpia y sigue apagado
     con ruido. **El ruido no cruza esa segunda compuerta.** El trato desigual
     frente a otros candidatos que sí pueden cobrarlo sigue existiendo.
4. **La consulta corta es frágil en este ejemplo.** La de cuatro palabras
   (`limpieza semántica tabla embedding`) también queda en el puesto 1, pero usa
   otras palabras: no aísla el efecto del largo. Su score es 0,8394; no es una
   cobertura de 0,84. Su cobertura simbólica de alias en el snapshot es 1,00.
5. **El daño observado sí cambia según la base** (material para E4): con la misma
   palabra inventada, los candidatos pasan de 122 a 128 en el snapshot (**×1,05**)
   y de 129 a **683** en la viva (**×5,3**). Son 554 candidatos más en la viva.
   Esto compara bases distintas; no demuestra que el tamaño, por sí solo, sea la
   causa. `zzqx` sola devuelve 0 candidatos en las dos bases: el efecto aparece
   al mezclarla con palabras que sí existen.

### A3. Qué se observa entre el esperado y el rival del 0848

| | gana | esperado |
|---|---|---|
| consulta limpia (snapshot) | — | **0,6143, puesto 1**, 0,065 por encima del segundo |
| con una palabra de más | 0,4006 | **0,3860, puesto 4**, en un pelotón de 0,38–0,40 |

En la consulta limpia el esperado gana y recibe el bono de alias; con ruido el
bono deja de aplicar y queda dentro del pelotón. El temático está apagado para
él en **ambas** consultas. Puede favorecer a rivales que pasen la compuerta, pero
el censo global no mide cuánto aportó cada señal a este cambio de puesto.

---

## B. El temático está saturado

Censo medido dentro de la QA oficial (`BIORAG_QA_TEMATICO_CENSO=1`). Aunque el
log dice «candidatos puntuados», el contador suma **llamadas a la fórmula**: un
mismo candidato puede aparecer varias veces. No son candidatos únicos.

| base | llamadas a la fórmula | llamadas con temático positivo | de ellas, temático **exactamente 1,0** | temático 0 y `sinonimos_ratio >= 0.5` |
|---|---:|---:|---:|---:|
| snapshot | 293.768 | 204.781 | **204.781 (100,00 %)** | 2.544 |
| viva | 773.259 | 559.586 | **559.586 (100,00 %)** | 3.201 |

Medido en las corridas **con** ruido: el número de llamadas en la viva es unas
2,6 veces el del snapshot. La última columna cuenta llamadas con esas dos
condiciones; por sí sola no demuestra que la compuerta de alias sea la única
razón de cada cero.

Como referencia, en su censo del snapshot **sin ruido**, el auditor informó
145.744 candidatos con temático positivo, todos a 1,0, y 5.442 con
`sinonimos_ratio >= 0.5`. Su punto de conteo es distinto: los totales no se
comparan como si midieran lo mismo. En ambos censos, el **100 % de las señales
positivas medidas** está saturado.

En estas corridas la señal no gradúa entre quienes la cobran. El peso nominal es
0,08 en la suma antes de normalizar; eso **no equivale necesariamente a +0,08**
en el score final. La compuerta excluye a los nodos con `sinonimos_ratio >= 0.5`.

La señal saturada no distingue el grado de parecido entre quienes la cobran, pero
sí puede cambiar el orden al premiar a unos y excluir a otros.

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
  1. que la compuerta no mire `sinonimos_ratio` (que un nodo con buen alias pueda
     cobrar la señal si cumple las demás condiciones); o
  2. dejar el temático sin compuerta y que el propio `tematico_score` gradúe
     (hoy sería igual, porque está saturado: primero habría que hacer que gradúe).
  La opción 1 es un cambio de una línea y la QA es el juez. **No se toca sin OK.**
- **El acantilado del bono de alias (0,95)** es un segundo candidato, más
  ambicioso: convertir ese umbral en una rampa. No se propone para esta entrega.

## E. Aclaración: 540 frente a 542 pruebas

Informé **540** pruebas en verde; el auditor obtuvo **542** en el commit
`789a70d`. Para comprobarlo repetí la suite sobre una copia aislada de ese commit,
con las dependencias fijadas, Python 3.11.2 y pytest 9.1.1, sin activar
`BIORAG_NEURONA=0`:

```text
/tmp/biorag-e2b-venv/bin/python -m pytest tests -q -rs
542 passed in 101.29s (0:01:41)
```

La cifra comprobada es **542 aprobadas**. No tengo el registro de la corrida en
que informé 540, así que la causa de la diferencia queda **sin identificar**.
Esta repetición no es una nueva corrida de la QA de 921 casos.

## Resumen para Dennys

1. Una palabra adicional **puede** bajar al recuerdo bueno; ocurre tanto con el
   ruido inventado probado como con `julio`.
2. El esperado limpio tiene alias **0,95 justo** y recibe el premio; con `zzqx`
   baja a 0,6333 y lo pierde. El temático ya estaba apagado en ambos casos.
3. En las dos corridas con ruido, todas las **llamadas con temático positivo**
   recibieron 1,0; el censo cuenta llamadas, no candidatos únicos.
4. La QA ya **no deja basura** junto al snapshot. El auditor confirmó que el
   censo no cambió la QA del snapshot.
5. **542 pruebas aprobadas**, verificadas sobre una copia de `789a70d`. El
   temático sigue sin tocarse hasta el OK de Dennys.
