# Experimento 18 — Informe previo: lo que pidió Claudia, comprobado en el código

**Fecha:** 2026-11-25 · **Rama:** `arena/da3df5df-memorybiorag` · **Base:** `fc111d6`

Este informe responde al punto 7 («antes de nada») de la propuesta de Claudia. Además, comprueba una por una
sus demás afirmaciones antes de diseñar nada. **No se modificó ningún archivo del motor ni de los tests.**

Notación:
- **[V]** = verificado leyendo el código o los resultados guardados en el repo, con archivo y línea.
- **[D]** = deducido. Es razonamiento, no medición.

---

## 1. Punto 7: ¿quién llama al código de `search.py` L3023 y L3148?

Las dos líneas están dentro de dos funciones viejas de evocación por **clave exacta**:

| Línea | Función | Qué hace al acceder a un recuerdo |
|---|---|---|
| L3017–3032 | `buscar_recuerdo_microsegundos` (L2958) | El recuerdo sube +0,15. **Todos** sus vecinos por sinapsis suben +0,05 en `largo_plazo.peso_sinaptico`. **Todas** sus sinapsis reciben `ultimo_uso = ahora` |
| L3141–3156 | `buscar_recuerdo_profundo` (L3075) | Lo mismo. Además despierta el recuerdo si estaba dormido y propaga por la columna vieja `asociaciones` |

**Quién las llama [V]** (con `grep` en todo el repo, excluyendo `docs/` y los tests):

| Llamador | ¿Lo usa el agente por MCP? |
|---|---|
| `biorag.py` L374/L376: CLI `recordar` **sin** `--todos` | No. Es la línea de comandos |
| `core/sinapsis.py` L392 `buscar_vecinos` → L412 pone `ultimo_uso` a **todas** las sinapsis del nodo | No. Solo lo llama `test_memory.py` L471 |
| `middleware/interceptor.py` L82 `procesar_comandos_ocultos` (`[BUSCAR: …]`) | No. **Nadie llama a esa función** |
| `scripts/concurrencia_qa.py`, `test_memory.py` | No. Son scripts de prueba |
| `core/memory_store.py` L313/L328 | Son envoltorios de una línea hacia las dos funciones |

Ninguno de los 1141 tests de `tests/` llama a estas dos funciones.

**Conclusión [V]:**
- Claudia describe bien lo que hace ese código: es una señal **difusa**, porque al tocar un recuerdo se marcan
  como usadas todas sus sinapsis, buenas y malas.
- Pero **ese código no está en el camino del agente**. Las herramientas MCP `recordar` y `buscar`
  (`core/mcp_server/search.py` L550) usan `buscar_por_frase`, y `buscar_por_frase` **no escribe**
  `sinapsis.ultimo_uso`.

### 1.1 Todo lo que hoy escribe `sinapsis.ultimo_uso` [V]

| Dónde | Cuándo | ¿Es por par? |
|---|---|---|
| `search.py` L3030 y L3154 | evocación por clave exacta (CLI) | No: todas las sinapsis del nodo |
| `sinapsis.py` L412 | `buscar_vecinos` (solo tests) | No: todas las sinapsis del nodo |
| `rafaga.py` L342 | ráfaga (B10), cuando crea o refuerza el par | Sí, pero es nacimiento, no uso |
| `synapses.py` L95 | `feedback(util=True)`, sobre las aristas del **camino exacto** de la evocación en cadena | **Sí, por par**. Ver §1.2 |
| upserts de nacimiento (B1–B7) | al nacer o al reforzar por las vías léxicas | Sí, pero es nacimiento, no uso |

### 1.2 Ya existe un refuerzo por par, pero casi nunca se dispara [V]

En `aplicar_refuerzo_dopaminergico` (`core/memory/synapses.py` L59–150), si `feedback(util=True)` llega y
`last_parent_map` no está vacío, se refuerzan **solo las aristas del camino** que llevó al recuerdo:
`peso += 0.05·(1−peso)`. Es exactamente la coactivación por par que pide Claudia, con un tercer factor. Pero
casi nunca actúa:
- `last_parent_map` se vacía al empezar **cada** `buscar_por_frase` (L108). Solo se llena en el **fallback 1.9**
  (evocación en cadena, L1097–1098), que corre únicamente si la búsqueda normal devolvió **menos de 3**
  resultados y el modo no es estricto.
