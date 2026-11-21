# NORMA MÁXIMA, INVARIANTE Y BLOQUEANTE DEL PROYECTO

## Estabilidad de resultados frente al crecimiento del corpus

> **Esta norma es la puerta de decisión obligatoria de mayor prioridad del proyecto.** Ninguna decisión de diseño, algoritmo, cambio de datos, optimización, evaluación o publicación puede aprobarse ni darse por validada sin definir y verificar cómo preserva esta invariancia.

Para cada algoritmo se debe especificar el tamaño del corpus `N`, la consulta y configuración relevantes, y qué datos nuevos son irrelevantes para el caso evaluado. Si `D` es el corpus, `q` la consulta e `I` contiene solo información irrelevante para `q`, el resultado debe permanecer igual —o dentro de una tolerancia numérica definida **antes** de medir— al crecer el corpus:

`F(D, q) = F(D ∪ I, q)`

La comparación debe mantener constantes la versión, los parámetros y la semilla aleatoria, cuando exista. Antes de aceptar un algoritmo o cambio, se probará con un corpus de referencia y otro ampliado con datos irrelevantes; cualquier diferencia no prevista bloquea la decisión hasta que se explique, corrija o se documente y autorice explícitamente el alcance aplicable. No se puede relajar el criterio después de ver los resultados.

Esta invariancia no exige respuestas idénticas cuando el corpus incorpora información **pertinente**: en ese caso el resultado puede y, si la evidencia lo justifica, debe cambiar. La exigencia es que el tamaño por sí solo, el orden de almacenamiento u otros cambios declarados irrelevantes no alteren la salida. La reproducibilidad para entradas y condiciones idénticas también es obligatoria.

El costo computacional es un requisito separado: cada algoritmo debe declarar y medir su objetivo de complejidad respecto a `N`. `O(1)` describe costo, no invariancia ni corrección, y no se prometerá si la tarea no lo permite. Si no se puede definir o verificar el contrato de invariancia y sus pruebas, la decisión queda **BLOQUEADA**: no implementar, aprobar, integrar, publicar ni afirmar validación hasta resolverlo o recibir autorización explícita para una excepción de alcance.

---

# BioRAG — Definitive Agent Field Manual & Master Operating Instructions

> **To any agent reading this**: You are stepping into **MemoryBioRAG**, a bio-inspired, mathematically pure associative memory engine. It is engineered to surpass traditional vector RAG *without* pre-trained deep neural embeddings, *without* external API calls, *without* GPUs, and running 100% locally on CPU via graph theory, linear algebra, and hyperdimensional computing.
>
> Read this document completely before touching any code. It is designed so that you can achieve 100% operational mastery from your very first step.

## Regla obligatoria: identidad DEV y cabecera de README

- `dennysjmarquez/MemoryBioRAG` es el repositorio principal de desarrollo (DEV); no debe presentarse como el canal de distribución estable.
- En el `README.md` raíz, mantener inmediatamente después del título la versión de trabajo vigente y un resumen breve y preciso de sus características. Ese bloque debe permanecer por encima de benchmarks, resultados históricos y detalles de versiones anteriores; actualizarlo cuando cambie la versión o el alcance real del código.
- Mantener visible, junto a la introducción, un aviso profesional en español que identifique este repositorio como DEV y enlace al repositorio estable canónico: `https://github.com/dennysjmarquez/MemoryBioRAG-Stable`.
- Al actualizar versiones, distinguir claramente la versión de desarrollo de versiones estables publicadas. Actualizar las referencias que describan el estado actual, pero conservar los resultados históricos con la versión, corpus, entorno y fecha realmente medidos. Nunca trasladar métricas antiguas a la versión actual ni dar a entender que una candidata local ya fue publicada.
- Para publicar en `MemoryBioRAG-Stable`, seguir el procedimiento del README raíz. Se permite preparar y auditar artefactos locales; ningún agente puede hacer push, crear tags, crear un GitHub Release ni subir a PyPI sin autorización explícita del dueño del proyecto.

