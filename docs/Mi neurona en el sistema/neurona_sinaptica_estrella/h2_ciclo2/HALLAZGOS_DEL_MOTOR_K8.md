# Dos fallos del motor que el motor se traga (encontrados al medir K8 de verdad)

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
| `OperationalError: no such table: concept_hub_domain_dict` | `memory/search.py:316` | tabla opcional | prevista |
| `TypeError: int(None)` | `memory/search.py:45`, `memory/synapses.py:33`, `similitud_conceptual.py:46` | corte de rowid ausente (`_corte_rowid_positivo`) | prevista (el código lo documenta) |
| **`OperationalError: no such column: l.contenido`** | **`memory/search.py:1488`** | **alias que no existe** | **fallo real (F-A)** |
| **`ValueError: operands could not be broadcast together with shapes (27,) (100,)`** | **`ppmi_vectorizer.py:153` ← `:288` ← `consolidation.py`** | **vectores de distinto tamaño** | **fallo real (F-B)** |

- **En los 5 brazos aparecen las mismas.** Ninguna la causa una variante de H2/4b: son del motor.
- Por eso, en `resumen_ciclo2.py`, **K8 estricto no lo cumple ningún brazo** (ni T). **K8-brazo**, que descuenta las
  excepciones que ya aparecen en T, lo cumplen −H2 −4b y H2loc+4bp.

## F-A. La consulta del «conteo de coincidencias en el contenido» falla siempre [V]

- **Dónde:** `core/memory/search.py` L1477–1495.
- **Qué pasa:**
  - la cláusula se arma con `PALABRA_INICIO_ANCHO(?, l.contenido)`, pero la consulta es
    `SELECT concepto, (...) FROM largo_plazo WHERE concepto IN (...)`, sin el alias `l`;
  - SQLite responde «no such column: l.contenido»;
  - el `except sqlite3.OperationalError: pass` la calla.
- **Efecto:**
  - `content_match_counts` queda **vacío para todos los candidatos** en toda búsqueda no estricta de 2 o más palabras;
  - según el comentario del código (v22.1), ese conteo es el que premia a los candidatos de FTS que **además**
    coinciden en el contenido. Hoy ese premio no existe;
  - la segunda consulta (L1530–1540) sí usa el alias (`CROSS JOIN largo_plazo l`) y funciona.
- **Frecuencia en el laboratorio:** 103 veces en un K8 de 80 sueños con la neurona activa. La Neurona 1 hace búsquedas
  dentro del sueño.
- **Antigüedad:** está así en el commit base `a6d271a`. No lo introdujo ningún cambio de esta rama.
- **Arreglo propuesto (sin aplicar):** `FROM largo_plazo l WHERE l.concepto IN (...)`.
  - **Cuidado:** activar el premio **cambia el ranking**, y la norma dice que el ranking no se toca. Restaura una
    intención del código, pero hay que medirlo con la QA completa (R@5, R@1, MRR, FP 0/40) antes de decidir.

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
- **Medido** en s7, |D| = 800, mundo D, brazo T, configuración ctl:

  | reloj | vectores de nodo | en cero | tokens del modelo |
  |---|---|---|---|
  | comprimido (sueños cada 60 s) | 605 de 100 dims + 172 de 27 dims | **605** | 65, de 27 dims |
  | diario (pasan los 7 días) | 333 de 100 dims | 0 | 588, de 100 dims |

- **Efecto:**
  - en el reloj comprimido, el canal PPMI (señal #13) **casi no existe** en todas las corridas del laboratorio:
    medición de H2, R-E1, R-E2 y ciclo 2;
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
- **Paso 3:** R y G_ciego pasan por el buscador. Se medirán con el motor tal cual, con F-A y F-B anotados, y se
  repetirán si se aprueban los arreglos (ver el protocolo del Paso 3, §6).
