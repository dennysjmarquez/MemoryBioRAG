# Experimento 15: resultados

- **Fecha:** 2026-11-25.
- **Protocolo:** [`PROTOCOLO.md`](PROTOCOLO.md), subido **antes** de medir (commit `5c6151c`).
- **Script:** [`simular.py`](simular.py). **Salidas:** `resultados/` (solo totales; la QA, sobre el snapshot
  público).
- **Lo que no se tocó:** el motor, los tests y la DB viva (solo se leyó en modo solo lectura para copiarla; su
  sha256 fue el mismo antes y después). El snapshot sigue con sha256 `104dd2902aaf`.
- **Decisión vigente (sin cambios):** la neurona solo ordena el canal 2. Nada de esto se implementa sin una
  conversación con Dennys.

## 0. Veredicto según los criterios escritos antes de medir

| Escenario | ¿Descartado? | Por qué | Beneficio |
|---|---|---|---|
| **S1** homeostasis (escalado por nodo) | **SÍ** | El canal 2 pierde lugares (snapshot 3173 → 3001, viva 5853 → 5719) y suben los recuerdos sin asociaciones (10 → 27; 1 → 3) | M3 +10 puntos (no cuenta: el escenario está descartado) |
| **S2** poda a cuarentena | **SÍ** | El canal 2 pierde lugares (3173 → 3151; 5853 → 5788) | viva: grado máximo −30 %, nodos con más de 100 vecinos −49 % |
| **S2b** = S2 sin tocar lo visible *(agregado DESPUÉS de medir)* | no | — | viva: nodos con más de 100 vecinos −49 % (cumple el criterio); snapshot: −17 % (no cumple) |

En los cuatro escenarios, la **QA oficial dio idéntica**, con todas las categorías iguales y la lista de casos
fallidos idéntica byte a byte. Lo mismo vale para los invariantes: enlaces manuales, recuerdos y recuerdos con
menos de 5 vecinos.

## 1. Base sintética (invariantes del script)

Base creada desde cero por el motor (solo el esquema), con 120 recuerdos inventados, 4 temas y 12 «hubs»:

| | S1 | S2 |
|---|---|---|
| DB vacía | 0 cambios | 0 cambios |
| Con datos | 581 sinapsis escaladas en 12 nodos (exactamente los hubs) | 26 pares a cuarentena |
| Manuales idénticos / recuerdos idénticos / < 5 vecinos no sube | ✅ / ✅ / ✅ | ✅ / ✅ / ✅ |

## 2. Copias reales

### 2.1 Qué cambió cada escenario

| | Snapshot | Viva |
|---|---|---|
| S1 | presupuesto 29,1; 200 nodos escalados; 10 741 sinapsis cambiadas (111 al piso de .10) | presupuesto 47,2; 226 nodos; 25 411 sinapsis (892 al piso) |
| S2 | 1776 pares a cuarentena | 9003 pares |
| S2b | 1526 pares | 8206 pares |

### 2.2 Métricas (M1–M5)

**Snapshot** (851 recuerdos activos):

| Métrica | S0 | S1 | S2 | S2b |
|---|---|---|---|---|
| Sinapsis automáticas | 13 152 | 13 152 | 11 371 | 11 623 |
| Grado máximo | 258 | 258 | 241 | 241 |
| Nodos con más de 100 vecinos | 24 | 24 | 19 | 20 |
| Suma de pesos automáticos por nodo: máximo | 172,8 | 65,4 | 155,9 | 155,9 |
| Islas (filtro del motor) / crudas de ≥ 5 / mayor cruda | 0 / 2 / 650 | 0 / 1 / 839 | 0 / 2 / 492 | 0 / 2 / 524 |
| M3 examen tapado por peso | 12,5 % | **22,6 %** | 12,5 % | 12,5 % |
| Canal 2: lugares / sin asociaciones | 3173 / 10 | **3001 / 27** ❌ | **3151** / 10 ❌ | 3173 / 10 |
| Manuales (cantidad / suma de pesos) | 588 / 298,334 | = | = | = |
| Recuerdos con < 5 vecinos | 75 | 75 | 75 | 75 |

**Viva** (1380 recuerdos activos; copia):

| Métrica | S0 | S1 | S2 | S2b |
|---|---|---|---|---|
| Sinapsis automáticas | 33 384 | 33 384 | 24 362 | 25 165 |
| Grado máximo | 759 | 759 | **530** | 631 |
| Nodos con más de 100 vecinos | 123 | 123 | **63** | **63** |
| Suma de pesos automáticos por nodo: máximo | 680,1 | 171,8 | 474,0 | 564,9 |
| Islas (filtro del motor) / crudas / mayor | 0 / 1 / 1380 | 0 / 1 / 1380 | 0 / 1 / 1380 | 0 / 1 / 1380 |
| M3 examen tapado por peso | 5,5 % | **15,7 %** | 6,7 % | 6,2 % |
| Canal 2: lugares / sin asociaciones | 5853 / 1 | **5719 / 3** ❌ | **5788** / 1 ❌ | 5853 / 1 |
| Manuales (cantidad / suma de pesos) | 1877 / 938,586 | = | = | = |
| Recuerdos con < 5 vecinos | 24 | 24 | 24 | 24 |