---

## 0. The Inventor's Attitude (guiding principle)

> **"Nada es 'imposible', solo 'todavía no medido'. Y si algo falla, busco otro camino, no me rindo."**
> *Nothing is "impossible", only "not yet measured". If something fails, find another way; never give up.*

This is the attitude every agent must bring to this project, above any technique (see `CONSTITUTION.md` §0):
- **Never close an idea with "impossible" or "it can't be done".** State what is missing instead: data, a measurement, or a signal ("needle") that does not exist yet.
- **A failed attempt is reverted, the goal is not.** Zero regressions still rules: a change that lowers any metric is reverted. That closes *that path*, not the objective. Record why it failed and look for another way.
- **Ambition stands on evidence.** Do not argue the goal; prove every step with verifiable output.

---

## 1. System Thesis & Architectural Philosophy

MemoryBioRAG is **not** a wrapper around OpenAI, LangChain, or SentenceTransformers. It models biological neocortical and hippocampal memory dynamics:
- **Heptadic Multi-Signal Retrieval**: Combines exact/fuzzy lexical matching (FTS5 BM25), co-occurrence latent space (PPMI+SVD 100-dim), 13 topological semantic dimensions, hyperdimensional associative memory (SDM 2048-bit), and synaptic graph activation.
- **Epistemic Conformal Certainty (v28.1)**: Uses split conformal prediction (Vovk, 2005) to calibrate a mathematical false-positive (FP) guarantee as a dynamic percentile, not an arbitrary hardcoded threshold.
- **Autonomous Sleep Cycle & DMN**: Background daemons consolidate short-term memories into long-term structures, prune dead synapses, and form associative abstractions during idle periods (La Hormiguita).
- **Universal & Domain-Agnostic**: Designed for anyone (a physician, attorney, researcher, student) who downloads and runs it out-of-the-box without needing to be a software engineer.

---

## 2. Invariants & Operating Methodology (Arcadia Protocol)

These rules are **immutable** and must guide every decision you make:

### Invariant 1: UX-First Universal Design ("Antes de construir, justifica")
Before writing a single line of new code or proposing a feature, you must answer:
1. **Who uses it?** Assume the end-user is *not* a programmer. They will not edit code, tweak JSON files, or configure obscure environment variables. If a feature is "default-OFF" and invisible to a standard user, it provides zero real-world value.
2. **Does another natural path exist?** If the user's natural workflow (e.g. intuitive synonyms when saving a memory) or existing mechanisms solve the issue, **do not build new code**.
3. **Is it worth the technical weight?** All new code is debt.
4. **STRICT PROHIBITION**: **NEVER** hardcode domain vocabularies, dictionaries, or project-internal terms into the engine. The system must remain 100% domain-agnostic.

### Invariant 2: One Change at a Time (Rule 13)
Never test multiple hypotheses or changes simultaneously. Isolate each change, measure Before vs After, and record exact metrics. If any metric regresses: **IMMEDIATE REVERT**.

### Invariant 3: Visible Failures (Rule 12)
Missing data, unindexed tokens, or database discrepancies must fail visibly with clear exceptions and descriptive logs. **Never** return silent defaults (such as `0.0`, empty arrays, or fallback nulls) that can masquerade as valid zero-score results.

### Invariant 4: No Prose Without Concrete Output
Never report assumed, simulated, or expected numbers as verified facts. Every claim of success, improvement, or regression must be proven with verbatim command outputs (diffs, benchmark summaries, pytest runs).

### Invariant 5: Dual Verification Discipline
Verifying a fix against the frozen snapshot is **NOT** enough.
1. **Snapshot** (`snapshots/qa_escape_qcr_20260811.db`): Verifies mathematical regression against historical baselines.
2. **Live DB Copy** (via `sqlite3.backup()`): Verifies real-world resolution against the active, mutating production corpus.
*If a fix passes on the snapshot but fails on the live copy, it is NOT resolved.*

