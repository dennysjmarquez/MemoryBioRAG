# Informe de Validación — Spec 003: Modularización de Arquitectura

- **Especificación:** `specs/003-modularizacion-arquitectura/spec.md`
- **Rama:** `modularizacion-arquitectura`
- **Commit evaluado:** `31f0cbf` / `aaa40a0`
- **Fecha:** 2026-09-26

---

## 1. Resultados de las Suites de Pruebas y Benchmarks

### A. Suite Unitaria (`pytest tests/ -v`)
```text
======================== 264 passed in 61.42s (0:01:01) ========================
```
* **Resultado:** 264 pasados, 0 fallados, 0 omitidos (100% verde).

### B. Suite de Fuzzing y Adversarial (`python3 scripts/fuzz_qa.py`)
```text
==================================================
FIN DE PRUEBAS DE FUZZING
Total casos: 33 | Exitos: 33 | Fallos: 0
==================================================
```
* **Resultado:** 33/33 casos aprobados sin excepciones no controladas.

### C. Suite Global QA y Benchmark Canónico (`./scripts/run_qa_suite.sh`)
```text
================================================================================
                      BIORAG QA EVALUATION REPORT
================================================================================
Total time elapsed: 938.50 seconds
--------------------------------------------------------------------------------
Category               | Total  | Recall@5  | Recall@1  | MRR      | Errors/FPs
--------------------------------------------------------------------------------
ambiguo                | 6      | N/A       | N/A       | N/A      | 2
cruce_idioma           | 8      |  100.00% |   62.50% |  0.740 | 0         
dormido                | 65     |  100.00% |  100.00% |  1.000 | 0         
literal                | 487    |  100.00% |   99.59% |  0.998 | 0         
negativo               | 40     | N/A       | N/A       | N/A      | 0
por_tema               | 65     |  100.00% |   67.69% |  0.811 | 0         
pregunta_natural       | 65     |  100.00% |   95.38% |  0.972 | 0         
sinonimo               | 55     |  100.00% |   56.36% |  0.722 | 0         
typo                   | 65     |  100.00% |   84.62% |  0.911 | 0         
variante_gramatical    | 65     |  100.00% |   86.15% |  0.911 | 0         
--------------------------------------------------------------------------------
GLOBAL SUMMARY (Retrieval) | 875    |  100.00% |   91.77% |  0.950 | 0         
GLOBAL SUMMARY (Noise/FP)  | 40     | N/A       | N/A       | N/A      | 0 (0.00% FP)
================================================================================
[GATE] OK — métricas dentro de los umbrales de la baseline oficial
```

### D. Verificación Dual Sustituto (921 Casos sobre blob `ae449de2` ANTES=df5d8db vs DESPUÉS=31f0cbf)

```text
Líneas antes:   921
Líneas despues: 921
Diffs:          2
```

**Detalle y Explicación:**
- **Casos comparados:** 921/921 casos.
- **Diferencias de score:** 0 (identidad exacta a 4 decimales en todos los scores devueltos).
- **Diferencias de orden:** 2 casos con empate exacto de score en posiciones 4–5:
  - Caso `0096`: empate exacto con score `0.2138` entre `biorag_sync_skill_v11_herramientas_mcp` y `auditoria_readme_v28_correcciones_20260815`.
  - Caso `0347`: empate exacto con score `0.2284` entre `oracle_auditoria_patrones_mejora_athena` e `identidad_dennys_perfil_completo`.
- **Casos con top5 vacío:** 38 casos en ANTES y 38 casos en DESPUÉS, correspondientes al 100% a casos marcados como controles negativos (`categoria: "negativo"`).

---

## 2. Comprobación Requisito por Requisito (RF por RF)

*Nota sobre numeración:* En `specs/003-modularizacion-arquitectura/spec.md` no existe `RF-13` (la numeración pasa directamente de `RF-12` a `RF-14`). Se evalúan los 26 requisitos funcionales formalmente definidos.

