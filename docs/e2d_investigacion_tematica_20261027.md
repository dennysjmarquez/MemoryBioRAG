# E2d — ¿Qué mide de verdad la señal temática?

**Encargo:** medir la distribución de la media *antes* de multiplicar por 3;
comprobar si compara con la consulta o con los demás candidatos; proponer hasta
dos caminos, sin aplicar ninguno.

**Alcance:** investigación. No se cambian ni el motor ni la QA oficial ni los
casos. No se modifica `VERSION`, `README` ni `CHANGELOG`. La neurona está
apagada. El **0848 sigue siendo un fallo conocido en la viva**: esta entrega no
lo resuelve. La corrección de E2c continúa rechazada y revertida; sus hallazgos
del auditor están incorporados en [E2c](e2c_compuerta_tematica_20261027.md).

## 1. Bases y forma de medir

| | Snapshot oficial | Copia de la base viva |
|---|---|---|
| Recuerdos totales | 866 | 1.357 |
| Fuente | `snapshots/qa_escape_qcr_20260811.db` | `/tmp/viva_e2c.db` |
| SHA-256 de la fuente | `104dd2902aaf24c3ce93624492ea95a719acbdcca50f4f6bc123ac8317749796` | `a61913ce074cd02323c13589040b7ab1e5e4f36b18bbe62c12f9c1d363324e9a` |

La copia viva fue reconstruida del volcado de Drive del **26-10-2026**
`google_drive/backup_memory_biorag.sql` (82.419.781 bytes, MD5
`34650056ebcc04427ba3f9b494150026`): no se presenta como una conexión en
directo a la base actual. `/tmp/viva_e2c.db` es temporal; para reproducir habrá
que reconstruirla del volcado y comprobar su SHA. Las dos fuentes se leen en
solo lectura; la QA opera sobre su propia copia aislada. El snapshot no se abre
en escritura. Ambas fuentes estaban sin WAL al medirlas: `immutable=1` **no
incorpora un WAL** si existe.

La prueba es la **QA oficial completa de 921 casos** de
`scripts/casos_qa_baseline_v1.jsonl`, sin añadir `zzqx`, con `BIORAG_NEURONA=0`
y `BIORAG_QA_TEMATICO_CENSO=1`. El método y los casos de la QA no se han
cambiado. El censo adicional de
[`scripts/censo_tematico_e2d.py`](../scripts/censo_tematico_e2d.py) observa la
lista `sims` en la búsqueda, sin escribir en ella, y devuelve el resultado de la
fórmula original. No reconstruye el bucle del examen.

**Unidad de medida:** llamadas a la fórmula por candidato y consulta, no
candidatos únicos, ni consultas, ni pares únicos. Entran en la distribución
solo llamadas en las que la compuerta se ejecutó y hubo al menos un par con
similitud `> 0,02`. Las listas vacías se cuentan aparte, no como medias cero.
Cuando la compuerta no se ejecuta, `sims` puede conservar la lista del candidato
anterior: el censo **no la lee**. Se verifica en cada lectura que
`min(1.0, media * 3.0)` coincide exactamente con el `tematico_score` entregado
a la fórmula. Un error invalida la medición.

**Primer intento descartado:** el observador contó también 12 llamadas de la
huella de la fórmula que `neurona.resumen` calcula al iniciar, incluso con la
neurona apagada. Ocurren fuera de la búsqueda y antes del censo nativo de la QA;
no son candidatos. Por ello el primer censo del snapshot se marcó inválido,
aunque sus métricas coincidieron con E1c. El primer intento de la viva se
detuvo al conocerse el problema; su log es parcial, sin métricas finales. Se
comprobó el origen en el código y en una copia; se corrigió solo el observador
y se repitieron las QA. El observador corregido cuenta por separado únicamente
llamadas reconocidas de `huella_motor`; cualquier otra llamada externa o externa
dentro del censo de la QA invalida la corrida. Se conservan el intento inválido,
el log parcial y el [diff del observador](e2d_ajuste_observador_20261027.patch)
para auditoría.

Los porcentajes del histograma usan como denominador **las medias válidas**;
no se extrapolan a todos los recuerdos ni a otras bases. Un recuerdo repetido
en diferentes consultas puede aportar varias llamadas. Además, como la lista
excluye similitudes `<= 0,02`, es una media **condicionada**, no una media de
todos los pares posibles.

## 2. Resultado del censo sin ruido

