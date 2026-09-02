# Scouting Report — MemoryBioRAG (v30.1)

**Fecha de evaluación:** 2026-09-02
**Objeto evaluado:** https://github.com/dennysjmarquez/MemoryBioRAG
**Tipo de auditoría:** Revisión técnica + análisis de adopción ("cazatalentos")
**Veredicto corto:** Talento real, contrato dudoso. **Adoptable como prototipo/investigación local, no como dependencia de producción hoy.**

---

## 🔁 Revisión 4 — Snapshot QA 921 ya publicado (commit `bad3d16`): el lazo de reproducción externa se cerró ✅

El autor hizo lo que faltaba para la venta/patrocinio: **publicó el snapshot congelado** de la suite QA.
- **Cambio:** `.gitignore` ahora permite `snapshots/qa_escape_qcr_20260811.db` (48 MB); el resto de `snapshots/*` sigue ignorado.
- **La DB personal sigue intacta y sigue en el repo:** `MemoryBioRAG_Data/memory_biorag.db` (60.8 MB) no se tocó, tal como pediste para tu backup.
- **Verificado desde clon fresco (`bad3d16`):**
  - Snapshot presente: 866 nodos / 45 tablas, JSONL con 921 casos.
  - `pytest tests/` → **57 / 57**.
  - Arnés QA corriendo contra el snapshot: subset de 8 casos → **100% R@1 / R@5**, usando una copia temporal aislada (`memory_biorag_qa_temp.db`, sin tocar la DB real).
- **Impacto:** un evaluador externo ya puede **reproducir los "921 casos"** sin usar la DB personal. Este era el punto que más frenaba el "vale la pena".

**Se mantiene pendiente (para producción/venta, no para evaluar):**
1. Sacar/sanitizar la DB personal del repo antes de mostrarla a terceros (decisión tuya: "aún no").
2. Sincronizar GitHub Releases (última sigue v4.0 aunque tags van a v30.1).
3. Benchmark 0-overlap contra embeddings densos reales (HuggingFace siguió bloqueado en el informe comparativo: S4 usó TF-IDF, no un dense real).
4. Gate QA en verde (CHANGELOG reconoce R@5 95.66% vs 97.39% oficial).
5. Cerrar la regresión de `typo`/`variante_gramatical` (hipótesis documentada, aún sin validar).

---

## 🔁 Revisión 3 — Cambios del 2026-09-02 (commit `876ff7e`): el bloqueo de reproducibilidad quedó resuelto ✅

Bajé el repo por tercera vez y re-verifiqué con un **clon fresco** (`876ff7e`), entorno limpio y siguiendo el material publicado del repo.

### Resultado real en clon limpio
```bash
git clone https://github.com/dennysjmarquez/MemoryBioRAG.git /tmp/mbr_fresh2
cd /tmp/mbr_fresh2
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```
→ **57 / 57 PASSED** ✅ (antes: 38/19 en la revisión 1 y 56/1 en la revisión 2).

Smoke test `SQLiteMemoryBioRAG` (guardar + `buscar_por_frase`): **ya no crashea por `omw-2.0`** ✅. La búsqueda antigua del error de WordNet deja de ser un bloqueo de entrada.

### Lo que arreglaron en esta ronda
| Cambio | Estado | Impacto |
|---|---|---|
| `mcp>=1.0.0,<2` en `requirements.txt` e `install.py` | ✅ | Era el único "1 failed" restante. Con MCP 1.29.1 la suite pasa completa. |
| `pyproject.toml` | ✅ | Ahora `pip install -e .` funciona y crea los entry points `biorag` / `biorag-mcp`. Verificado. |
| `.github/workflows/ci.yml` | ✅ | CI en 3 versiones de Python (3.10/3.11/3.12), pytest + invariantes + Concept Hub. |
| `.env.example` v30.1 | ✅ | Incluye `BIORAG_QCR_*`, `BIORAG_ORDEN_MONOTONICO`, etc. |
| Aliases de categorías en `core/memory_store.py` | ✅ | Mitiga el desfase del CLI (`proyecto`, `leccion`, etc.). |