### Invariant 6: Modular, Decoupled, Hexagonal (golden rule — `CONSTITUTION.md` Pilar 9)
Nothing monolithic. Every piece (engine layer, neuron, validator, language adapter) lives in its own module with one clear responsibility and talks to others through a small explicit interface. Coupling is harmful: if one piece breaks, everything coupled to it breaks. Keep the brain's domain logic at the center; DB, MCP, dictionaries, languages and neurons are pluggable **ports and adapters**. Decoupling existing code is its own measured change.

### Invariant 7: Document Why (golden rule — `CONSTITUTION.md` Pilar 10)
Every piece records **what problem it solves, why at that point, and which measurement approved it**. Every removed or disabled piece records **why it was removed**, with evidence. Write so that a non-technical human and any future AI can understand it. If it is not in the repo, it is lost.

### Invariant 8: Every Neuron Has a Floor, a Ceiling and Guardians (`CONSTITUTION.md` Pilar 11)
No neuron enters the engine without a **floor** (the hand formula stays the guaranteed minimum), a **ceiling** (maximum it can move), **guardians** (checks that switch it off when something does not match) and its own **exam**. Empty-DB safe, constant time, it only **adds** on top of the ranking. The engine's first neuron is the model.

---

### Invariant 9: Useful Noise Is Never Killed (golden rule — `CONSTITUTION.md` Pilar 12)
- **Neurons (re-ranking, reasoning) only ORDER.** They never remove, filter or empty the result list.
- No engine or MCP change may strip the related / similar memories that come with the best one, even if a single-query metric goes up. A change that shortens the list must prove, by measurement, that the cue memories are kept.
- A "don't know" never empties the list: the brain says how close it is (`nivel_certeza`, knowledge-gap warning) and still shows the similar memories.
- **Why:** BioRAG is a brain, not a search engine. Agent + brain are one mind: the agent tries to recall, the brain returns similar memories, and those bring cue words for the next search (pattern completion). That "noise" is the thread that leads to the memory. Kill it and the system becomes blind — an ordinary search engine.

### Invariant 10: A Living System: Foster What Emerges (guiding focus — `CONSTITUTION.md` Pilar 13)
- BioRAG is built as an **organism**, not a rule machine: place a piece and let usage, the agent, sleep and time shape the rest. It has already shown behavior nobody dictated: memory **islands** that formed on their own and faded when the graph saturated, memories that fall asleep and wake up when recalled, synapses born from use.
- **Every change must foster such behavior emerging naturally (adaptive, evolutionary) instead of imposing it by hand.** Prefer simple local rules over global hand-written orders. Keep catalogs open but legible. Give every emergent mechanism homeostasis so it survives 10× growth. It must emerge from each DB's own data, starting from an empty DB. Observe and measure before using it, and never delete it just because it isn't understood yet. Emergent signals go to association/cues first; they reach ranking only with measurement and Dennys's OK.
- Mandatory question: *does this let the behavior emerge, or impose it by hand? Does it stay alive when memory grows 10×?* All other invariants still apply.

## 3. The Search Pipeline Anatomy (`core/memory_store.py`)

All retrieval through `buscar_por_frase` flows through three deterministic phases:

```
Query Entrada
    │
    ▼
[FASE 1: Generación de Candidatos]
    ├── 1.1 FTS5 Exacto (concepto + sinonimos)
    ├── 1.2 Escape QCR (si score < 0.60 o pool vacío → relajación OR)
    └── 1.3 Expansión Sináptica BFS (recorre aristas de `sinapsis` hasta N saltos)
    │
    ▼
[FASE 2: Scoring Híbrido Multi-Señal (_calcular_score_hibrido)]
    ├── BM25 / FTS Rank (~0.25)
    ├── PPMI + SVD 100-dim Cosine (~0.15)
    ├── 13 Ejes Semánticos / Jaccard dimensional (~0.14)
    ├── Peso Sináptico Hebbiano (~0.10)
    ├── Concepto & Sinónimos Ratios (~0.16)
    ├── SDM / HDC 2048-bit Overlap
    ├── Hub Matching & Predicados SRL
    └── Reranking Jaccard léxico final
    │
    ▼
[FASE 3: Calibración Conforme & Certeza Epistémica]
    ├── Umbral Conforme Dinámico (Percentil adaptativo según tamaño de corpus)
    └── Clasificación en 3 Niveles:
          • 'evidencia_directa' (Score ≥ umbral)
          • 'relacionado_confianza_media'
          • 'sin_evidencia_directa'
```