| Recuento de llamadas | Snapshot | Copia viva |
|---|---:|---:|
| Llamadas a la fórmula **en búsqueda** | 224.938 | 426.253 |
| Compuerta no ejecutada, por cualquier condición | 78.979 | 130.644 |
| Compuerta ejecutada, lista vacía | 0 | 0 |
| **Compuerta ejecutada, con media válida** | **145.959** | **295.609** |
| Medias ≥ 1/3 y, por tanto, saturadas | **145.959/145.959: 100 %** | **295.609/295.609: 100 %** |
| Pares que pasaron `> 0,02`, sumados en esas listas | 2.188.815 | 4.433.848 |
| Llamadas de huella fuera de búsqueda, contadas aparte | 12 | 12 |
| Errores al comprobar media contra temático | 0 | 0 |

El censo nativo de la QA coincide en llamadas de búsqueda, medias y saturadas;
el desglose también suma exactamente el total. Las 12 llamadas de huella por
base no estaban dentro del censo nativo. «Compuerta no ejecutada» agrupa todas
las condiciones que la cierran: **no equivale** a decir que todas se cerraron
solo por alias.

### Distribución de la media antes del ×3

Percentiles por rango más próximo; cada columna tiene como denominador sus
**medias válidas** indicadas arriba. Valores redondeados a seis decimales:

| Medida | Snapshot | Copia viva |
|---|---:|---:|
| Mínimo | 0,524577 | 0,515633 |
| Media | 0,590271 | 0,588235 |
| P1 | 0,550669 | 0,551552 |
| P5 | 0,563738 | 0,566136 |
| P10 | 0,576775 | 0,571722 |
| P25 | 0,588633 | 0,581309 |
| **Mediana / P50** | **0,593391** | **0,592100** |
| P75 | 0,597115 | 0,597440 |
| P90 | 0,598543 | 0,600000 |
| P95 | 0,600000 | 0,600000 |
| P99 | 0,600000 | 0,600000 |
| Máximo | 0,600000 | 0,600000 |

Histograma resumido, sobre el mismo denominador:

| Intervalo de la media | Snapshot | Copia viva |
|---|---:|---:|
| `< 1/3` | 0 | 0 |
| `[1/3, 0,50)` | 0 | 0 |
| `[0,50, 0,60)` | **145.959: 100 %** | **295.609: 100 %** |
| `≥ 0,60` | 0 | 0 |

En ambos JSON se conserva el histograma completo de 12 intervalos. El máximo
real registrado fue `0.5999999999999999` en las dos corridas: se redondea a
0,600000 en la tabla, pero está por debajo de 0,60 en el histograma. La media
sí varía, aunque en un rango estrecho; el ×3 borra **todas esas diferencias**
en las llamadas medidas al entregar siempre 1,0. Esto no describe las llamadas
sin media ni garantiza el mismo porcentaje en cualquier base.

## 3. Control: ¿el observador movió la QA?

Comparación con E1c, sin ruido: antes → ahora con censo nativo y observador.
Coinciden el total de casos, el global clásico, **todas las categorías** y el
bloque completo de QA honesta guardados en las métricas E1c.

| Medida | Snapshot E1c → E2d | Copia viva E1c → E2d |
|---|---:|---:|
| Clásica R@5 | 100,00 → **100,00 %** | 99,20 → **99,20 %** |
| Clásica R@1 | 93,14 → **93,14 %** | 91,09 → **91,09 %** |
| Honesta R@5 | 100,00 → **100,00 %** (865) | 99,88 → **99,88 %** (861) |
| Honesta R@1 | 95,31 → **95,31 %** (853) | 93,53 → **93,53 %** (850) |
| `por_tema` honesta R@5 | 100,00 → **100,00 %** (65) | 98,46 → **98,46 %** (65) |
| Fallos honestos fuera del top-5 | 0 → **0** | 1 → **1** |
| Falsos positivos | 0/40 → **0/40** | 0/40 → **0/40** |

Ambas QA terminaron con gate clásico `OK`, cero errores de observación y
`valido: true`. Sus archivos de fallos contienen también los controles de
consultas ambiguas: 2 registros en el snapshot y 11 en la viva; en esta última
son **7 fallos clásicos + 4 ambiguos**, no 11 fallos del recall clásico.