### 2.3 QA oficial (copia del snapshot de cada escenario, `PYTHONHASHSEED=1`, fórmula a mano sola)

| | R@5 | R@1 | MRR | Fallos | FP | Gate | Casos fallidos (md5) |
|---|---|---|---|---|---|---|---|
| S0 | 100 | 93,03 | 0,9566 | 0 | 0/40 | OK | `532837c4…` |
| S1 | 100 | 93,03 | 0,9566 | 0 | 0/40 | OK | `532837c4…` |
| S2 | 100 | 93,03 | 0,9566 | 0 | 0/40 | OK | `532837c4…` |
| S2b | 100 | 93,03 | 0,9566 | 0 | 0/40 | OK | `532837c4…` |

S0 reproduce la QA conocida. Que S1–S2b den igual **es un resultado medido, no un supuesto**, y coincide con el
experimento 12: la QA de una consulta casi no depende de las sinapsis.

## 3. Lo que se aprendió (nuevo)

1. **El canal 2 tiene un umbral absoluto (`peso ≥ .50`).** Cualquier mecanismo que baje pesos (homeostasis,
   atenuación) le roba pistas al agente. Antes de cualquier homeostasis, el canal 2 tendría que dejar de
   depender del peso absoluto. Eso es justo lo que hace la neurona que ordena (experimento 14).
2. **La protección de la poda tiene que mirar lo que ve el agente**, no el número de vecinos. S2 cuidaba que
   ningún recuerdo quedara con menos de 5 vecinos, y aun así quitó pistas visibles. S2b lo corrige por
   construcción.
3. **Las islas no vuelven ni escalando ni podando.** Incluso quitando el 25–27 % de las automáticas, la viva
   sigue siendo una sola comunidad de 1380 recuerdos. La saturación no es de pesos sino de **estructura**: los
   enlaces que unen todo con todo nacen así (`sinonimo_explicito` por `LIKE`, `co_semantica` con un solo token;
   ver `../experimento_14_neurona_ordena_canal2/biologia_ciclo_de_vida_sinapsis.md`, §1).
4. **La homeostasis sí pone los pesos en mejor orden** (M3 +10 puntos en las dos bases), porque los manuales
   (0.5) dejan de quedar tapados por automáticas infladas. El costo es el umbral del punto 1.

## 4. Lo que este experimento NO prueba (limitaciones)

- **S2b se agregó después de ver S2.** Su resultado necesita confirmarse con una medición nueva y
  pre-registrada antes de tomarse como evidencia.
- **No se midió la calidad de lo que S2b manda a cuarentena.** En la hoja de 100 pares (experimento 11), el 36 %
  de lo que la neurona soltaría era bueno. S2b exige además «nunca usado» y «fuera del top 20 de los dos
  lados», pero sin una hoja nueva no se sabe cuánto bueno se perdería.
- **No se reconstruyeron los vectores PPMI** (se construyen con, entre otros, `sinonimo_explicito` y
  `pmi_hebbiano`). Podar cambiaría esos vectores en la siguiente reconstrucción, y ese efecto no está medido.
- **Copia estática:** no hay uso nuevo. «Hebb» se aproximó con `ultimo_uso` histórico, que el código también
  rellena al nacer o al actualizar, y el tercer factor (utilidad en el autoexamen) no se simuló.
- La QA mide una sola consulta. No mide la ráfaga ni lo que el agente hila con varias consultas.

## 5. Recomendación del auditor (para conversar; nada se implementa)

1. **No a la homeostasis (S1) ni a la poda S2** tal como están: los criterios las descartan.
2. **El orden correcto, si se sigue:**
   1. primero, la neurona que ordena el canal 2 (experimento 14), que saca al canal 2 del umbral absoluto;
   2. después, mirar dónde **nacen** los enlaces que unen todo con todo, porque esa es la causa de la
      saturación (punto 3);
   3. solo entonces, volver a medir la poda (S2b) con un protocolo nuevo y una hoja de pares marcada a mano.
3. Los tres puntos requieren el OK de Dennys, uno por uno.

## 6. Cómo repetirlo

```bash
export PYTHONHASHSEED=1
S="docs/Mi neurona en el sistema/experimento_15_ciclo_de_vida_simulado/simular.py"
python "$S" sintetica /tmp/exp15/sint
python "$S" preparar snapshots/qa_escape_qcr_20260811.db /tmp/exp15/snap
python "$S" s2b      snapshots/qa_escape_qcr_20260811.db /tmp/exp15/snap
for e in S0 S1 S2 S2b; do python "$S" medir /tmp/exp15/snap/$e.db /tmp/exp15/snap_$e.json; done
# QA de cada escenario (unos 16 min cada una):
BIORAG_PATH=/tmp/exp15/snap/S0.db BIORAG_QA_ORIGEN=/tmp/exp15/snap/S0.db \
BIORAG_QA_METRICS=/tmp/exp15/qa_S0.json BIORAG_QA_FAILED_CASES=/tmp/exp15/fallidos_S0.jsonl \
  python scripts/evaluar_qa.py
```