---

## 4. Codebase Navigation Map

The core engine is largely centralized in `core/memory_store.py` (~7,500 lines). Do not get lost; use this functional index:

| Component / Function | Line Range (Approx.) | Purpose |
|----------------------|----------------------|---------|
| `SQLiteMemoryBioRAG.__init__` | ~L150 - L450 | Database bootstrap, table schema creation, FTS5 virtual tables, PRAGMAs. |
| `guardar` / `aprender` | ~L1800 - L2150 | Memory ingestion: dimensional encoding, synonym storage, synaptic link triggers. |
| `vincular` / Hebbian updates | ~L2400 - L2700 | Graph edge creation, weight updates, reinforcement via activation. |
| `_calcular_score_hibrido` | ~L3660 - L3760 | The multi-signal scoring equation balancing BM25, PPMI, dimensions, and graph. |
| `nivel_certeza` & Calibración | ~L4200 - L4350 | Conformal prediction percentile, Platt scaling, Neocortex certainty labeling. |
| `buscar_por_frase` | ~L4770 - L5500 | Main retrieval pipeline: candidate generation, BFS graph expansion, ranking. |
| Daemons & Consolidation | ~L6000 - L7499 | Short-term to long-term memory consolidation, episodic cleanup, DMN hooks. |

### Auxiliary Core Modules (`core/`)
- `core/sinapsis.py`: Pure graph data structures, topological distance, triadic closure.
- `core/ppmi_vectorizer.py`: PPMI co-occurrence matrix generation, SVD dimensional reduction (100 dims), retrofitting.
- `core/ppmi_hybrid_search.py`: Fast cosine similarity on local latent space.
- `core/sdm.py`: Sparse Distributed Memory (Kanerva, 1988) with 2048-bit hyperdimensional binary vectors.
- `core/calibracion.py`: `UmbralConforme` and `CalibradorPlatt` statistical guarantees.
- `core/dmn_engine.py` & `core/dmn_reflexion.py`: Default Mode Network background sleep reflection.

---

## 5. Database Schema Reference (SQLite)

### Table: `largo_plazo` (Primary Long-Term Memory)
- `id` (INTEGER PRIMARY KEY)
- `concepto` (TEXT): Canonical identifier/title of the node.
- `contenido` (TEXT): Full memory content / descriptive payload.
- `peso_sinaptico` (REAL): Base Hebbian strength [0.0 - 1.0].
- `estado` (TEXT): `'activo'`, `'dormido'`, `'consolidado'`.
- `asociaciones` (TEXT): Comma-separated list of related concepts.
- `sinonimos` (TEXT): Comma-separated lexical equivalents.
- `dimensiones` (TEXT): Encoded semantic coordinate string (13 axes).
- `creado_en` (INTEGER/REAL): Timestamp.

### Table: `sinapsis` (Connectome Graph Edges)
- `id` (INTEGER PRIMARY KEY)
- `origen` (TEXT): Source node concept.
- `destino` (TEXT): Target node concept.
- `peso` (REAL): Synaptic connection strength [0.0 - 1.0].
- `tipo` (TEXT): Relation type (`'asociativa'`, `'causal'`, `'temporal'`).
- `ultima_activacion` (REAL): Timestamp for Hebbian decay calculation.

### Table: `calibracion_estado` (Conformal Predictor State)
- `id` (INTEGER PRIMARY KEY, always 1)
- `umbral` (REAL): Currently calibrated FP threshold.
- `alpha` (REAL): Target significance level (e.g. 0.05 for 95% confidence).
- `n_nodos_corpus` (INTEGER): Node count at calibration time (triggers re-calibration if drift > 20%).
- `platt_a`, `platt_b` (REAL): Platt scaling calibration coefficients.