### Resumen con puntaje actualizado
- **Reproducibilidad desde cero:** `4/10 → 8/10` (clon limpio 57/57; tras `bad3d16`, los "921 casos" ya también son reproducibles desde el clon porque el snapshot QA quedó trackeado).
- **Empaquetado:** `2/10 → 6/10` (ya hay pyproject + CI; falta release oficial sincronizada).
- **Veredicto general no cambia:** sigue siendo **investigación/prototipo**, no dependencia de producción. Pero ahora el arranque no muere en la instalación; ese era el principal bloqueo funcional.

### Lo que sigue pendiente (no crítico para instalar, crítico para adoptar)
1. **Sincronizar GitHub Releases**: los tags llegan a v30.1 pero la última release publicada sigue siendo v4.0 (mayo 2026).
2. **Separar/sanitizar la DB personal** (`MemoryBioRAG_Data/memory_biorag.db`, 60.8 MB) del repo público — sigue siendo el riesgo de privacidad más grande.
3. **Validación externa de benchmark** contra Mem0/Zep/Letta/Cognee en datos estándar.
4. **Benchmark 0-overlap contra embeddings densos reales** (en el informe comparativo S4 se usó TF-IDF; HuggingFace siguió bloqueado).
5. **Reducir el monolito** (`core/memory_store.py` 6.574 líneas) y hacer que las capas experimentales no toquen el camino de recuperación estable.

---

## 🔁 Reevaluación previa (revisión 2) — crash de `omw-2.0` resuelto, quedaba el pin de `mcp`

El autor re-subió el repo con cambios orientados al hallazgo de *Reproducibilidad rota de cero*. Re-cloné un clon fresco desde `origin/master` (commit `412dc17`) en un entorno limpio y re-verifiqué. Esto fue lo que cambió y lo que **todavía** faltaba.

### Lo que se arregló ✅
| Punto reportado antes | Estado ahora | Evidencia |
|---|---|---|
| `buscar_por_frase` crasheaba con `LookupError: omw-2.0 not found` | **Arreglado** | `core/clasificador_wordnet.py` ahora envuelve `wn.synsets(..., lang='spa')` en try/except y degrada a WordNet/inglés. Un smoke test con `SQLiteMemoryBioRAG` (guardar + `buscar_por_frase`) **ya no crasha**. El intento de descarga de `omw-2.0` imprime error de red pero lo traga y sigue. |
| `nltk` sin pin | **Arreglado** | `install.py` ahora instala `nltk>=3.8,<3.10`. |
| `requirements.txt` incompleto | **Parcialmente arreglado** | Añadieron `pydantic>=2`, `nltk>=3.8,<3.10`, `mcp>=1.0.0`, `python-dotenv>=1.0.0`. |
| README/CHANGELOG desactualizados | **Mejorado** | README pasó a v30.1, CHANGELOG añade v29.2 y la nota honesta de la regresión v30.0→v30.1. Test unitario declarado: 56/56. |

### Lo que seguía roto (revisión 2)
En un entorno limpio, siguiendo `requirements.txt` tal cual estaba publicado:

```
pytest tests/
```
→ **56 passed, 1 failed** (no 56/56 ni 57/57 como prometen los docs).

- **Causa:** `requirements.txt` declaraba `mcp>=1.0.0`, **sin límite superior**. `pip install -r requirements.txt` instalaba **`mcp 2.x`**, y el código (`mcp_server.py:552`, y por herencia `tests/test_memory_core.py`) importa `from mcp.server.fastmcp import FastMCP`.
- El paquete `mcp 2.x` renombró esa API a `MCPServer` y **rompe la importación** con el mensaje explícito: *"This is mcp 2.x... pin 'mcp<2' to keep running v1 code."*
- **Evidencia empírica:** con `mcp 1.29.1` (`mcp>=1.0.0,<2`) el mismo clon daba **57/57 PASSED**.
- Quiere decir que el fix **estaba a un pin de distancia**, y en la revisión 3 ya se aplicó.

