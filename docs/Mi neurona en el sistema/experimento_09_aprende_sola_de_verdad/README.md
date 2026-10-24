# Experimento 09 — Que aprenda sola de verdad (v34.1)

> **Pregunta (Dennys):** *"¿Y este modo de aprender no es muy lento para un tercero con una DB nueva?"*
>
> **Respuesta corta:** sí lo era. Con v34.0 una DB nueva **nunca** juntaba su examen: en 80 sesiones
> llegó a 20 preguntas de estudio y 7 de control (necesita 150 y 40). Con v34.1 el examen está listo en
> la **sesión 16** y la neurona trabaja desde la **sesión 21**. En el snapshot canónico, a igual número
> de prácticas, la QA oficial queda **igual** (1 caso de 875 de diferencia, dentro del ruido normal).

## 0. En una línea por hallazgo

1. **La neurona practica 1 vez por consolidación, no por guardado.** `aprender` deja el recuerdo en
   corto plazo; la práctica corre al pasar a largo plazo (`consolidar`, `sueno`, `contexto_fin`).
   10 `aprender` + 1 `consolidar` = 1 práctica. (El texto de `--estado` decía "por guardado": corregido.)
2. **Era lento porque preguntaba poco:** 2 recuerdos × 2 preguntas por práctica. Tenía permiso de usar
   3 s y usaba 0.4 s en una DB chica.
3. **Segundo freno, del propio motor:** cada consolidación baja 0.075 el peso de todo recuerdo que no
   se usa (LTD) y a las ~13 consolidaciones sin uso se duerme. La neurona (correctamente) tira las
   preguntas de los dormidos. Con poquitas preguntas nuevas, perdía casi lo mismo que ganaba.
4. **Primer intento (8 recuerdos × 7 preguntas, en profundidad): descartado.** En la DB nueva mejoró
   mucho, pero en el snapshot la QA bajó a **R@1 93.26** (antes 94.86). Causa medida: en una DB
   grande los 3 s alcanzan para ~15 preguntas, y se las hacía a 2 recuerdos. El examen terminó con
   **212** recuerdos distintos en vez de **312**: conocía menos recuerdos y se acostumbraba a ellos.
5. **La solución: preguntar A LO ANCHO.** Primero la 1ª pregunta de los 8 recuerdos, luego la 2ª de
   los 8... hasta que se acaban los 3 s. En una DB chica igual alcanza para todas; en una grande quedan
   repartidas. El examen final tiene **535** recuerdos distintos (estudio) y **136** (control).
6. **Repasar primero lo que falta:** al completar con recuerdos al azar, se eligen primero los del
   grupo del examen (estudio o control) al que más le faltan preguntas. Sin sesgo cuando ninguno falta.
7. **Arreglo menor:** con un número impar de preguntas por recuerdo, los dos caminos (agente y crudo)
   quedaban desbalanceados. Ahora se alterna con un contador de todo el ciclo.

## 1. El cambio, en el código (`core/memory/neurona.py`)

| | v34.0 | v34.1 |
|---|---|---|
| Recuerdos por práctica (`BIORAG_NEURONA_NODOS`) | 2 | **8** (tope) |
| Preguntas por recuerdo (`BIORAG_NEURONA_PREGUNTAS`) | 2 | **7** (tope; todas las que genera) |
| Presupuesto (`BIORAG_NEURONA_PRESUPUESTO_S`) | 3 s | 3 s (sin cambio: es el costo fijo) |
| Orden de las preguntas | por recuerdo | **a lo ancho** (ronda 1 de todos, ronda 2 de todos...) |
| Relleno al azar | cualquiera | **primero el grupo al que más le falta** (`_le_falta`) |
| Consultas para elegir recuerdos | ≤ 4·n | ≤ 4·n (sin cambio: no crece con la DB) |

Nada más cambia: ni la búsqueda, ni el piso, ni la guardia, ni las 18 capas. La neurona solo **junta
su examen más rápido y más variado**.

```text
listas = [(recuerdo, sus_preguntas[:7]) for recuerdo in elegir(8, prefiere=_le_falta(examen))]
orden  = [(r, qs[i]) for i in range(7) for r, qs in listas if i < len(qs)]   # a lo ancho
for r, q in orden:
    if tiempo + la_más_lenta > 3 s: break                                      # costo fijo
    caso = preguntar(r, q, camino=alternar())                                  # agente / crudo
```