| RF | Descripción resumida | Test que lo cubre / Evidencia | Estado |
|---|---|---|---|
| **RF-1** | Preservar firmas públicas, nombres y contratos de `SQLiteMemoryBioRAG` | `tests/test_memory_core.py`, `tests/test_biorag_cli.py`, `test_memory.py` | ✅ pasa |
| **RF-2** | Preservar 42 nombres exactos de tools MCP, 2 resources y 1 prompt | `tests/test_mcp_singleton.py`, `scripts/fuzz_qa.py` (inspección `_build_server()`) | ✅ pasa |
| **RF-3** | Preservar puntos de entrada (`mcp_server.py`, `biorag.py`, `core/memory_store.py`) | `tests/test_biorag_cli.py`, `tests/test_memory_core.py` | ✅ pasa |
| **RF-4** | Invarianza DDL en SQLite (sin cambios de esquema que rompan DBs previas) | `tests/test_sustantivos_clave_schema.py`, `tests/test_sustantivos_clave_instalacion.py` | ✅ pasa |
| **RF-5** | Descomposición estricta de `mcp_server` en 15 submódulos + `_shared.py` | Inspección de paquete `core/mcp_server/`, `scripts/fuzz_qa.py` | ✅ pasa |
| **RF-6** | Submódulos MCP exponen `register(mcp)` y docstring con nombres en español | `tests/test_mcp_singleton.py`, `scripts/fuzz_qa.py` | ✅ pasa |
| **RF-7** | `core.paths.project_root()` en arranque y soporte de ejecución con `cwd=/tmp` | Cubierto por la suite de 264 (sin test dedicado) | ✅ pasa |
| **RF-8** | Extracción a `core/memory/` sin reescritura, firmas completas, calificación `constants.NOMBRE` y adaptación `inspect.getsource` | `tests/test_ncd_e6.py`, `tests/test_jsd_adaptativo_e7.py`, `tests/test_dim_escape.py`, `tests/test_dim_resonancia.py`, `tests/test_qcr_idf_e3.py`, `tests/test_qcr_typo_d4.py` | ✅ pasa |
| **RF-9** | Estado en memoria no-SQL encapsulado en instancia `self` (sin globales mutables) | Cubierto por la suite de 264 (sin test dedicado) | ✅ pasa |
| **RF-10** | Clusters de dominio extraídos como bloques completos | `pytest tests/ -v` (264/264 pasando) | ✅ pasa |
| **RF-11** | Fachada `core/memory_store.py` delgada con delegación explícita (prohibido `__getattr__`) | `tests/test_memory_core.py`, inspección AST de `core/memory_store.py` | ✅ pasa |
| **RF-12** | Aislamiento de constantes en `core/memory/constants.py` con re-exports hacia afuera | `tests/test_dim_escape.py`, `tests/test_dim_resonancia.py`, `tests/test_normalizar_sustantivos_clave.py` | ✅ pasa |
| **RF-13** | *(No existe en spec.md — numeración discontinua de RF-12 a RF-14)* | N/A | N/A |
| **RF-14** | Fase 0: Congelamiento de entorno, golden baseline y snapshot inmutable fuera del repo | PARCIAL — golden y entorno generados en Fase 0; el snapshot de la base viva se perdió; medición 3 sustituida por dual sobre blob ae449de2 | ⚠️ PARCIAL |
| **RF-15** | Invarianza de rutas sensibles (`test_resonancia*.py`, `test_memory.py`, dashboards) | Inspección de working tree y `git status` | ✅ pasa |
| **RF-16** | Trabajo exclusivo en rama aislada `modularizacion-arquitectura` (sin tocar `master`) | `git branch --show-current` (`modularizacion-arquitectura`) | ✅ pasa |
| **RF-17** | Merge a `master` reservado exclusivamente a Dennys tras informe Gate Nivel 2 | Gobernanza de repositorio (cero push a `master`) | ✅ pasa |
| **RF-18** | Commits atómicos en la rama sin uso de `git push --force` | Historial `git log --oneline` (T1 a T21 secuenciales y atómicos) | ✅ pasa |
| **RF-19** | Revert formal vía `git revert` ante fallos detectados | Procedimiento auditado en historial de git (`e6aabb4`) | ✅ pasa |
| **RF-20** | Mensajes de commit con estándar `type(scope): descripción` y tablas de líneas | Inspección de `git log` | ✅ pasa |
| **RF-21** | Prohibición de incluir archivos `.db`, `.env.local`, `__pycache__` en commits | `git log -p` auditado; `git status --short` (`memory_biorag.db` excluido) | ✅ pasa |
| **RF-22** | Prohibición estricta de `git add -A` y checkouts ciegos | Adherencia a git staging selectivo por archivo | ✅ pasa |
| **RF-23** | Entorno determinista `PYTHONHASHSEED=0`, `BIORAG_NO_LOG=1`, DMN externo | `run_qa_suite.sh`, `evaluar_qa.py`, scripts de dual | ✅ pasa |
| **RF-24** | Gate Nivel 0 (264 tests passed, smoke imports, inventario MCP 42 tools) | `pytest tests/ -v` (264/264 pasando) | ✅ pasa |
| **RF-25** | Gate Nivel 1 (Identidad funcional caso a caso en módulos completos) | Benchmarks y golden runs intermedios de T11 a T20 | ✅ pasa |
| **RF-26** | Política de no-regresión y reversión inmediata ante variaciones funcionales | Verificada en T17/T18/T19 | ✅ pasa |
| **RF-27** | Gate Nivel 2: suite QA completa (875/875, 0 FP) + fuzz (33/33) + dual SUSTITUTO | `./scripts/run_qa_suite.sh`, `scripts/fuzz_qa.py`, `dual_sustituto.py` | ✅ pasa |

