# Experimento 13 — Los enlaces del agente, el "ruido" y dónde va la neurona

**Fecha:** 2026-10-24 · **Rama:** `arena/8b932aae-memorybiorag` · **Base:** copia del snapshot `qa_escape_qcr_20260811.db` (sha256 `104dd290…`, intacto)

Dennys pidió (resumen de sus palabras):

1. Quitar las sugerencias del MCP que le dicen al agente "vincula esto con X": a los modelos pequeños los llevan a enlazar mal.
2. Investigar cómo nacen hoy las sinapsis de fondo (sinónimos, palabras).
3. Los enlaces que hace el agente con `vincular_con` (después de `busqueda_previa`) son perfectos: **nunca deben borrarse**.
4. El agente ve los resultados a través de las sinapsis que crea el "ruido" mecánico. ¿Ayuda o estorba? Ordenar las piezas.
5. Usar mejor la neurona.
6. "No decidas por decidir. Decide con pruebas en mano, código en mano."

Todo lo de abajo está medido en copias. Ninguna base real se tocó.

---

## 1. Lo que encontré en el código

### 1.1 Los enlaces del agente

`vincular_con` (en `aprender`) y la herramienta `vincular` llaman a `establecer_asociacion`, que crea una sinapsis de **tipo `manual`, peso 0.5**. Las dos vías dejan el mismo tipo; los `manual_v7` son vínculos manuales de versiones viejas.

**Antes de este cambio no estaban protegidos.** En los datos de Dennys:

| Qué los dañaba | Dónde en el código | Prueba en los datos |
|---|---|---|
| Desgaste de consolidación: −5 % por ciclo si no se usan en 7 días | `consolidation.py` (2b) | 18 ya se habían usado: 9 bajaron de 0.5 y 4 de 0.2 |
| Poda por debajo de 0.05 | `consolidation.py`, `dmn_engine.podar_ltd_guiado` | Era el destino de los anteriores |
| Hormiguita (Gemini) | `dmn_reflexion.py` (cuarentena, borrar, re-pesar) | Borró 11 `manual` y 4 `manual_v7`; 10 nunca volvieron |
| Avisos "desvinculá a↔b" en `recordar` | `mcp_server/search.py` | No miraban el tipo: podían señalar un enlace del agente |

Cuándo nacieron los 382 pares manuales (estimado por la hora):

| Momento | Pares | Lectura |
|---|---|---|
| ≤ 10 s después de crear uno de los nodos | 251 | casi seguro `vincular_con` |
| ≤ 10 min después | 108 | probablemente `vincular` tras una sugerencia |
| Más tarde | 23 | `vincular` a propósito |

### 1.2 Las sugerencias

`write.py` buscaba nodos con `concepto LIKE '%palabra%'`, sin orden, y le proponía 3 al agente ("¿tiene relación con estos nodos? Si sí, vinculalos"). Con nombres que llevan "dennys" o "biorag", eso es casi al azar. Encima, la descripción de `aprender` decía **"VIOLACIÓN CRÍTICA — NO GUARDAR SIN VINCULAR"** y el prompt lo repetía 3 veces. Un modelo pequeño obedece.

### 1.3 Cómo llegan las sinapsis al agente

- **Ranking (canal 1):** la evocación en cadena y la expansión de vecinos usan las sinapsis para traer resultados.
- **Asociaciones enriquecidas (canal 2):** 5 vecinos junto a cada resultado. Primero los `manual`; luego el resto por tipo y peso ≥ 0.5, con un máximo de 2 sinónimos. Este campo **no toca el ranking**.

En los 851 nodos activos de Dennys, de los 3,173 huecos que el agente ve en el canal 2:

| Tipo | Huecos | % |
|---|---|---|
| sinonimo_explicito | 1,356 | 42.7 |
| manual (agente) | 685 | 21.6 |
| co_semantica | 488 | 15.4 |
| co_ocurrencia | 356 | 11.2 |
| co_nombre | 148 | 4.7 |
| pmi_hebbiano | 118 | 3.7 |
| otros | 22 | 0.7 |

De los pares del examen a mano de Dennys que el agente llega a ver en el canal 2: **5 buenos y 8 malos**.

---

## 2. Cambios hechos al motor (aislados, con tests)

### Cambio 1 — `0182ad4` · Fuera las sugerencias de vincular y desvincular
- `write.py`: fuera el aviso `sinapsis=0`, las sugerencias por `LIKE` y el bloque "VIOLACIÓN CRÍTICA".
- `prompt.py`: fuera las 3 órdenes "vincular() ANTES de consolidar" y la regla que dependía de los avisos de desvincular.
- `search.py`: fuera los avisos "desvinculá con biorag_desvincular(a, b)" y su función auxiliar.
- **Se quedan** las herramientas `vincular` y `desvincular` (por si el agente las necesita). **`vincular_con` no se toca.**
- Test: `tests/test_sin_sugerencias_de_enlace.py` (4). Con el código viejo fallan 2.

### Cambio 2 — `8c7d476` · Los enlaces del agente son intocables para lo automático
- Constante única `TIPOS_SINAPSIS_AGENTE = ("manual", "manual_v7")` en `core/memory/constants.py`.
- Consolidación: fuera del desgaste y de la poda < 0.05.
- LTD guiado: fuera de candidatos.
- Hormiguita: el prefiltro no los manda a Gemini; cuarentena, borrar y re-pesar se niegan (formato viejo y nuevo).
- El agente **sí** puede quitarlos a propósito con `desvincular`.
- Test: `tests/test_enlaces_del_agente_intocables.py` (9). Con el código viejo fallan 8.

