# Experimento 15: protocolo (escrito y subido ANTES de medir)

- **Fecha:** 2026-11-25.
- **Qué es:** una simulación de laboratorio de dos reglas del «ciclo de vida de la sinapsis»
  (`../experimento_14_neurona_ordena_canal2/biologia_ciclo_de_vida_sinapsis.md`).
- **Qué NO es:** una implementación.
  - No cambia el motor, los tests ni la DB viva.
  - No autoriza podar, atenuar ni poner nada en cuarentena en ninguna base real.
  - La decisión vigente sigue siendo la de Dennys: la neurona **solo ordena** el canal 2.
  - Cualquier cambio en el ciclo de vida de las sinapsis se consulta después de ver estos resultados.
- **Etapas:** E3 sigue abierta. Este experimento no avanza ninguna etapa.

## 1. Dónde se mide

| Base | Para qué | Cómo |
|---|---|---|
| **Sintética** (creada desde cero: solo el esquema, con recuerdos y sinapsis inventados) | comprobar que las reglas del script cumplen los invariantes, incluida una DB vacía | sin datos reales |
| **Copia del snapshot** (`snapshots/qa_escape_qcr_20260811.db`, ya público en el repo) | métricas del grafo y **QA oficial** | `sqlite3.backup` en modo solo lectura a `/tmp`; sha256 antes y después |
| **Copia de la DB viva** | métricas del grafo (no hay casos QA para ella) | ídem; **solo totales**, ningún nombre ni contenido sale del sandbox |

## 2. Escenarios (un cambio aislado cada uno)

- **S0 (base):** la copia sin cambios.
- **S1 (homeostasis por nodo, solo escalado):**
  - `A(n)` = suma de pesos de las sinapsis automáticas del nodo `n`.
  - Presupuesto `B` = 2 × la mediana de `A` en ESTA memoria.
  - `f(n) = min(1, B / A(n))`.
  - Cada sinapsis automática `(o, d)` pasa a `peso · sqrt(f(o)·f(d))`, con un piso de 0.10 (la consolidación del
    motor borra las de menos de .05).
  - No se borra ni se mueve nada; los manuales no se tocan.
  - Supuesto declarado: con la media geométrica, el orden dentro de un nodo se conserva solo en parte, porque
    los socios muy conectados bajan más.
- **S2 (poda por competencia a cuarentena, sin homeostasis):** una sinapsis automática pasa a una tabla de
  cuarentena de la copia **solo si cumple todo** esto:
  - fuerza de la neurona < .40;
  - nunca usada (`ultimo_uso` NULL);
  - fuera de los 20 vecinos más fuertes de **los dos** extremos;
  - no es `manual` ni `manual_v7`;
  - después de quitarla, los dos extremos quedan con 5 vecinos activos o más.

  Las sinapsis se revisan de la más débil a la más fuerte.

Supuesto común: en una copia estática no hay uso nuevo. Por eso «Hebb» se aproxima con `ultimo_uso`
histórico, y el tercer factor (utilidad en el autoexamen) **no se simula**. Es una limitación declarada.

## 3. Métricas (definidas antes de medir)

| # | Métrica |
|---|---|
| M1 | Grafo: sinapsis automáticas, grado máximo, nodos con más de 100 vecinos, suma de pesos automáticos por nodo (p50, p90, máximo) |
| M2 | Islas: `core/auto_clustering.detectar_comunidades` del motor (LPA). Comunidades que pasan su filtro (≥ 5 nodos, densidad ≥ .3), comunidades de ≥ 5 nodos sin el filtro de densidad, y el tamaño de la mayor |
| M3 | Examen tapado **por peso**: % de manuales que caen entre los 5 primeros al ordenar por peso, sin la etiqueta |
| M4 | Canal 2 con el código actual (`peso ≥ .50`, escalera): lugares, recuerdos sin asociaciones, fuerza mediana de las automáticas mostradas |
| M5 | Invariantes: enlaces manuales (cantidad y suma de pesos) idénticos; recuerdos idénticos; recuerdos con < 5 vecinos activos |
| M6 | QA oficial sobre la copia del snapshot de cada escenario: R@5, R@1, MRR, FP, gate. Ejecutada con `PYTHONHASHSEED=1` |

## 4. Criterios (definidos antes de medir)

**Un escenario se DESCARTA si:**
- cambia algún enlace manual o algún recuerdo;
- suben los recuerdos con < 5 vecinos activos;
- baja R@5 o R@1, o suben los FP, o el gate deja de dar OK (QA en el snapshot);
- en el canal 2 bajan los lugares o suben los recuerdos sin asociaciones (Pilar 12).

**Un escenario que no se descarta pasa a «vale la pena conversarlo»** si cumple al menos uno de estos:
- M3 sube 10 puntos o más;
- el grado máximo o los nodos con más de 100 vecinos bajan un 30 % o más;
- M2 encuentra más de 1 isla.

**Se informa todo**, incluidos los escenarios descartados. Los resultados nuevos se separan de la evidencia
histórica. No se cambia ningún criterio después de medir. Si hace falta otra variante, se agrega como
escenario nuevo y se dice que se agregó después.