### Evidencia reproducible (revisión 3, la nueva)
```bash
# Clon fresco (commit 876ff7e), env limpio
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt

python -m pytest tests/ -q          # → 57 passed, 0 failed
pip install -e .                    # → OK (pyproject.toml)
biorag --help                       # → OK (entry point)
```
A continuación sigue el informe original completo.

---

---

## 0. Ficha técnica rápida

| Campo | Dato |
|---|---|
| Producto | BioRAG / MemoryBioRAG — memoria cognitiva biomimética para agentes de IA |
| Versión del repo | v30.1 (`VERSION` y README; pyproject `30.1.0`) |
| Licencia | Apache-2.0 |
| Lenguaje / stack | Python 3 + SQLite (FTS5, WAL) + NumPy + NLTK WordNet (OMW) |
| Dependencias ML densas | 0. No usa torch/sentence-transformers/GPU ni APIs externas en el camino de recuperación |
| Integración | MCP (Model Context Protocol) — servidor con ~34 tools |
| Tamaño medible del repo | ~45,450 líneas de Python; `core/memory_store.py` = 6,574 líneas; `mcp_server.py` = 4,034; `test_memory.py` = 2,344 |
| Datos | DB live de 993 nodos, 47 tablas, ~18,387 sinapsis, 13 dimensiones, 17 Concept Hubs, 119 bridges, 6,490 términos de dominio |
| Benchmark reportado (interno) | R@5 95–96 %, R@1 86–88 %, MRR ~0.90, FP 0/40 en controles negativos |
| Estado en GitHub | 8 estrellas, 1 fork, 0 issues visibles, última **release publicada: v4.0 (mayo 2026)** aunque los tags llegan a v30.1 |
| CI / paquete | ✅ `pyproject.toml` + GitHub Actions (3.10/3.11/3.12) + entry points `biorag`/`biorag-mcp`. Sin Dockerfile. |
| Reproducibilidad (verificada) | ✅ `pip install -r requirements.txt` + `pytest tests/` → **57/57** en clon limpio |

---

## 1. ¿Qué es el sistema?

**En una frase:** BioRAG es una *memoria externa* para agentes de IA que se guarda en SQLite y recupera por señales híbridas (léxicas, vectoriales locales, dimensionales, sinápticas y temporales), en lugar de usar embeddings de un modelo preentrenado.

**Su posición en el campo:** vive en la intersección de Retrieval clásico, grafos de conocimiento y arquitecturas cognitivas. No es un LLM, no "piensa": es el **cuaderno de notas con indexación semántica** que un agente consulta. En sus propios términos: *"BioRAG no piensa. El agente piensa."* El agente debe descomponer la pregunta; BioRAG aporta el recuerdo.

**Qué lo hace distinto:**
- Motor vectorial propio (PPMI + SVD de 100 dimensiones + retraining de grafo) entrenado en el corpus local.
- SDM/HDC (Sparse Distributed Memory, Kanerva) de 2048 bits.
- Grafo de sinapsis con LTP/LTD, propagación, clustering (la "Hormiguita") y una "Red por Defecto" (DMN) que reflexiona en segundo plano.
- Concept Hubs con 5 ángulos cognitivos para resolver el **"abismo léxico"**: cuando la consulta y el recuerdo no comparten **ni una sola palabra**.
- Calibración conforme (Vovk) para control de falsos positivos.
- Todo en CPU, sin GPU, sin APIs de embedding, con Apache-2.0.

**Interpretación del scouter:** es una idea científicamente ambiciosa y bien documentada, implementada con mucho esfuerzo, pero presentada como "sistema de producción" cuando por evidencia es más un **laboratorio maduro de diseño de memoria** que un producto adoptable.

---

## 2. Fortalezas (sus mejores herramientas)

### 2.1 El "abismo léxico" es un diferencial real, no marketing
El informe comparativo interno (`INFORME_COMPARATIVO.md`) hace la afirmación más honesta del repo:

| Sistema | Casos 0-overlap (metáfora pura) |
|---|---|
| Léxico puro | 0 % |
| BioRAG sin capa semántica v29.1 | 0 % |
| TF-IDF / retriever vectorial offline | 0 % |
| **BioRAG-full** | **80 % (4/5)** |

En recuperación general el sistema *no* supera a un baseline léxico (incluso le cede ~5 pts en R@5). Pero en el caso donde **no hay solape de palabras**, los alternatives clásicos caen a 0 y BioRAG resuelve 4/5. Ese es su verdadero y diferenciador valor.

### 2.2 Footprint mínima y control de infraestructura
- Regex de dependencias: `numpy`, `nltk`, `fastapi`, `uvicorn`, `pydantic`, `mcp`, `dotenv`.
- Sin torch, sin GPU, sin servicio externo de embeddings.
- SQLite WAL + FTS5: es la misma base de datos, el índice y el grafo. Un solo archivo.
- Ideal para **memoria local por usuario** en agentes corriendo dentro de un IDE / sandbox.

### 2.3 Integración MCP amplia
~34 tools (`biorag_recordar`, `biorag_aprender`, `biorag_feedback`, `biorag_vincular`, `biorag_consolidar`, `biorag_oraculo_*`, etc.) y un instalador (`install.py`) que configura OpenCode, Claude Code/Desktop, VS Code, Cursor, Cline y Antigravity. Para un agente que quiera memoria persistente sin salir del entorno, es un buen punto de partida.

### 2.4 Cultura de experimentación y honestidad metodológica
- `EXPERIMENTS.md` documenta hipótesis **descartadas** (PPR, FCA, JSD, Bayesian BM25, etc.). Esto es raro y valioso.
- `CHANGELOG.md` confiesa una regresión abierta vs baseline, calibración vencida, y dataset ruidoso en `sinonimo`.
- El sistema tiene una suite QA grande (921 casos, 9 categorías), tests pytest (~57), y benchmarks reproducibles de formas que muchos repos OS no tienen.
- `docs/` contiene auditorías profundas y planes con hipótesis de causa raíz.

### 2.5 Arquitectura "todo-en-uno" para un caso de uso específico
Para un **agente personal** que necesita recordar "lo que aprendí en mi proyecto" con poco hardware, BioRAG resuelve el problema sin salir de Python/SQLite. El modelo de "caballo de trabajo" con LTP/LTD, DMN y Concept Hubs es más rico que guardar texto + texto en un vector DB.

---

## 3. Debilidades (sus fallas o limitaciones)

### 3.1 Ya es paquete (pyproject + CI) y el snapshot QA ya es reproducible, pero aún no es "release consumible"
**Mejoró mucho desde la revisión 1:** hay `pyproject.toml`, GitHub Actions, entry points (`biorag`, `biorag-mcp`), `pip install -e .` funciona, la suite pasa 57/57 en clon limpio y —tras `bad3d16`— el snapshot `snapshots/qa_escape_qcr_20260811.db` ya viaja con el repo **para reproducir los 921 casos**. Lo que **no cerró**: sigue sin ser una release formal consumible por terceros (los tags van a v30.1 pero la **última release en GitHub sigue siendo v4.0, mayo 2026**) y `scripts/snapshot_prf_real.db` sigue sin trackear.

### 3.2 La "dependencia ML 0" ya no muere en instalación, pero sigue sin ser 100% offline
**Arreglado desde la revisión 2/3:** `python -m pytest tests/` ya da **57/57** en entorno limpio, y `SQLiteMemoryBioRAG(...).buscar_por_frase(...)` **ya no crashea** por `omw-2.0`; el clasificador WordNet degrada con gracia a WordNet/inglés. Lo que **queda**: el repo solo incluye `omw-1.4` + `wordnet` (no `omw-2.0`), la parte de "lexnames" multilingüe más profunda sigue sin funcionar offline, y en mi smoke test las queries devolvieron `total=0` en una DB de 3 nodos recién guardados porque necesitan pasar por consolidación para indexación profunda; en la práctica "local-first sin descarga" funciona, pero con menos capacidad multilingüe que la que proclama el README.