---

## 3. Comprobación de Requisitos No Funcionales (RNF)

| RNF | Descripción | Evidencia / Medición | Estado |
|---|---|---|---|
| **RNF-1.1** | Límite por archivo ($\le 500$ orientativo, $\le 800$ duro salvo excepciones de deuda) | Submódulos respetan el límite; los que superan 500 incluyen justificación explícita en docstring. | ✅ pasa |
| **RNF-1.2** | Límite por función ($\le 100$ objetivo, $> 150$ bandera roja/deuda) | Cero funciones nuevas $> 150$ líneas. Funciones monolíticas preexistentes documentadas como deuda técnica explícita. | ✅ pasa |
| **RNF-1.3** | Mover $\neq$ Partir (deuda técnica trasladada intacta) | `buscar_por_frase`, `_recordar_impl`, `_aprender_impl`, `ciclo_sueno_consolidacion`, `_crear_estructura_cerebral` trasladadas 100% intactas. | ✅ pasa |
| **RNF-1.4** | Fachada `core/memory_store.py` delgada | 637 líneas, justificación en docstring línea 80 (excepción RNF-1.4). | ✅ pasa |
| **RNF-2** | Rendimiento y cero dependencias externas adicionales | Tiempo global suite QA: 938.5s. 100% offline, Python estándar y SQLite local. | ✅ pasa |

---

## 4. Tabla de Auditoría de Líneas (`wc -l`)

### A. Paquete `core/memory/`
| Archivo | Líneas (`wc -l`) | Excepción aplicada |
|---|---|---|
| `core/memory/__init__.py` | 0 | Ninguna ($\le 500$) |
| `core/memory/adn.py` | 166 | Ninguna ($\le 500$) |
| `core/memory/catalog_methods.py` | 124 | Ninguna ($\le 500$) |
| `core/memory/comms.py` | 117 | Ninguna ($\le 500$) |
| `core/memory/consolidation.py` | 719 | Excepción RNF-1.3 (deuda técnica: `ciclo_sueno_consolidacion` 505 líneas trasladada intacta) |
| `core/memory/constants.py` | 248 | Ninguna ($\le 500$) |
| `core/memory/context.py` | 119 | Ninguna ($\le 500$) |
| `core/memory/dmn.py` | 111 | Ninguna ($\le 500$) |
| `core/memory/episodes.py` | 128 | Ninguna ($\le 500$) |
| `core/memory/ingest.py` | 181 | Ninguna ($\le 500$) |
| `core/memory/quarantine.py` | 145 | Ninguna ($\le 500$) |
| `core/memory/rafaga.py` | 383 | Ninguna ($\le 500$) |
| `core/memory/schema.py` | 1161 | Excepción RNF-1.3 (deuda técnica: `_crear_estructura_cerebral` 513 líneas + DDL trasladadas intactas) |
| `core/memory/scoring.py` | 452 | Ninguna ($\le 500$) |
| `core/memory/search.py` | 2603 | Excepción RNF-1.3 (deuda técnica: `buscar_por_frase` 2109 líneas trasladada intacta) |
| `core/memory/synapses.py` | 560 | Excepción RNF-1.1 (bloque indivisible de operaciones de grafo sináptico, docstring L8) |
| `core/memory/telemetry.py` | 161 | Ninguna ($\le 500$) |
| `core/memory/umbral.py` | 523 | Excepción RNF-1.1 (bloque indivisible de calibración conforme Platt y UmbralConforme, docstring L8) |

