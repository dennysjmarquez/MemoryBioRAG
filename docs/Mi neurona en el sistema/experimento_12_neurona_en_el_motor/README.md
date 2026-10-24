# Experimento 12: la neurona asociativa entra al motor

> **En una frase:** cuando el motor crea una sinapsis, ahora **la neurona decide con qué fuerza
> nace**. El motor sigue decidiendo **qué** sinapsis se crean, igual que antes. No se crea ni se corta
> ninguna de más.

Viene del experimento 11 (la neurona cerrada, calibrada de fábrica) y de las cinco decisiones del
examen de Dennys (experimento 11, V2.17 y V2.18):

| Decisión del examen | Qué hace el motor v35 |
|---|---|
| 1. Cablear para poner el peso | ✅ La neurona pone el peso de nacimiento |
| 2. Cortar sinapsis: no, por ahora | ✅ No corta nada; nacen las mismas sinapsis |
| 3. Quitar a Gemini: todavía no | ✅ La hormiguita sigue igual |
| 4. Proponer conexiones: sí, con cuidado | ⏸️ Todavía no. Es el paso siguiente, por separado (Regla 13: un cambio a la vez) |
| 5. Capa de contradicción: no hace falta | ✅ No se agregó |

---

## 1. Qué cambió en el código

| Archivo | Cambio |
|---|---|
| `core/neurona_asociativa.py` | **Nuevo.** La neurona del experimento 11 dentro del motor |
| `core/sinapsis.py` | `auto_vincular` (sus 4 pasadas) y `vincular_por_sinonimos` piden el peso a la neurona |
| `tests/test_neurona_asociativa_motor.py` | **Nuevo.** 14 pruebas |

Son los dos puntos donde nacen las sinapsis cuando el agente guarda algo (herramienta `aprender`
del MCP y `biorag.py`), y también en la consolidación. Los demás puntos de nacimiento (sueño, DMN,
inferencia transitiva, ráfaga, aprendizaje léxico) **no se tocaron**.

### La fórmula (la misma del experimento 11, cerrada)

```
fuerza = 1 / (1 + e^-z)
z      = -1 + 2·parecido + 1·semantica + 1·rareza_max + 4·episodio + 1·etiquetas
peso   = 0.5 + 0.5·fuerza            ← siempre entre 0.5 y 1.0
```

**Por qué `0.5 + 0.5·fuerza`:**
- **Ninguna sinapsis nace por debajo de 0.5.** El motor usa 0.5 como filtro de asociaciones y poda
  por debajo de 0.05. Así ninguna conexión queda "cortada de hecho" por nacer débil: se respeta
  "nunca bajar el recall".
- **El orden lo pone la neurona.** La expansión por el grafo toma los 6 vecinos de mayor peso de
  cada recuerdo. Con la neurona, esos 6 son los que más tienen que ver.
- **Fuerza 0.6 → peso 0.80**, justo el umbral de "peso alto" del DMN. En el examen de Dennys, con
  fuerza ≥ 0.6, **13 de 14** sinapsis existentes eran buenas.

### Lo que NO cambia
- Qué sinapsis se crean: las reglas de siempre (Jaccard, nombre, sinónimos, PMI, cierre triádico, topes).
- Las sinapsis que ya existen: si una sinapsis ya estaba, se queda con el **mayor** de los dos pesos
  (`ON CONFLICT … MAX`). La neurona **nunca baja** una sinapsis existente.
- El ranking, la búsqueda, el agente y el MCP: ningún parámetro nuevo.
- La neurona no aprende: cerrada, como decidió Dennys.

### Capas que hubo que agregar (lo que le faltaba al motor)