En el snapshot, el censo nativo contó **224.944 llamadas y 145.958 medias** en
el intento inválido, frente a **224.938 y 145.959** en el corregido. Las
métricas de QA y los archivos completos de fallos fueron idénticos. **La causa
de la pequeña diferencia de llamadas no está identificada**: no se atribuye ni
se descarta la instrumentación. No se fijó `PYTHONHASHSEED`, así
que el comando reproduce el procedimiento, no promete idénticos conteos bit a
bit; se conservan ambos registros.

La igualdad de métricas y de las clasificaciones que E1c guardó es necesaria
para confiar en esta medición, pero **no demuestra que el top-5 de cada consulta
sea idéntico**: E1c no guardó todos los rankings individuales. Como control
adicional reproducible, [`diagnostico_0848_e2d.py`](../scripts/diagnostico_0848_e2d.py)
comparó cuatro consultas del 0848 sobre dos copias frescas del snapshot: sus
top-5, scores y totales coincidieron sin y con observador. Es un control
acotado, no una prueba de igualdad de los 921 rankings.

En ese control, con `849 + zzqx`, la cobertura bajó a 0,475 y la media de las
15 parejas admitidas fue 0,593972: el temático llegó a 1,0 y el esperado al
1.º. Con solo `zzqx` y sin `849`, la cobertura fue 0,6333 y la compuerta quedó
cerrada. Esa consulta salió fuera del top-5 **al pedir 5**; E2b la midió 4.ª
**al pedir 50**, que no equivale a pedir 5. La
[salida literal del control](e2d_control_0848_20261027.log) distingue ambas.

Pruebas completas en una copia aislada del código, con el observador corregido
y sus pruebas: `550 passed in 187.10s (0:03:07)`. Para esas pruebas generales no
se exportó `BIORAG_NEURONA=0`, porque también prueban la neurona. La
[salida literal](e2d_pytest_corregido_20261027.log) está conservada.

## 4. Qué significa realmente «temático»

En [`core/memory/search.py`](../core/memory/search.py), por cada candidato con
la compuerta abierta:

1. Toma otros candidatos de **`todos[:15]`**, sin incluirse a sí mismo. Son los
   primeros candidatos reunidos **antes** del orden híbrido, no necesariamente
   los 15 mejores finales.
2. Calcula la similitud de dimensiones entre cada par y conserva solo valores
   mayores que `0,02`.
3. Si hay valores, calcula su media y entrega `min(1.0, media * 3.0)`.

**Respuesta:** esta señal mide parecido entre un candidato y otros candidatos,
**no una comparación directa con la consulta**. La consulta sí influye
indirectamente en qué candidatos se reúnen y en si se abre la compuerta. No hay
que confundir esta señal temática con la señal independiente `grupo_score`.

La similitud de cada par, en [`core/tematica.py`](../core/tematica.py), combina
`0,4 × presencia + 0,6 × ausencia ponderada`. La presencia compara dimensiones
compartidas. La ausencia compara dimensiones que faltan en ambos y usa pesos
calculados a partir de la base. Aunque un comentario la llama «Jaccard», el
código divide la intersección ponderada por el **promedio de las dos sumas**;
con pesos no negativos esa expresión corresponde a una forma ponderada de
Dice, no al Jaccard de intersección sobre unión. El nombre no cambia el cálculo.

### Una comprobación sin ranking: dos recuerdos sin dimensiones

En lectura inmutable, conté **89/851** recuerdos activos sin asignaciones de
dimensión en el snapshot y **196/1.195** en la copia viva. Elegí dos de ellos
en cada base y ejecuté solo la función existente de similitud, sin búsqueda:

```text
snapshot similitud_dos_sin_dimensiones= 0.6 con_x3= 1.0
viva similitud_dos_sin_dimensiones= 0.6 con_x3= 1.0
```

No es evidencia de que esos dos recuerdos causen un fallo de la QA. Sí muestra
un riesgo de la definición: dos perfiles vacíos pueden parecerse `0,6` por
compartir ausencias, sin una sola dimensión presente compartida. Si fuesen la
única pareja admitida, el ×3 convertiría esa media en `1,0`.

La cuenta se reproduce en ambas fuentes con este fragmento, **solo si no tienen
WAL pendiente**:

```python
from pathlib import Path
from types import SimpleNamespace
import sqlite3
from core.tematica import calcular_idf_dims, calcular_perfiles_presencia, similitud_tematica

for nombre, ruta in [("snapshot", Path("snapshots/qa_escape_qcr_20260811.db").resolve()),
                     ("viva", Path("/tmp/viva_e2c.db"))]:
    con = sqlite3.connect(ruta.as_uri() + "?mode=ro&immutable=1", uri=True)
    activos, vacios = con.execute("""SELECT COUNT(*), SUM(CASE WHEN NOT EXISTS
        (SELECT 1 FROM largo_plazo_dimensiones d WHERE d.concepto=l.concepto)
        THEN 1 ELSE 0 END) FROM largo_plazo l WHERE estado='activo'""").fetchone()
    a, b = [r[0] for r in con.execute("""SELECT concepto FROM largo_plazo l
        WHERE l.estado='activo' AND NOT EXISTS (SELECT 1 FROM largo_plazo_dimensiones d
        WHERE d.concepto=l.concepto) ORDER BY concepto LIMIT 2""")]
    lector = SimpleNamespace(cursor=con.cursor())
    perfiles = calcular_perfiles_presencia(lector)
    idf = calcular_idf_dims(lector)
    sim = similitud_tematica(a, b, lector, perfiles, idf)
    print(nombre, vacios, activos, sim, min(1.0, sim * 3.0))
    con.close()
```

### Dependencia de la base

El peso de cada dimensión usa `log(N / n)`: `N` es el número de recuerdos
**activos**, mientras que `n` cuenta asignaciones de esa dimensión sin filtrar
por estado. Se observaron **cero pesos negativos** en las dos fuentes medidas;
en otra base podría haberlos si `n > N`. No se ha probado aquí que eso ocurra
fuera de estas fuentes.

El motor guarda perfiles y pesos en caché; no los recalcula para cada
candidato. Al cargar o invalidar esa caché, el valor puede variar con la
composición de la base, tanto por esos pesos como por los candidatos reunidos.
Quitar el ×3 no vuelve a esta señal invariante al tamaño o composición de la
base. Tampoco convierte la comparación entre candidatos en una comparación
directa con la consulta.

Hay un contraejemplo matemático, **no una medición de la QA**: supongamos seis
dimensiones con frecuencias `[5, 10, 15, 25, 40, 70]`, dos candidatos con
dimensiones `{1, 2}` y `{1, 3, 4}`, y que esta sea la única pareja admitida.
Con `N=100`, el par da **0,287847** y el temático `0,863541`. Si se añaden
100 recuerdos activos sin dimensiones, de modo que `N=200` y las frecuencias y
los dos candidatos no cambian, el par da **0,345773** y el temático **1,0**.
Suponiendo la misma compuerta abierta y los mismos candidatos, la fórmula ya
varía por el tamaño de la base. El ejemplo no afirma que eso explique un caso
concreto de la QA. Se reproduce sin base ni escritura:

```python
import math
from core.tematica import similitud_tematica
perfiles = {"a": {1, 2}, "b": {1, 3, 4}}
frecuencias = {1: 5, 2: 10, 3: 15, 4: 25, 5: 40, 6: 70}
for N in (100, 200):
    idf = {d: math.log(N / n) for d, n in frecuencias.items()}
    par = similitud_tematica("a", "b", None, perfiles, idf)
    print(N, par, min(1.0, par * 3.0))
```

## 5. Dos caminos para discutir — ninguno aplicado

### A. Recuperar la graduación de la media existente

Idea mínima: conservar la compuerta y sustituir el ×3 por la propia media,
limitada a 1: `min(1.0, media)`. No se tocaría el peso manual ni la neurona.

**A favor:** devolvería diferencias entre medias que hoy quedan todas en 1.
**En contra:** los valores observados seguirían comprimidos aproximadamente entre
0,516 y 0,600; cambia la escala del aporte, puede bajar el recall, conserva el
sesgo de ausencias y la comparación con los vecinos, y **no cumple por sí sola
la invariancia al corpus**. Mantener la compuerta también deja pendiente el
problema del 0848. Es una posible prueba aislada, no una solución aprobada.

### B. Medir directamente la consulta frente al candidato

Idea estructural, simbólica y sin modelos embebidos: si `Q` es el conjunto de
dimensiones que expresa la consulta y `C` las presentes en el candidato, usar
por ejemplo `|Q ∩ C| / |Q|`, o 0 si `Q` está vacío. Con `Q` y `C` fijos, esa
fórmula no necesita contar el corpus ni mirar a los otros candidatos; un perfil
vacío no gana por ausencias compartidas.