### 3.3 Riesgo de datos: se subió la DB de memoria personal
`MemoryBioRAG_Data/memory_biorag.db` (60.8 MB) está **versionada en GitHub**. Contiene ~993 nodos con perfil personal de Dennys, historial de agentes, estilo de escritura, caminos locales, referencias a emails, proyectos y conversaciones. Es una **fuga de privacidad / anti-pattern** seria para un proyecto open source. Además `memory_biorag.db` (0 bytes) también está trackeado en la raíz, duplicando ruido.

### 3.4 Deuda de mantenimiento estructural
- `core/memory_store.py` = 6,574 líneas; `mcp_server.py` = 4,034; `dmn_reflexion.py` = 2,132.
- 130 `except Exception`, 98 `pass`, 188 `print`, ~14 `TODO/FIXME`.
- Mezcla de español/inglés, acentos en nombres de archivo, 100+ MB de `docs/`, un `arena_negativos_fix.patch` de 50 KB committeado, `legacy_hubs_para_convertir.json` de 1 MB.
- Muchos mecanismos (26+) están "apagados por defecto" o en evaluación; hay doble camino `biorag` / `mcp_server`, `test_memory.py` y `tests/`.
- `biorag.py` documenta categorías en minúsculas (`proyecto`, `leccion`) que el resolver de la DB v30.1 **no acepta** (acepta `Project`, `Lesson`, `Principle`...). El CLI está desfasado del motor.

### 3.5 Benchmark: fuerte, pero autoevaluado y en regresión
Los números estrella (0 % FP, 5/5 Concept Hub, 97.39 % R@5) son **mediciones internas** sobre una DB de una sola persona, no validadas por un tercero ni comparadas con Mem0/Zep/Letta/Cognee en datos estandarizados. Además `CHANGELOG.md` reconoce que el R@5 global cayó a **95.66 %** frente al baseline oficial de **97.39 %**, con `typo` bajando de 98.46 % a 89.23 % — y admite que **el gate quedó en rojo deliberadamente** hasta resolver la causa. Es honesto, pero significa que en este release **no** hay garantía de performance estable.

### 3.6 Algunas afirmaciones del README no se verifican tal cual
- Los count de tests ya son coherentes en el clon limpio (**57/57**), pero sigue siendo una **suite autoevaluada** y el README mezcla cifras de distintas corridas (34/56/57).
- "Modelo de producción con ~20MB RAM y 2.84ms" vs benchmark propio de 0.96s–1.26s por query; ambas métricas pueden ser ciertas en condiciones distintas, pero la doc no delimita.
- `.env.example` ya fue actualizado a v30.1 con `BIORAG_QCR_*` y `BIORAG_ORDEN_MONOTONICO`; aún convendría unificar las variables reales del motor con `AGENTS.md`.

### 3.7 No escala a multi-usuario / producción comercial
- Un solo SQLite con un usuario, sin tenancy, sin auth, sin operaciones de contradicción, sin versionado temporal de hechos.
- El propio "modelo mental" exige que el agente descomponga la query; si el agente no razona bien, el retriever devuelve 0 resultados aunque el conocimiento exista.
- El manual de uso del README es condicional: depende del sistema de prompts del LLM, no del motor.

---

## 4. El Veredicto del Cazatalentos

**Pregunta directa:** ¿Vale la pena invertir tiempo/dinero en este sistema?

### Verdicto por perfil de inversión

| Perfil | ¿Vale la pena? | Por qué |
|---|---|---|
| **Investigar / aprender diseño de memoria biomimética** | ✅ SÍ | Es un proyecto con ideas de primer nivel (13 señales, SDM/HDC, PPMI+SVD local, Concept Hubs, conformal calibration), documentación de experimentos y una implementación asombrosamente completa para un solo autor. |
| **Prototipo personal / agente local sin GPU, en español** | ⚠️ CONDICIONAL | Ya no hay error inicial por NLTK ni falta CI/paquete; sigue siendo válido si aceptas la DB personal del repo sin separar y un benchmark autoevaluado. |
| **Dependencia en producción (startup/equipo)** | ❌ NO | Aunque ya hay pyproject, CI, tests 57/57 y snapshot QA reproducible, sigue sin haber release oficial sincronizada, validación de terceros del benchmark ni separación de la DB personal. Mem0, Zep, Letta o Cognee tienen más madurez y ecosistema. |
| **Sistema multi-usuario con temporalidad/contradicciones** | ❌ NO | BioRAG no resuelve invalidación temporal, contradicción, copias multi-tenant ni ciclo de vida de hechos. Ese mercado ya está cubierto por Zep/Letta/Cognee. |