---

## 6. Curated Deep-Dive Documentation Index (`docs/`)

The `docs/` folder contains extensive research artifacts. Do not read them all at once to preserve context window. Consult them on demand:

- **For Semantic Dimensions Theory**: `docs/teoria_de_ejes_semanticos.md`
- **For PPMI+SVD Mathematical Formulation**: `docs/LEEME_ppmi_svd.md`
- **For Conformal Calibration Deep-Dive**: `docs/AUDITORIA_CALIBRACION_v28.1.md`
- **For the Lexical Abyss Challenge (EXP-Q)**: `docs/INFORME_ABISMO_LEXICO_EXPQ_v31.3.md` and `docs/analisis_pilares_abismo_lexico.md`
- **For Background Daemon & Graph Maintenance**: `docs/plan_hormiguita_mantenimiento_grafo.md`
- **For Master Project Vision & History**: `Building Human-Like Persistent Memory.md` and `docs/PLAN_MAESTRO_BIORAG_UNICO_EN_EL_PLANETA.md`

---

## 7. Execution & Benchmark Commands

Always run these commands from the repository root:

```bash
# 1. Full QA Evaluation Suite (921 frozen cases — Primary Gate):
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py

# 2. Comprehensive Unit Test Suite:
python3 -m pytest tests/ -v

# 3. Lexical Abyss Challenge (Zero lexical overlap test):
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/test_abismo_lexico.py

# 4. Safe Live DB Copy for Dual Verification:
python3 -c "import sqlite3; src=sqlite3.connect('MemoryBioRAG_Data/memory_biorag.db'); dst=sqlite3.connect('/tmp/live_copy.db'); src.backup(dst); dst.close(); src.close()"

# 5. MCP Server (Stdio communication):
python3 mcp_server.py

# 6. Background Consolidation Daemon:
python3 graph_maintenance_daemon.py
```

### Official Baseline Target (v31.3 / State B):
- **Global Recall@5**: ≥ 96.03% (Gate threshold: ≥ 97.0%)
- **Global Recall@1**: ≥ 88.76%
- **Global MRR**: ≥ 0.916
- **False Positive Rate**: Target 0.0% on negative controls

---

## 8. Common Pitfalls & How to Avoid Them

| Pitfall | Cause | Remediation |
|---------|-------|-------------|
| **Evaluating against Live DB directly** | Daemons and test scripts write to the DB. | **Always** use `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db` for official benchmarks. |
| **Solving snapshot without live verification** | Snapshot population (851 active) differs from production. | Run Dual Verification via temporary SQLite backup. |
| **Omitting `parafrasis` in searches** | Single queries lose ~60% recall on complex queries. | Always generate 3–5 diverse paraphrases in MCP search tools. |
| **Hardcoding domain terms** | Temptation to patch a single test case with a lookup dict. | **STRICTLY FORBIDDEN**. Must be resolved via graph topology, PPMI, or universal heuristics. |
| **Modifying scoring weights arbitrarily** | `_calcular_score_hibrido` weights are tightly normalized. | Re-normalize weights so total equals `1.0 - jsd_weight`; verify with complete QA eval. |
| **Committing `.db` files (any except the cortex)** or `.env.local` | Repository hygiene. The live cortex `MemoryBioRAG_Data/memory_biorag.db` is the sole exception. | Check `git status` before finishing any task. |

---

## 9. Onboarding Checklist for Incoming Agents

Before claiming readiness to tackle any new feature or fix:
1. [ ] Confirm you have read this `AGENTS.md` file.
2. [ ] Run `pytest tests/ -v` and confirm all tests pass.
3. [ ] Run `scripts/evaluar_qa.py` against the snapshot and record your baseline metrics.
4. [ ] State clearly the hypothesis and isolated change you intend to make (One change at a time).
5. [ ] Ensure your proposed solution adheres to the **"Antes de construir, justifica"** UX-first rule.
6. [ ] Read Section 10 (Pre-flight Search Protocol) and confirm you understand the mandatory search invariant.