| Capa | Por qué |
|---|---|
| **Estado de la neurona** en 2 tablas propias (`neurona_asociativa_estado`, `neurona_asociativa_raices`) | La neurona necesita saber qué palabras son raras en ESTA memoria (idf) y su espacio de significado (LSA). Se calcula solo la primera vez y se rehace cuando la memoria crece un 10 %. |
| **Plegado LSA** | Un recuerdo nuevo se proyecta al espacio de significado con los vectores guardados, sin recalcular nada. Para los recuerdos que ya estaban da exactamente lo mismo que el experimento. |
| **Techo de costo** | En memorias grandes, el estado se calcula sobre una muestra fija de 2,000 recuerdos. Cada decisión por par es tiempo constante. |
| **Índice `idx_lp_creado_en`** | Para encontrar en 1 consulta los recuerdos guardados cerca en el tiempo. |
| **Guardia de tiempo (7 días reales)** | Si vuelves después de 2 meses, tu primer recuerdo no "se vivió junto" con el último de hace 2 meses, aunque no haya nada en medio. En tu memoria, el 99 % de los pares a ≤ 10 recuerdos de distancia están a menos de 80 h: la guardia no cambia la fórmula calibrada en el uso normal. |
| **Apartarse si falla** | Cualquier error dentro de la neurona → el motor usa el peso a mano de siempre. Nunca rompe un guardado. |
| **Interruptor** | `BIORAG_NEURONA_ASOCIATIVA=0` la apaga: todo vuelve exactamente al peso a mano. |

---

## 2. ¿Es la misma neurona del experimento?

Sí. En los **100 pares del examen de Dennys**, la fuerza del motor y la del experimento difieren
como máximo **0.003** (media 0.0003). La prueba `test_fiel_al_experimento_11` lo verifica en 200
pares de una memoria sintética con diferencia ≤ 0.000001.

---

## 3. Mediciones

Todo sobre **copias** del snapshot `qa_escape_qcr_20260811.db` (sha256 `104dd290…`, sin cambios).
Ninguna DB real fue tocada.

### 3.1 QA oficial (921 consultas, `PYTHONHASHSEED=1`)

| | R@5 | R@1 | MRR | Falsos positivos | Gate |
|---|---|---|---|---|---|
| **Antes** (código anterior) | 100 % | 91.89 % | 0.950 | 0 % | OK |
| **Código nuevo**, snapshot intacto | 100 % | 91.89 % | 0.950 | 0 % | OK |
| **Código nuevo + las 13,114 sinapsis automáticas repesadas por la neurona** | 100 % | 91.89 % | 0.950 | 0 % | OK |

Los tres son **idénticos caso por caso** (mismos fallos, mismas métricas por categoría).
Salidas completas: `resultados/qa_antes.txt`, `resultados/qa_codigo_nuevo_snapshot_intacto.txt`,
`resultados/qa_todas_las_sinapsis_por_la_neurona.txt`.

**Lectura honesta:** el QA no se mueve ni siquiera cambiando el peso de **todas** las sinapsis
automáticas. Eso prueba que la neurona no daña la búsqueda. También dice que **el QA no ve el peso de
las sinapsis**: la expansión por el grafo actúa en 8 de 921 consultas. Para ver lo que la neurona
mejora, hay que mirar el grafo (3.2).

### 3.2 Calidad del grafo: los 6 vecinos que usa la expansión

`calidad_grafo.py` compara el snapshot con la copia repesada:

| De los 6 vecinos de mayor peso de cada recuerdo | Peso de hoy | Neurona |
|---|---|---|
| Pares que Dennys marcó **sí** | 11 de 29 | **14** de 29 |
| Pares que Dennys marcó **no** | 13 de 29 | **9** de 29 |
| **Enlaces manuales** de Dennys | 86 de 390 | **142** de 390 (+65 %) |
| AUC del peso (sí contra no, examen) | 0.628 | **0.738** |

Los enlaces manuales no se repesaron: suben porque, cuando el par también tiene una sinapsis
automática, la neurona le da fuerza alta.

### 3.3 Guardar 5 recuerdos nuevos (punta a punta)

`prueba_guardado.py` hace lo mismo que `aprender` del MCP, con la neurona apagada y encendida:

| Recuerdo nuevo | Mismas sinapsis | Sinónimos a mano | Sinónimos con neurona |
|---|---|---|---|
| neurona_asociativa_cableada_motor | ✅ 51 | todos 0.90 | 0.637–0.778 |
| qa_baseline_antes_cableado | ✅ 73 | todos 0.90 | 0.634–0.847 |
| hormiguita_gemini_cuarentena_revision | ✅ 37 | todos 0.90 | 0.697–0.830 |
| athena_identidad_reflexion_octubre | ✅ 213 | todos 0.90 | 0.634–0.841 |
| plugin_opencode_sesion_idle | ✅ 56 | todos 0.90 | 0.638–0.875 |

**Alcance:** con el peso a mano, un recuerdo nuevo se mete entre los 6 vecinos principales de casi
todos sus vecinos (400 de 430). Todos sus sinónimos nacen en 0.90 y, en el empate, gana la sinapsis
más nueva. Por eso cada recuerdo nuevo desplaza a los anteriores, tengan que ver o no. Con la
neurona entra solo donde tiene que ver: **101 de 430**. En el régimen completo (todo repesado) da lo
mismo (102 de 430), así que no es un efecto de mezclar pesos viejos y nuevos.

### 3.4 Velocidad

| | Tiempo |
|---|---|
| Decisión por par | ~0.3 ms (constante: no depende del tamaño de la memoria) |
| Construir el estado, memoria de Dennys (851 recuerdos) | 0.5 s, una vez, y luego cada vez que crece un 10 % |
| Construir el estado, memoria de 6,000 (techo de muestra 2,000) | 3.3 s, con el mismo techo para cualquier tamaño |
| Guardado típico (37–213 sinapsis) | +0.02 a +0.09 s |

### 3.5 Pruebas

| | Resultado |
|---|---|
| Suite completa antes | 408 passed (`resultados/pytest_antes.txt`) |
| Suite completa después | **422 passed** = 408 + 14 nuevas (`resultados/pytest_despues.txt`) |

Las 14 pruebas nuevas cubren:
- fidelidad al experimento;
- mismas sinapsis con la neurona encendida o apagada;
- rango y orden del peso;
- apagada = peso a mano idéntico;
- falla en las agujas → se aparta;
- falla en la construcción → se aparta;
- nunca baja una sinapsis existente;
- memoria mínima y memoria vacía;
- el estado se rehace solo al crecer y persiste entre procesos;
- techo de muestra;
- guardia de tiempo;
- velocidad.

---

## 4. Lo que falta, honesto

1. **Las sinapsis que ya existen siguen con el peso a mano.** La neurona solo pesa las que nacen desde
   ahora. `repesar_copia.py` repesa una **copia**. Hacerlo en tu DB viva es **decisión tuya**
   (Dennys). En la copia, el QA no cambia y el grafo mejora (3.1 y 3.2).
2. **Proponer conexiones nuevas** (decisión 4) es el paso siguiente, por separado.
3. **Gemini** sigue hasta que haya más evidencia (en el examen quedaron 6 a 7).
4. **El QA no puede medir esta mejora** porque no mira el peso de las sinapsis. Hace falta una
   categoría de QA de asociación, o el canal 2 de asociaciones, para medirla con consultas.

---

## 5. Reproducir

```bash
# 1. pruebas
python -m pytest -q tests/test_neurona_asociativa_motor.py

# 2. guardar 5 recuerdos (copias en /tmp/e12)
python "docs/Mi neurona en el sistema/experimento_12_neurona_en_el_motor/prueba_guardado.py" snapshots/qa_escape_qcr_20260811.db

# 3. repesar una copia y medir el grafo
python "docs/Mi neurona en el sistema/experimento_12_neurona_en_el_motor/repesar_copia.py" snapshots/qa_escape_qcr_20260811.db /tmp/repesada.db
cp snapshots/qa_escape_qcr_20260811.db /tmp/antes.db
python "docs/Mi neurona en el sistema/experimento_12_neurona_en_el_motor/calidad_grafo.py" /tmp/antes.db /tmp/repesada.db

# 4. QA sobre la copia repesada (unos 12 minutos)
BIORAG_PATH=/tmp/repesada.db PYTHONHASHSEED=1 BIORAG_QA_FAILED_CASES=/tmp/fallidos.jsonl \
  BIORAG_QA_METRICS=/tmp/metrics.json python scripts/evaluar_qa.py
```