**Tests:** 421 → 434, todos pasan. **QA tras los dos cambios: idéntico al de antes** (`resultados/qa_antes.txt` vs `resultados/qa_tras_cambios_1_y_2.txt`):

```
GLOBAL SUMMARY (Retrieval) | 875    |  100.00% |   91.89% |  0.950 | 0
GLOBAL SUMMARY (Noise/FP) | 40     | N/A       | N/A       | N/A      | 0          (0.00% FP sobre 40 válidos; 0 contaminados)
[GATE] OK — métricas dentro de los umbrales de la baseline oficial
```

Lo que **no** hice: no subí el peso de los enlaces del agente (0.5) ni restauré los que ya se habían gastado. Eso cambia el ranking y pide su propia medición.

---

## 3. El "ruido": ¿ayuda o estorba? (simulación en copias, `PYTHONHASHSEED=1`)

`preparar_copias.py` arma las copias. "La neurona decide al nacer" se simula así: de todos los pares que propusieron las 5 reglas (los vivos más los que la hormiguita mandó a cuarentena), quedan solo los que la neurona juzga con fuerza ≥ umbral.

| Escenario | Enlaces automáticos | R@5 | R@1 | MRR | Fallos | Examen de Dennys: quedan sí / no |
|---|---|---|---|---|---|---|
| **Hoy** (hormiguita prendida) | 13,114 | 100.00 % | 91.89 % | 0.950 | 0 | 26 / 29 |
| **Hormiguita apagada** (todo lo cortado vuelve) | 15,864 | **100.00 %** | **92.00 %** | **0.951** | 0 | 30 / 36 |
| Neurona decide al nacer, ≥ 0.40 | 10,261 | 99.89 % | 91.77 % | 0.949 | 1 | 27 / 28 |
| Neurona decide al nacer, ≥ 0.50 | 3,847 | 99.66 % | 91.77 % | 0.948 | 3 | 18 / 11 |
| Neurona decide al nacer, ≥ 0.60 | 1,684 | 99.43 % | 91.66 % | 0.947 | 5 | 15 / 8 |
| Sin ningún enlace automático | 0 | 99.43 % | 91.77 % | 0.948 | 5 | 0 / 0 |

Los fallos que aparecen al cortar: `denys-identidad-profunda` (typo), `real más sistemas` y `semánticas 849 embedding` (por_tema), `memorias v5 1s optimizaciones` (variante), `regla` y `memoria compartida` (sinónimo).

**Lo que dicen las pruebas:**

1. **El ruido sí sirve para buscar.** Sin él se pierden 5 de 875 búsquedas. Su peso no importa (exp 12: repesar todo dejó el QA igual); lo que importa es que exista.
2. **Cualquier corte al nacer baja el recall**, incluso con umbral 0.40. Eso choca con la regla de Dennys de que el recall nunca baje. Por eso, "la neurona decide al nacer cortando" **no pasa la prueba**.
3. **Apagar la hormiguita mejora el QA** (R@1 +0.11, MRR +0.001, por_tema 63.08 → 64.62). Además se equivoca a menudo: de 11 cortes suyos que Dennys juzgó, 4 eran buenos. Su propia alarma restauró 2,681 de los 6,870 cortes.
4. **Donde el ruido sí estorba es en lo que el agente ve** (canal 2): 5 buenos y 8 malos.

## 4. Medida extra: la neurona filtra lo que ve el agente (canal 2)

Se calculó sobre la copia sin tocar el motor. Los enlaces del agente se muestran siempre; los automáticos solo si la neurona les da fuerza ≥ umbral. El canal 2 **no toca el ranking**, así que el recall no puede moverse.

| Canal 2 | Huecos | Automáticos | Del agente | Nodos sin vecinos que mostrar | Examen de Dennys visibles: sí / no |
|---|---|---|---|---|---|
| Hoy | 3,173 | 2,466 | 691 | 22 | 5 / 8 |
| Neurona ≥ 0.50 | 2,588 | 1,876 | 694 | 103 | **9 / 1** |
| Neurona ≥ 0.60 | 2,024 | 1,303 | 698 | 225 | 10 / 1 |

Con la neurona, los huecos que deja el ruido se llenan con enlaces mejores. Así aparecen más pares buenos y desaparecen los malos.

**Límites, sin adornos:**
- Solo 10–13 pares del examen caen en el canal 2. Es una muestra chica.
- Parte del examen se armó en grupos según la fuerza de la neurona, lo que puede favorecerla.
- Con ≥ 0.50, 81 nodos más se quedan sin vecinos que mostrar.

## 5. Cómo reproducir

```bash
# 1. copias (nunca toca el snapshot)
python preparar_copias.py ../../../snapshots/qa_escape_qcr_20260811.db /tmp/e13
# 2. mediciones de solo lectura
python medir.py ../../../snapshots/qa_escape_qcr_20260811.db /tmp/e13/fuerzas.json
# 3. QA de cada copia (≈ 12 min cada una, de a una)
for n in sin_auto h_apagada_todo neurona_040 neurona_050 neurona_060; do
  BIORAG_PATH=/tmp/e13/$n.db PYTHONHASHSEED=1 python scripts/evaluar_qa.py > qa_$n.txt
done
```

Nota: en las copias no se reconstruye el índice SDM (igual en todas). La dependencia real del ruido podría ser algo mayor que 5 búsquedas.

## 6. Archivos

- `preparar_copias.py`: arma las copias y `fuerzas.json`.
- `medir.py`: mide los enlaces del agente, la hormiguita, el canal 2 y el examen por umbral → `resultados/mediciones.json`.
- `resultados/qa_*.txt`: salida literal de cada QA.