---

## 10. Protocolo Pre-flight Search (Invariante — Spec 004)

> **🔒 REGLA INMUTABLE**: Ningún agente puede llamar `aprender` o `guardar` sin haber realizado una búsqueda previa y pasar `busqueda_previa=True`. Sin excepción. Nunca.

### ¿Por qué existe esta regla?

El corpus de BioRAG crece con cada sesión. Sin una búsqueda previa obligatoria, el sistema acumula:
- **Nodos duplicados**: el mismo concepto guardado 3 veces con nombres ligeramente diferentes.
- **Versiones fragmentadas**: "última versión" repartida en 10 nodos sin conexión entre sí.
- **Grafo huérfano**: conocimiento nuevo que no conecta con lo ya almacenado.

La búsqueda previa es la única manera de que el agente tome una decisión informada: ¿actualizo, vinculo, o creo nuevo?

### Flujo de decisión obligatorio

```
ANTES de guardar/aprender
         │
         ▼
┌─────────────────────────────┐
│  biorag_buscar / recordar   │  ← OBLIGATORIO. Sin esto, no se puede guardar.
│  (con tema o concepto)      │
└────────────┬────────────────┘
             │
             ▼
    ¿Hay resultados top-5?
             │
     ┌───────┴──────────┐
     │ SÍ               │ NO
     ▼                  ▼
¿El top-1 tiene     Crear nodo nuevo
score ≥ 0.80?       (aprender/guardar
     │               + busqueda_previa=True)
 ┌───┴────┐
 │ SÍ    │ NO
 ▼       ▼
¿El    ¿El nodo top-1
nodo   tiene mucho texto
trata  o es muy distinto?
del        │
mismo  ┌───┴────┐
tema?  │ SÍ    │ NO
 │     ▼       ▼
 │  Crear     Actualizar
 │  nuevo +   nodo top-1
 │  vincular  (actualizar
 │  con top-1  + busqueda_previa=True)
 │
 ▼
Actualizar nodo
(actualizar +
busqueda_previa=True)
```

### Tabla de decisión

| Situación | Acción correcta | Tool MCP |
|-----------|----------------|----------|
| No hay resultados relevantes | Crear nodo nuevo | `aprender` / `guardar` con `busqueda_previa=True` |
| Top-1 trata del mismo tema, score ≥ 0.80, contenido corto | Actualizar el nodo existente | `actualizar` |
| Top-1 trata del mismo tema, pero ya tiene mucho texto | Crear nodo nuevo + vincular con top-1 | `aprender` con `busqueda_previa=True, vincular_con=[top-1]` |
| Top-1 relacionado pero diferente tema | Crear nodo nuevo + vincular | `aprender` con `busqueda_previa=True, vincular_con=[top-1, ...]` |
| Actualización parcial (ej: añadir sustantivos) | Enriquecer sin sobrescribir | `agregar_sustantivos` o `actualizar` |
| Reemplazar completamente el nodo | Sobrescribir todo | `actualizar` con `sobrescribir=True` |

### Parámetros del contrato Pre-flight

```python
# ✅ CORRECTO — busqueda_previa=True declarada explícitamente
aprender(
    concepto="nueva_idea",
    contenido="...",
    bridges=[...],           # 5 ángulos obligatorios
    sustantivos_clave="...", # 2-4 sustantivos OBLIGATORIO
    busqueda_previa=True,    # 🔒 INVARIANTE — debe ser True
    vincular_con=["nodo_relacionado"],  # opcional pero recomendado
)

# ❌ INCORRECTO — se omite busqueda_previa (default=False → error inmediato)
aprender(concepto="nueva_idea", contenido="...")
# → Retorna: {"status": "error", "codigo": "BUSQUEDA_PREVIA_REQUERIDA"}
```