- El cerebro del MCP es un singleton (`_shared.py` L102–104, y `cerrar_sistema` no hace nada en el singleton,
  `memory_store.py` L660–663). Por eso el mapa sobrevive entre llamadas, pero cualquier búsqueda intermedia lo
  borra.
- Además depende de que el agente llame a `feedback`. Eso **choca con la norma 4 de Dennys** («sin feedback del
  agente»). El propio `core/feedback_implicito.py` documenta que `log_busquedas.util` estaba vacía: 0 de 2157
  filas.

### 1.3 Ya existe un registro de qué salió junto en cada consulta [V]

`buscar_por_frase` guarda en `log_busquedas` (L2896–2908) la consulta, la fecha y `conceptos_top`, que es el
**top-5 de cada búsqueda**:
- Se escribe salvo con `BIORAG_NO_LOG=1` o en silencio de neurona.
- Un trigger lo purga a los **7 días** (`schema.py` L716–723).
- Además, `nodo_accesos_historial` guarda los accesos **por nodo** (`dmn.py` L66), no por par.

---

## 2. ¿Cómo se haría la coactivación por par? Tres caminos

| Camino | Cómo | Costo | Choque con las normas de Dennys |
|---|---|---|---|
| **A. Derivarla de `log_busquedas`** | En el sueño se cuenta, para cada par (A,B) que ya tiene sinapsis, en cuántas consultas distintas aparecieron A y B en el mismo top-5, y en cuántos días distintos | sin columnas nuevas; K nodos por sueño | **Sí.** Es telemetría de búsquedas reales. U0 dice «sin telemetría». La norma 4 dice «sin registrar qué usó». Hay que **pedir la excepción** |
| **B. Contador nuevo por sinapsis** | Al responder `recordar`, sumar 1 a cada par del top-k que ya tiene sinapsis | una escritura por consulta | **Sí, y más fuerte.** U0: «ninguna señal nueva por sinapsis» |
| **C. Repaso interno en el sueño** (autoexamen, *replay*) | En cada sueño el motor **se pregunta a sí mismo**: para K recuerdos tocados desde el último sueño, arma consultas con los campos del propio recuerdo (alias, sinónimos, sustantivos clave, dimensiones) y corre la búsqueda real **en silencio** (`neurona.silencio`, L102: no escribe accesos ni log). Si A y B se activan juntos, ese par queda coactivado | K búsquedas por sueño, costo fijo | **No.** No observa al agente, no guarda telemetría y no pide trabajo extra. Es la **medición D del exp. 10**, ya prevista como «tercer factor» en la biología §4 |

**Recomendación [D]: el camino C.**
- Es el equivalente directo del cerebro. En el sueño, el hipocampo **repite** lo marcado en la vigilia y eso
  decide qué se consolida (Yang, Buzsáki y col., *Science* 2024, ya citado en la biología §2).
- Además es el único camino que no rompe ninguna norma vigente.

**Riesgo del camino C, que hay que medir:** el repaso premia los pares que el canal 1 **ya** encuentra juntos.
Un enlace así es **redundante**: no le da al agente nada nuevo. Por eso el protocolo mide aparte el **aporte
único**: los pares relacionados que la consolidación conserva y que el canal 1 **no** trae solo (ver
`PROTOCOLO.md` §6).

---

## 3. Lo que dijo Claudia, comprobado