**No está lista para aplicar:** hay que definir cómo obtener `Q` desde las
palabras sin hacerlo depender de los resultados. La inferencia actual en
`search.py` toma dimensiones de los primeros resultados FTS, y reutilizarla
mantendría esa dependencia. Podría no detectar dimensiones, perder sinonimia o
empeorar la QA. Con la compuerta actual, 0848 podría seguir bloqueado. Es una
alternativa de diseño, no un resultado medido ni una garantía de ranking.

No se han experimentado estas reparaciones. **Una sola decisión y un solo
cambio por entrega**, si Dennys lo autoriza. Para cualquier candidato: volver a
las cuatro QA oficiales, snapshot y viva, con y sin `zzqx`, neurona apagada;
comparar R@5 honesta por categoría, R@1 honesta global y FP 0/40, sin bajadas,
y ejecutar las pruebas. La meta completa sigue incluyendo H_mitad, H_todos y
EXP-Q 3/3 en el top-5; esta investigación no la da por alcanzada.

## 6. Cómo reproducir y evidencias

Entorno medido: Python **3.11.2**, SQLite **3.40.1**, numpy **2.4.6** y pytest
**9.1.1**. El motor y la QA de referencia son los de `1339cfb`. El lanzador
exige una ruta nueva de métricas; conviene usar también rutas nuevas para el
censo y los fallos para no sobrescribir resultados anteriores. Ejemplo para el
snapshot, desde la raíz y con las dependencias del proyecto:

```bash
BIORAG_PATH="$PWD/snapshots/qa_escape_qcr_20260811.db" \
BIORAG_NEURONA=0 BIORAG_QA_RUIDO='' BIORAG_QA_TEMATICO_CENSO=1 \
BIORAG_QA_METRICS=/tmp/e2d-qa-snapshot.json \
BIORAG_QA_FAILED_CASES=/tmp/e2d-fallos-snapshot.jsonl \
python -u scripts/censo_tematico_e2d.py \
  --baseline docs/e1c_qa_honesta_snapshot_20261026.json \
  --salida /tmp/e2d-censo-snapshot.json
```

Para la viva, sustituir `BIORAG_PATH` por la copia reconstruida, la baseline por
`docs/e1c_qa_honesta_viva_20261026.json` y usar otras rutas de salida. La
comparación de baseline y censo debe quedar en `true` y el resumen en
`"valido": true`. Los logs conservan la salida literal del arnés.

| Evidencia | Snapshot | Copia viva |
|---|---|---|
| Distribución y validaciones | [censo JSON](e2d_censo_snapshot_20261027.json) | [censo JSON](e2d_censo_viva_corregida_20261027.json) |
| Salida literal QA | [log](e2d_qa_snapshot_20261027.log) | [log](e2d_qa_viva_corregida_20261027.log) |
| Métricas completas | [JSON](e2d_qa_snapshot_20261027.json) | [JSON](e2d_qa_viva_corregida_20261027.json) |
| Fallos, incluidos ambiguos | [JSONL](e2d_fallos_snapshot_20261027.jsonl) | [JSONL](e2d_fallos_viva_corregida_20261027.jsonl) |
| Referencia E1c | [JSON](e1c_qa_honesta_snapshot_20261026.json) | [JSON](e1c_qa_honesta_viva_20261026.json) |

Otros archivos: [control del 0848](e2d_control_0848_20261027.log),
[pytest corregido](e2d_pytest_corregido_20261027.log),
[pytest inicial](e2d_pytest_20261027.log),
[censo inicial inválido](e2d_censo_invalido_snapshot_20261027.json),
[métricas iniciales](e2d_qa_invalida_snapshot_20261027.json),
[log inicial](e2d_qa_invalida_snapshot_20261027.log),
[fallos iniciales](e2d_fallos_invalida_snapshot_20261027.jsonl),
[log parcial de la viva interrumpida](e2d_qa_invalida_viva_parcial_20261027.log)
y [diff de la corrección del observador](e2d_ajuste_observador_20261027.patch).
El JSON y el log inválidos conservan la ruta literal que usaron al ejecutarse:
la salida de ese intento fue renombrada a `*_invalida_*` antes de repetirla;
la ruta normal contiene ahora la corrida corregida.

Las huellas SHA-256 de fuentes, código, baselines y archivos de evidencia están
en [`e2d_sha256_20261027.txt`](e2d_sha256_20261027.txt).