## 2. DB nueva que crece (lo que vive un tercero)

`simular_db_nueva.py`: una DB vacía; cada sesión guarda N recuerdos reales del snapshot (en orden de
creación) con `percibir_corto_plazo` y consolida **una vez** con `ciclo_sueno_consolidacion`. Nadie
busca nada (caso más duro: el motor duerme lo que no se usa). 80 sesiones.

**Usuario normal (5 recuerdos por sesión):**

| Versión | Examen listo (150 + 40) | 1ª campeona | Sesiones con campeona | s/consolidación |
|---|---|---|---|---|
| v34.0 (2 × 2) | **nunca** (final: 20 / 7) | **nunca** | 0 / 80 | 0.65 |
| Intento 1: 8 × 7 en profundidad + preferencia | sesión 16 | sesión 69 | 12 / 80 | 2.51 |
| **v34.1: 8 × 7 a lo ancho + preferencia** | **sesión 16** | **sesión 21** | **60 / 80** | **2.15** |

Variantes medidas solo con variables de entorno sobre el código de v34.0 (para elegir los topes):

| Variante (sin preferencia, en profundidad) | Examen listo | 1ª campeona | Sesiones con campeona |
|---|---|---|---|
| 12 × 4 | 20 | 20 | 41 / 60 |
| 16 × 4 | 20 | 20 | 10 / 60 |
| 6 × 7 | 20 | 20 | 41 / 60 |
| 8 × 7 | 19 | 26 | 55 / 80 |

(Una corrida intermedia, 12 × 4 con preferencia, no llegó a campeona en 80 sesiones; su salida no se
conservó porque se reemplazó al pasar a 8 × 7. Se cuenta igual para no esconderla.)

Estado final de v34.1 en la DB nueva (sesión 80): 7 aprobaciones, **0 retiros**, campeona trabajando;
en sus 48 preguntas de control el primer lugar pasa de **87.5 %** (fórmula) a **89.6 %** (neurona).
En una DB chica la fórmula ya acierta casi todo: la neurona suma poco, y nunca resta.

**Usuario ligero (2 recuerdos por sesión):** ninguna versión llega. Solo tiene ~25 recuerdos
despiertos (el resto se durmió por no usarse) y con tan pocos la fórmula alcanza: **es correcto que la
neurona no se encienda**. Con v34.1 junta 4 veces más preguntas (57 / 7 frente a 14 / 1), así que
cuando esa memoria crezca o se use, llegará.

## 3. Snapshot canónico (~900 recuerdos): ¿se pierde algo?

Copia nueva del snapshot por corrida. `despertar_neurona.sh` y después la QA oficial
(`scripts/evaluar_qa.py`) y el camino del agente (experimento 07, `evaluar_camino_mcp.py`). Nunca dos
corridas pesadas a la vez. El presupuesto de 3 s hace que dos corridas del **mismo** código ya
difieran algunos casos (experimento 08); por eso se dan referencias de varias corridas.

**QA oficial (875 de recuperación + 40 negativos):**

| Corrida | Prácticas | R@5 | R@1 | MRR | FP | GATE |
|---|---|---|---|---|---|---|
| Fórmula a mano (piso) | — | 99.89 | 91.66 | .949 | 0/40 | OK |
| v34.0 publicada (README, 500 prácticas) | 500 | 100 | 94.06 | .964 | 0/40 | OK |
| v34.0 hoy, 17 min | 561 | 100 | 94.86 | .969 | 0/40 | OK |
| Intento 1 (profundidad), 17 min | 378 | 100 | **93.26** | .958 | 0/40 | OK |
| v34.1, 17 min | 389 | 100 | 94.17 | .964 | 0/40 | OK |
| **v34.1, mismas 561 prácticas** | 561 | **100** | **94.74** | **.968** | **0/40** | **OK** |

**Por categoría, R@1 (fórmula → v34.0 hoy → v34.1 a 561 prácticas):**