### Pitfalls específicos del Pre-flight

| Error | Causa | Remediación |
|-------|-------|-------------|
| `BUSQUEDA_PREVIA_REQUERIDA` en respuesta | Se llamó `aprender`/`guardar` sin `busqueda_previa=True` | Buscar primero, luego llamar con `busqueda_previa=True` |
| Nodos duplicados en el corpus | Se ignoró el top-5 y se creó nodo nuevo | Revisar top-5, decidir actualizar o vincular |
| Conocimiento sin conexiones en el grafo | Se creó nodo sin `vincular_con` | Usar `vincular_con` con los nodos relacionados del top-5 |
| Score alto en top-1 sin relación semántica real | Coincidencia de nombre (ej: `biorag_v32_1`) | El agente evalúa el contenido — si no es el mismo tema, crea nodo nuevo y vincula |

---

## Agent Skills (Ecosistema SDD)

### Convenciones

- **Fuente única**: editar skills en `.agents/skills/`; los symlinks propagan los cambios automáticamente.
- **biorag-sync**: vive en `skills/biorag-sync/` (lo escanea `install.py`); `.agents/skills/biorag-sync` es un symlink hacia ahí.
- **Formato**: cada skill es una carpeta con `SKILL.md` (frontmatter YAML: `name` + `description` obligatorios, `name` ≤64 chars, coincide con la carpeta).
- **Para agentes que no escanean ninguna ruta**: leer este archivo (AGENTS.md) es suficiente para saber dónde están las skills.

---

## 11. Publicar al Repo Público (MemoryBioRAG-Stable) — Protocolo del Agente

> **Este protocolo aplica cuando el dueño del proyecto dice:**  
> *"Quiero hacer la publicación al repo público"* / *"Quiero hacer el release X.Y.Z"* / *"Prepara el release"* / *"Voy a publicar"*.

### 11.1 Secuencia obligatoria (5 pasos, en este orden)

> 🛑 **REGLA DE ORO DE TERRITORIALIDAD:**  
> **El agente SOLO ejecuta en consola los Pasos 1, 2 y 3 (`test`, `stage_stable` y `release_stable`).**  
> Los Pasos 4 y 5 (`git push` al repo público `MemoryBioRAG-Stable`, creación de tags remotos, GitHub Releases oficiales o publicaciones a registros) tocan repositorios y canales públicos oficiales. **El agente los redacta, los prepara, calcula sus hashes de verificación y los deja en bandeja de plata, pero JAMÁS los dispara por terminal sin autorización explícita.** El lanzamiento físico lo realiza única y exclusivamente el dueño del proyecto.

```
[EJECUTA EL AGENTE]
Paso 1: pytest tests/ -v && BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python scripts/evaluar_qa.py
         → Debe pasar al 100% en tests unitarios y cumplir los umbrales de QA baseline (Recall@5 ≥ 96.03%, MRR ≥ 0.916, Falsos Positivos 0/40).
         Si falla algún check, se corrige el código fuente antes de continuar.

Paso 2: python scripts/stage_stable.py --version <tag>
         → Audita y genera el preview aislado en .staging/stable/preview/.
         El resultado debe ser READY (0 blockers). Revisa el reporte en .staging/stable/preview/report.md.

Paso 3: python scripts/release_stable.py --version <tag> --stage-dir .staging/stable/preview --confirm-tree-sha256 "$(cat .staging/stable/preview/TREE_SHA256)"
         → Empaqueta los artefactos locales verificados en .stable-release/stable/releases/.

[PREPARA EL AGENTE — LANZA EL USUARIO]
Paso 4: El agente crea o actualiza docs/releases/RELEASE-<tag>.md (en inglés pulcro; ver §11.2).

Paso 5: El usuario ejecuta en su terminal el script que hace el push atómico + crea la GitHub Release:
         $ python3 scripts/publish_stable.py \
             --version <tag> \
             --stage-dir .staging/stable/preview \
             --message-file docs/releases/RELEASE-<tag>.md
         → El script: clona MemoryBioRAG-Stable, sincroniza el árbol limpio, hace commit con
           autor canónico, crea el tag annotated, verifica identidad, hace push atómico y
           finalmente ejecuta `gh release create` con las mismas notas. UN SOLO COMANDO.
         → Si `gh` no está disponible o falla, el push YA se realizó y el script imprime el
           comando manual para crear la Release en GitHub.
         → Verificar en: https://github.com/dennysjmarquez/MemoryBioRAG-Stable/releases
```

