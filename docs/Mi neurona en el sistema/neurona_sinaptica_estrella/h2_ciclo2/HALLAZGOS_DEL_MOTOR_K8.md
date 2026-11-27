# Dos fallos del motor que el motor se traga (encontrados al medir K8 de verdad)

> **Corrección del 27-11 (revisión de Claude web, el auditor de Arena y el agente local).** Cambia lo siguiente;
> el resto del documento se mantiene:
> 1. **F-A no cambia el ranking.** `content_match_counts` se escribe (L1476, L1494, L1570) pero **no se lee en
>    ninguna parte** (verificado con grep en `core/`). La consulta rota está dentro de **código muerto**: el premio
>    que describe el comentario v22.1 nunca se llegó a implementar. Arreglar el alias no activaría nada. Lo único
>    que cuesta hoy es una consulta fallida por búsqueda. Lo había descrito como «el premio no existe / arreglarlo
>    cambia el ranking»: **era una deducción equivocada**.
> 2. **F-B: el 605 de 777 es una sola configuración** (s7, |D| = 800, D, T, ctl). Que pase lo mismo en todo el reloj
>    comprimido es una **inferencia por el mecanismo**, no un conteo hecho en cada configuración.
> 3. **La traza de K8 contaba de menos.** Deduplicaba por `id(excepción)`, y Python reutiliza los `id` de objetos ya
>    liberados. **Corregido** (se guarda el objeto mientras dura el sueño) y K8 se repitió (`031b062`):
>    - `ctl`: los mismos tipos y lugares; solo cambian las cuentas de `GeneratorExit` (≈ 200 → ≈ 8 500);
>    - `real`: **faltaban tipos enteros en 30 celdas** (por ejemplo `neurona.py:383/479` y F-B en
>      `ppmi_vectorizer.py:153`). F-A pasa de ≈ 100 a ≈ 900 veces por K8;
>    - **los veredictos no cambian:** K8 estricto ✗ en todos; K8-brazo ✓ en −H2 −4b y H2loc+4bp.
> 4. **`search.py:316` no es «una vez por base nueva»:** salta ≈ 1 000 veces por K8. La tabla
>    `concept_hub_domain_dict` no existe y la caché solo se guarda si la consulta sale bien, así que cada búsqueda lo
>    vuelve a intentar. Es benigno (no hay diccionario), pero se repite; va a la lista de §4.
> 5. **4bp protege a los mismos recuerdos que 4b:** comprobado ejecutando las dos sentencias exactas sobre recuerdos
>    protegidos (`prueba_inmunes_4b.py`). Los dos excluyen valencia ≥ 0,8 y Principle/Protocol; **ninguno** excluye la
>    prioridad 0/1. Además, **ningún camino del motor fija una prioridad 0/1** (solo existe el valor por defecto 3, en
>    `schema.py`): la inmunidad por prioridad de H2 y LTD solo actúa si alguien edita la base a mano.

> **Origen.** La auditoría de `64e055f` señaló que K8 daba `sin_excepciones = True` sin medirlo. Al medirlo se
> registraron, con una traza del sueño (`sys.settrace`, solo en el laboratorio), todas las excepciones que se lanzan en
> código de `core/`, también las que el propio motor captura y calla. La mayoría son caminos previstos. **Dos son
> fallos reales.**
> **No se tocó el motor.** `core/` y `tests/` siguen como en `d7bc5dc`. Cada arreglo propuesto necesita el OK de
> Dennys y su propio ciclo: uno a uno, con Antes/Después, tests nuevos y la QA.

## 0. Qué se lanzó dentro del sueño

Datos: K8, 5 brazos × 3 semillas × 2 mundos (`resultados/k8_*.json`).

| excepción | dónde | qué es | clase |
|---|---|---|---|
| `GeneratorExit` | `stemmer_es.py:56`, `cjk_unidades.py:49`, otros | `any(...)` que corta un generador | control de flujo normal de Python |
| `OperationalError: no such table: nodos` | `ppmi_vectorizer.py:196` | base nueva, primera vez | prevista (base vacía) |
| `OperationalError: no such table: neurona_estado` | `memory/neurona.py:383` y `:479` | base nueva | prevista |
| `OperationalError: no such table: concept_hub_domain_dict` | `memory/search.py:316` | tabla opcional; se reintenta en cada búsqueda (≈ 1 000 por K8) | prevista, pero repetida (§4) |
| `TypeError: int(None)` | `memory/search.py:45`, `memory/synapses.py:33`, `similitud_conceptual.py:46` | corte de rowid ausente (`_corte_rowid_positivo`) | prevista (el código lo documenta) |
| **`OperationalError: no such column: l.contenido`** | **`memory/search.py:1488`** | **alias que no existe** | **fallo real (F-A)** |
| **`ValueError: operands could not be broadcast together with shapes (27,) (100,)`** | **`ppmi_vectorizer.py:153` ← `:288` ← `consolidation.py`** | **vectores de distinto tamaño** | **fallo real (F-B)** |

- **En los 5 brazos aparecen las mismas.** Ninguna la causa una variante de H2/4b: son del motor.
- Por eso, en `resumen_ciclo2.py`, **K8 estricto no lo cumple ningún brazo** (ni T). **K8-brazo**, que descuenta las
  excepciones que ya aparecen en T, lo cumplen −H2 −4b y H2loc+4bp.

## F-A. La consulta del «conteo de coincidencias en el contenido» falla siempre [V] — dentro de código muerto (corrección 1)