| Categoría (n) | Fórmula | v34.0 | v34.1 |
|---|---|---|---|
| cruce_idioma (8) | 62.50 | 87.50 | 87.50 |
| dormido (65) | 100 | 100 | 100 |
| literal (487) | 99.59 | 99.59 | 99.59 |
| por_tema (65) | 63.08 | 78.46 | 78.46 |
| pregunta_natural (65) | 93.85 | 95.38 | 96.92 |
| sinonimo (55) | 56.36 | 63.64 | 60.00 |
| typo (65) | 87.69 | 96.92 | 95.38 |
| variante_gramatical (65) | 87.69 | 95.38 | 96.92 |
| **GLOBAL (875)** | **91.66** | **94.86** | **94.74** |

Ninguna categoría queda por debajo de la fórmula. Frente a v34.0 hoy: +1 caso en pregunta_natural,
+1 en variante_gramatical, −1 en typo, −2 en sinónimo: neto **−1 caso de 875**, el orden de la
variación entre entrenamientos (experimento 08: el mismo código dio por_tema 78.46 y 84.62).

**Camino del agente (MCP, 875):**

| Corrida | R@1 | R@5 | MRR |
|---|---|---|---|
| Fórmula a mano (experimento 07) | 92.34 | 99.09 | .951 |
| v34.0 hoy, 17 min | 94.97 | 99.54 | .967 |
| Intento 1 (profundidad), 17 min | 93.37 | 99.20 | .957 |
| v34.1, 17 min | 94.40 | 99.31 | .963 |
| **v34.1, 561 prácticas** | **94.74** | **99.54** | **.966** |

**El examen de la neurona al final (cuántos recuerdos distintos conoce):**

| Corrida | Estudio: casos / recuerdos | Control: casos / recuerdos | 1ª aprobación | Aprobó | La quitaron |
|---|---|---|---|---|---|
| v34.0 hoy | 645 / 312 | 179 / 89 | práctica 86 | 19 | 0 |
| Intento 1 (profundidad) | 616 / **212** | 168 / **56** | práctica 71 | 9 | 0 |
| v34.1, 17 min | 801 / 433 | 231 / 115 | práctica 60 | 3 | 0 |
| **v34.1, 561 prácticas** | **1138 / 535** | **300 / 136** | **práctica 61** | 7 | 0 |

El intento 1 sacaba 97.5 % en su propio control, pero con solo 56 recuerdos de control esa nota era
optimista: en la QA rindió peor. v34.1 tiene un control 2.4 veces más grande y variado; su nota
(89.3 %) es más baja y más honesta.

## 4. Lo que esto NO dice

- No dice que v34.1 mejore la QA del snapshot: **la iguala** a igual número de prácticas. La ganancia
  es para quien empieza con una DB nueva (de "nunca" a "sesión 21").
- A igual **tiempo** de despertar (17 min) v34.1 hace menos prácticas (cada una usa sus 3 s) y quedó
  0.7 puntos abajo (94.17). Por eso `despertar_neurona.sh` sigue con su default de **500 prácticas**
  (ahora ~22 min con ~900 recuerdos) en vez de recomendar menos minutos.
- Cada consolidación cuesta ahora **hasta 3 s** (antes ~0.4–1.6 s). Es el mismo tope que ya existía; el
  costo sigue sin crecer con el tamaño de la DB.
- Una sola corrida por configuración en el snapshot (cada una tarda ~45 min). Las conclusiones se
  apoyan en las varias referencias de v34.0, no en una sola.

## 5. Reproducir

```bash
cd "docs/Mi neurona en el sistema/experimento_09_aprende_sola_de_verdad"
mkdir -p /tmp/q/e09/base && (cd ../../.. && git archive 55dc8f5 | tar -x -C /tmp/q/e09/base)
cp -r ../../../MemoryBioRAG_Data/nltk_data /tmp/q/e09/base/MemoryBioRAG_Data/
bash correr.sh /tmp/q/e09/base "$(cd ../../.. && pwd)"     # ~3 h: DB nueva + snapshot A/B
# a igual número de prácticas: en correr.sh cambiar "--minutos 17 --ciclos 100000" por "--ciclos 561"
```

## 6. Archivos

- `simular_db_nueva.py`: DB nueva que crece, una consolidación por sesión, una línea por sesión.
- `correr.sh`: corrida completa (DB nueva + despertar + QA oficial + camino MCP) para A y B.
- `resultados/`: `sim_*.txt`, `despertar_*.txt`, `qa_oficial_*.txt`, `mcp_*.json|txt`
  (`antes` = v34.0, `v1profundo` = intento 1, `final_17min` y `final_561ciclos` = v34.1).