### 11.2 Formato del archivo de release (`docs/releases/RELEASE-<tag>.md`)

**Reglas invariantes:**
- El archivo se escribe **en inglés**. Cero palabras en español (con la única excepción de nombres literales de comandos CLI o herramientas MCP como `buscar` o `recordar`, siempre en formato de código).
- El nombre del archivo usa la versión exacta: `RELEASE-v1.0.md`, `RELEASE-1.0.0.md`, `RELEASE-v36.0.md`, etc.
- El texto NO menciona nada interno: sin rutas privadas (`/mnt/...`, `~/.gemini/...`), sin nombres de ramas de desarrollo (`master`, `dev`), sin palabras como "taller", "arena", "privado".
- El formato sigue el patrón: una línea de título, un párrafo de contexto, secciones cortas y concretas (`Highlights of X.Y.Z`, `Installation & Quick Start`, `Quick Verification`, `Distribution Note`).

**Estructura del texto:**
```markdown
MemoryBioRAG X.Y.Z — [una frase que describe el cambio principal]

[Párrafo de contexto: qué tiene esta versión que la anterior no tenía.
Sin jerga interna. Como si lo leyera un desarrollador externo en GitHub.]

Highlights of X.Y.Z

[Lista de cambios concretos y visibles para el consumidor de la librería / MCP.
No mencionar el proceso interno, solo el resultado: arquitectura, conectores, rendimiento, correcciones.]

Installation & Quick Start

[Comandos limpios de clonación e instalación automatizada sin dependencias complejas.]

Quick Verification

[Comandos reales de prueba básica con salida verificable.]

Distribution Note

[Información sobre el canal estable y el tag correspondiente en GitHub.]
```

**Ejemplos de lo que NO debe aparecer:**
- ❌ Rutas absolutas del host (`/mnt/recursos_compartidos_y_otros/...`, `/home/dennys/...`)
- ❌ Nombres de sesiones, agentes internos o referencias al repositorio de desarrollo (`DEV`)
- ❌ Referencias a bases de datos de desarrollo privadas o logs de testing internos
- ❌ Texto en español en el cuerpo principal de la documentación de release

### 11.3 Invariante de Aprobación Humana

**Ningún comando que modifique el repositorio público remoto o cree tags públicos se ejecuta de forma automática.**

Cuando el dueño del proyecto pida publicar:
1. El agente valida que todos los pasos locales 1, 2 y 3 hayan terminado con éxito (cero errores, cero blockers).
2. El agente prepara el archivo `docs/releases/RELEASE-<tag>.md` y el contenido exacto para el GitHub Release.
3. El agente presenta el resumen de los cambios, el árbol sanitizado y solicita confirmación explícita antes de ejecutar cualquier acción sobre el repositorio remoto o deja los comandos listos para ejecución por el usuario.

### 11.4 Operaciones de Control y Emergencias en Git / GitHub

El agente debe conocer los comandos directos para asistir al usuario ante cualquier contingencia:

1. **Eliminar un tag remoto erróneo o corrupto:**
   ```bash
   git tag -d <tag>
   git push origin :refs/tags/<tag>
   ```

2. **Publicar un hotfix de emergencia:**
   - Si se detecta un problema crítico en una versión recién publicada, se corrige en el repositorio de desarrollo, se genera el preview con el nuevo tag de parche (ej. `v1.0.1`), se audita con `stage_stable.py`, y se publica inmediatamente el nuevo release reemplazando el anterior.