- **Dónde:** `core/memory/search.py` L1477–1495.
- **Qué pasa:**
  - la cláusula se arma con `PALABRA_INICIO_ANCHO(?, l.contenido)`, pero la consulta es
    `SELECT concepto, (...) FROM largo_plazo WHERE concepto IN (...)`, sin el alias `l`;
  - SQLite responde «no such column: l.contenido»;
  - el `except sqlite3.OperationalError: pass` la calla.
- **Efecto (corregido):**
  - `content_match_counts` queda vacío, pero **nadie lo lee**: ni el ranking ni ningún otro módulo;
  - el comentario v22.1 promete un premio a los candidatos de FTS que además coinciden en el contenido; **ese premio
    no está implementado**. Sin efecto en el ranking hoy;
  - la segunda consulta (L1530–1540) sí usa el alias (`CROSS JOIN largo_plazo l`), funciona y **sí** se usa (amplía
    los candidatos con `origen_scores = "contenido"`).
- **Frecuencia en el laboratorio:** ≈ 900 veces por K8 de 80 sueños con la neurona activa (traza corregida). La Neurona
  1 hace búsquedas dentro del sueño.
- **Antigüedad:** está así en el commit base `a6d271a`. No lo introdujo ningún cambio de esta rama.
- **Qué hacer (ticket, sin aplicar, después de la neurona; decisión del agente local del 27-11):** quitar el bloque
  muerto, o arreglar el alias **sin** usar el conteo. Ninguna de las dos cambia el ranking; las dos ahorran una
  consulta por búsqueda. Implementar el premio de v22.1 sería otra cosa: una señal nueva de ranking, con su propio
  ciclo y la QA.

## F-B. En bases jóvenes, el canal PPMI queda casi apagado y su retrofitting falla [V]

- **Dónde:** `core/ppmi_vectorizer.py`:
  - `fold_in_nodos` (L221), L263: `v_final = np.zeros(100)`, con el número 100 fijo;
  - `PPMISVD.entrenar`, L97: `dim_real = min(self.dim, V, D)`;
  - `_ppmi_full_reindex_due` (L191): reentrena solo si pasaron 7 días **y** hay ≥ 50 nodos nuevos.
- **Qué pasa:**
  1. El primer sueño de una base vacía entrena el PPMI con los pocos recuerdos que hay. En el laboratorio: 65 tokens,
     **27 dimensiones**.
  2. Después, si no pasan 7 días, no se vuelve a entrenar. El vocabulario queda congelado en esos 65 tokens.
  3. Cada recuerdo nuevo sin tokens conocidos recibe un vector de **ceros de 100 dimensiones** (no de 27).
  4. Al hacer `retrofit` con vecinos de 27 dimensiones, el numpy falla. `consolidation.py` captura la excepción y la
     calla. Las filas ya insertadas quedan como están.
- **Medido en una sola configuración** (s7, |D| = 800, mundo D, brazo T, ctl; corrección 2):

  | reloj | vectores de nodo | en cero | tokens del modelo |
  |---|---|---|---|
  | comprimido (sueños cada 60 s) | 605 de 100 dims + 172 de 27 dims | **605** | 65, de 27 dims |
  | diario (pasan los 7 días) | 333 de 100 dims | 0 | 588, de 100 dims |

- **Efecto:**
  - **[D, por el mecanismo]** en el reloj comprimido, el canal PPMI (señal #13) casi no existiría en todas las
    corridas del laboratorio (medición de H2, R-E1, R-E2 y ciclo 2). Medido solo en la configuración de arriba;
  - **[D] muy probable:** es la causa del «vector nulo en 36/36» y del `score_candidato` idéntico de R-E2
    (`RESULTADOS_RESIDUAL.md` §7). Allí se describió el efecto, no la causa;
  - en uso real, un usuario que guarda mucho durante su primera semana tendría el canal PPMI entrenado con sus
    primeros recuerdos y la mayoría de los vectores en cero hasta el primer reentrenamiento.
- **Arreglos propuestos (sin aplicar):**
  - (a) ceros del tamaño del modelo (`len` de un vector de token), no 100;
  - (b) reentrenar también cuando el corpus se duplicó desde el último entrenamiento. Es un calendario geométrico:
    costo total lineal, sin depender del reloj de pared.
  - Las dos opciones tocan el ranking a través del canal PPMI: misma exigencia de QA que F-A.

## Qué cambia en lo ya medido

- **Ciclo 2:**
  - los veredictos de estado (K1, K3, K4, K5″, K6) no dependen del PPMI de búsqueda;
  - los del top-k en comprimido se midieron **con el canal PPMI casi apagado**. Vale igual para los 5 brazos, pero es
    una condición del laboratorio que hay que tener presente.
- **Paso 3:** R y G_ciego se miden sobre la copia limpia con `BIORAG_PPMI_WEIGHT=0` (protocolo §6), así que F-B no
  los afecta. F-A no afecta a nada (corrección 1).

## 4. Ticket aparte: los `except sqlite3.OperationalError: pass` del motor

- **Origen:** Claude web contó 33 en `core/`. Con un recorrido del árbol sintáctico (`ast`) salen **35**:
  23 en `memory/search.py`, 3 en `memory/rafaga.py`, 2 en `memory/schema.py`, 2 en `neurona_asociativa.py`, 2 en
  `sinapsis.py`, y uno en `mcp_server/search.py`, `memory/consolidation.py` y `memory_store.py`.
- **Cuáles saltan de verdad en el laboratorio** (traza de K8, dentro del sueño): `search.py:1488` (F-A, código
  muerto) y `search.py:316` (tabla opcional, se reintenta en cada búsqueda). La lista completa, con lo que salta y
  lo que no también en búsquedas, está en `INVENTARIO_EXCEPT_PASS.md`.
- **Decisión del agente local (27-11):** queda anotado; se revisa después de cerrar la neurona. No se toca el motor.