**Score del scouter (1–10) tras los cambios de hoy:**
- Originalidad técnica: **9/10**
- Implementación como laboratorio: **8/10**
- Viabilidad como producto: **4/10** (sube por pyproject + CI)
- Reproducibilidad: **9/10** (57/57 en clon limpio + snapshot QA 921 ya publicado)
- Seguridad/privacidad de datos: **3/10** (DB personal aún versionada)
- Mantenibilidad: **4/10**
- Competitividad frente a la categoría: **3/10**
- **Potencial futuro:** **6.5/10** — alto si se convierte en librería investigable, bajo en su estado actual.

### La conclusión de una línea

> **MemoryBioRAG es un proyecto de investigación genuinamente fascinante con una ventaja diferencial demostrada en búsquedas sin solape léxico; pero hoy es la demostración que mantiene un autor con una DB personal y un conjunto de métricas autocontadas, no una dependencia battle-tested. Vale la pena **estudiarlo** y, si te encaja el caso de uso local-personal, **probar su motor**; **no** vale la pena **adoptarlo como plataforma de producción** hasta que se resuelvan privacidad, reproducibilidad, empaquetado y evaluación independiente.**

### Qué debería hacer el autor para que pase de "prototipo interesante" a "vale la pena invertir"
1. **Eliminar la DB personal del repo** y publicar un snapshot sintético/sanitizado separado. *(Sigue siendo el hallazgo de seguridad #1.)*
2. **Publicar el snapshot QA real** (`snapshots/qa_escape_qcr_20260811.db` o su reemplazo), que hoy está gitignoreado. Con los 57 tests ya verdes, esto cerraría también la reproducibilidad de los "921 casos".
3. **Sincronizar GitHub Releases con los tags** (v30.1) y añadir un `release.yml` automático.
4. **Cerrar el gate QA en verde**: hoy el CHANGELOG admite R@5 95.66% vs baseline 97.39% y el gate quedó rojo a propósito. Hasta no validar la causa raíz de la regresión de `typo`/`variante_gramatical`, "estable" es condicional.
5. **Añadir comparación estándar**: LOCOMO o suite pública con Mem0/Zep/Letta/Cognee, no solo baseline interno.
6. **Separar capas**: biblioteca estable + módulo experimental (DMN, ADN, SDM detrás de flags), para que el core sea estable.
7. **Reducir el monolito**: `core/memory_store.py` (6.574 líneas) es el mayor riesgo de mantenimiento y el mayor freno para contribuciones externas.
8. **Decidir el posicionamiento**: si quiere ser "Memoria local explicable sin ML denso", debería empaquetarse como plugin ligero para agentes; si quiere ser "RAG semántico", está compitiendo en un mercado brutal.

> Nota: los puntos 3–4 que en la revisión 1 parecían "falta de instalación" hoy ya están resueltos (pyproject + CI + mcp<2). El progreso real del día fue de "no arranca de cero" a "arranca de cero y pasa la suite".

---

## Referencias externas usadas para posicionar la categoría
- [Top 6 AI Agent Memory Frameworks (2026) — DEV Community](https://dev.to/thedailyagent/top-6-ai-agent-memory-frameworks-for-devs-2026-1fef)
- [Mem0 vs Letta vs Zep: Agent Memory 2026](https://aiworkflowlab.dev/article/agent-memory-mem0-vs-letta-vs-zep-2026)
- [Best AI agent memory tools in 2026 — Braintrust](https://www.braintrust.dev/articles/best-ai-agent-memory-tools-2026)