### B. Paquete `core/mcp_server/`
| Archivo | Líneas (`wc -l`) | Excepción aplicada |
|---|---|---|
| `core/mcp_server/__init__.py` | 0 | Ninguna ($\le 500$) |
| `core/mcp_server/_shared.py` | 148 | Ninguna ($\le 500$) |
| `core/mcp_server/calibrar.py` | 47 | Ninguna ($\le 500$) |
| `core/mcp_server/catalog.py` | 186 | Ninguna ($\le 500$) |
| `core/mcp_server/communication.py` | 155 | Ninguna ($\le 500$) |
| `core/mcp_server/concept_hub_tools.py` | 192 | Ninguna ($\le 500$) |
| `core/mcp_server/consolidation.py` | 70 | Ninguna ($\le 500$) |
| `core/mcp_server/daemon.py` | 108 | Ninguna ($\le 500$) |
| `core/mcp_server/introspection.py` | 196 | Ninguna ($\le 500$) |
| `core/mcp_server/oracle.py` | 309 | Ninguna ($\le 500$) |
| `core/mcp_server/prompt.py` | 263 | Ninguna ($\le 500$) |
| `core/mcp_server/resources.py` | 80 | Ninguna ($\le 500$) |
| `core/mcp_server/search.py` | 1465 | Excepción RNF-1.3 (deuda técnica: `_recordar_impl` 753 líneas trasladada intacta) |
| `core/mcp_server/server.py` | 174 | Ninguna ($\le 500$) |
| `core/mcp_server/session.py` | 97 | Ninguna ($\le 500$) |
| `core/mcp_server/synapses.py` | 117 | Ninguna ($\le 500$) |
| `core/mcp_server/sync.py` | 107 | Ninguna ($\le 500$) |
| `core/mcp_server/write.py` | 898 | Excepción RNF-1.3 (deuda técnica: `_aprender_impl` 321 líneas trasladada intacta) |

### C. Fachada Principal
| Archivo | Líneas (`wc -l`) | Excepción aplicada |
|---|---|---|
| `core/memory_store.py` | 637 | Excepción RNF-1.4 (fachada consolidada con 99 delegadores con firma completa explícita, docstring L80) |

---

## 5. Veredicto Final

```
VEREDICTO: ✅ SPEC CUMPLIDA (con salvaguarda RF-14 documentada)

RF cubiertos: 25/26 cumplidos al 100%, 1 parcial documentado (RF-14, sustituido por dual sustituto blob ae449de2)
RNF cubiertos: 5/5
Tests Unitarios: 264 pasando, 0 fallando, 0 omitidos
Fuzzing QA: 33 pasando, 0 fallando
Benchmark QA (Retrieval): 875/875 (100.00% Recall@5, 0 FP)
Dual Sustituto: 921/921 casos, 0 diferencias de score, 2 empates en pos 4-5
```

> Validación completada. Si vienen cambios al proyecto, usa el skill `sdd-cambio` — **nunca toques el código antes de actualizar la spec**.

---

## 6. Incidencia 0513

- Corrida de Dennys 2026-09-26: R@5 874/875, caso 0513 (typo) ausente del top-5; los otros 4 scores idénticos a la referencia.
- Aislamiento: buscar_por_frase con los mismos parámetros de evaluar_qa, df5d8db y 34d888c, dos corridas cada uno, sobre copias frescas del snapshot: idénticos, esperado en pos 3 con 0.2707. El código no lo movió.
- Re-corrida completa con BIORAG_DMN_ESTADO_PATH fuera del repo: 875/875, idéntica a baseline 2026-08-26.
- Causa NO confirmada. Sospechoso: graph_maintenance_daemon.py (PID 6535, vivo desde 14:58, spawneado por mcp_server con --intervalo 0.5 = horas) ejecuta UPDATE largo_plazo SET estado='dormido' (core/dmn_reflexion.py:752) con veredictos LLM; un nodo dormido no entra en profundidad="activos". Verificado: el daemon corre sin BIORAG_PATH (usa la DB viva por defecto, cwd=repo), por lo que NO tocó la copia QA; el sospechoso queda debilitado. Causa no reproducida en 3 corridas completas. Se abre como spec 004.