| Afirmación | Veredicto | Evidencia |
|---|---|---|
| Existen los commits `7e1eb9c`, `555b06e`, `6d64515` y `fc111d6` | ✅ [V] | `git log` |
| El 2a compara por coincidencia exacta con normalización Unicode, sin listas | ✅ [V] | `core/sinapsis.py`, `_norma_sinonimo` |
| Solo el 11–18 % de las sinapsis automáticas une recuerdos relacionados | ✅ [V] | exp. 16, `RESULTADOS.md` L14 y L68 |
| Con otro orden cambia la puntuación del 73–78 % de los pares | ✅ [V] | exp. 16, `RESULTADOS.md` L18, L96 y L99 |
| AUC 1,000 y ECE 0,001 no prueban valor | ✅ [V], y **con causa encontrada** | `mundo.py` L45–60: cada tema tiene **25 pseudopalabras exclusivas** (el conjunto `usadas` impide repetirlas entre temas). Cada recuerdo lleva 14 de ellas y el 70 % de los sinónimos sale de ahí. La relación queda escrita en el vocabulario por construcción. Además, los conectores son una **lista de palabras en español** (L11). Ese mundo no representa ni el lenguaje real ni el chino o el japonés |
| «El experimento 12 no mejoró nada al poner el peso al nacer» | ⚠️ **Inexacto** [V] | exp. 12 §3.1–3.2: el QA quedó **idéntico** (la expansión por el grafo actúa en 8 de 921 consultas). Pero el grafo **sí mejoró**: AUC 0,628 → 0,738 y enlaces manuales entre los 6 vecinos principales de 86 a 142 (+65 %). Lo correcto es: «no cambió el recall, porque el QA casi no ve el peso de las sinapsis» |
| «Cortar al nacer bajó el recall» (exp. 13) | ✅ [V] | exp. 13, `README.md` L113: «cualquier corte al nacer baja el recall, incluso con umbral 0.40» |
| Ya está escrita la «neurona asociativa v3» en la biología §4 | ✅ [V] | `experimento_14…/biologia_ciclo_de_vida_sinapsis.md` L60–125: «captura ≥ 2 de 3» con (1) fuerza ≥ 0,80, (2) Hebb, (3) autoexamen |
| Al acceder, todas las sinapsis reciben `ultimo_uso` y los vecinos suben +0,05 | ✅ [V] el código, ⚠️ el alcance | Cierto en L3023–3030 y L3148–3154, pero ese código **no está en el camino del agente**. Ver §1 |
| A-MEM: candidatos por embeddings y luego un LLM decide los enlaces | ✅ | arXiv 2502.12110 §3.2: «we prompt the LLM to analyze potential connections» sobre los k vecinos más cercanos. Publicado en NeurIPS 2025 |
| Vecinas con actividad coordinada se protegen de la poda | ✅ | Niculescu y col., *Cell Reports* 2018: BDNF estabiliza las sinapsis agrupadas; proBDNF deprime las que van «fuera de compás» |
| La compresión entre textos (NCD) sirve | ❓ hipótesis, **con una advertencia** | La literatura advierte que con textos de menos de unos 100 bytes la cabecera del compresor domina y la NCD no es fiable. Hay que medirla, no suponerla |

---

## 4. Choques con las normas de Dennys (hay que resolverlos antes de construir)

| # | Lo que propone Claudia | Norma con la que choca | Propuesta |
|---|---|---|---|
| **C1** | coactivación **por par** a partir del uso | **norma 4** (sin feedback, sin registrar qué usó) y **U0** (ninguna señal nueva por sinapsis, sin telemetría) | usar el **repaso interno** (camino C). Si Dennys prefiere el uso real (camino A), necesita **autorizar una excepción escrita** |
| **C2** | examen en datos reales, ocultando enlaces `manual` | **decisión 3** (no se usa la DB viva, ni recuerdos privados, ni el snapshot; `manual` no es etiqueta) | hasta que Dennys lo autorice: mundos sintéticos **sin filtración léxica** (§3) y corpus multilingües escritos a mano. El examen real queda como etapa **bloqueada** en el protocolo |
| **C3** | la biología §4 usa como factor 2 «A y B salieron juntos en un recordar» | **U0**, posterior a ese documento | se sustituye por el repaso interno. Así el factor 2 y el 3 quedan en uno solo, interno |
| **C4** | que la neurona «aprenda de cada memoria» | **invariancia** (Norma Máxima) y neurona **cerrada** | primero la neurona «de fábrica» (congelada y versionada), como dice la propia Claudia. Aprender por memoria queda como decisión aparte |

**Lo que sí encaja sin choques [V/D]:**
- Nacer igual que hoy (exp. 13).
- Estado «a prueba» con fecha.
- Consolidar en el sueño con K nodos por ciclo.
- Cuarentena reversible.
- Los `manual` intocables (ya garantizado por el cambio 1, `7e1eb9c`).
- Agujas del par que no dependen del resto del corpus.
- Prueba en cuatro idiomas.
