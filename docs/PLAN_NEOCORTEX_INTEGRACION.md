# PLAN — Integración Neocórtex v29 en MemoryBioRAG

> **Este archivo es el hilo conductor.** Si una sesión se pierde, se reanuda desde acá.
> Última actualización: 2026-08-13. Estado: **FASE 2 COMPLETA** (módulos instalados + parches, flag OFF, eval con paridad exacta).
> Firmado por: Athena-OEC, en co-creación con Dennys. Sesión anterior (Claude Web) se quemó — el contexto está en BioRAG (`neocortex_v29_estado_integracion_20260813`, `neocortex_politica_a_honestidad_epistemica`, `vision_neocortex_memoria_asociativa_redactada`).

---

## 1. La meta (redactada, aprobada por Dennys)

**Emular la memoria asociativa biológica: recuperar por significado y relaciones, no por coincidencia de palabras.**
- Cuando se activa "playa" → propagar activación a "piscina", "mar", "fotos" (caso Cebra).
- Tres niveles de honestidad epistémica (Política A): `evidencia_directa` (C_e ≥ 0.60) / `relacionado_confianza_media` (0.20–0.59) / `sin_evidencia_directa` (< 0.20). **Nunca silencio vacío, nunca inventar.**
- Sustrato: espacio semántico que **emerge del propio corpus** (PPMI+SVD interno, no DB vectoriales comerciales ni embeddings de caja negra).
- Matiz crítico: "cero vectores" literal es FALSO (el ADN usa coseno sobre vectores PPMI). Correcto: **cero dependencia de bases vectoriales externas**.

## 2. Estado real verificado (2026-08-13)

- Commit `906b27c` está en `master`, pero **solo agregó archivos a `docs/¿Cuál es la Meta Final del Proyecto_Neocortex_nivel_2/`** (el fork).
- `core/` está **INTACTO**: NO existen `core/neocortex_teleologico.py` ni `core/adn_conceptual.py`. Copiarlos directo daría ImportError.
- `core/auto_clustering.py`, `core/ppmi_vectorizer.py`, `core/ppmi_hybrid_search.py` SÍ existen.
- Baseline oficial: `snapshots/qa_escape_qcr_20260811.db` (866 nodos, con PPMI) → **921 casos, R@5 96.03%, R@1 88.76%, MRR 0.916, FP 10/40 (25%)**.
- ⚠️ `scripts/snapshot_prf_real.db` (487 nodos, SIN PPMI/ADN) **NO es comparable** — de ahí vienen los números 87.85%/FP 0% del plan original (discrepancia corregida).
- VERSION = v27.0, branch de trabajo: `neocortex-v29-integracion` (desde master 906b27c).

## 3. Decisiones de Manus AI (aplican, no se negocian)

1. **Política A**: nunca silencio; bandas C_e 0.60/0.20/<0.20; nunca `raise` público.
2. **Flag** `BIORAG_ADN_RANKING_ENABLED=0` por defecto. Ablación OFF/ON sobre dos copias aisladas idénticas del snapshot canónico (checksum + commit + flags + conteos en JSON).
3. **Integración por etapas**: módulos a `core/`, scripts a `scripts/`, cambios a `memory_store.py`/`dmn_engine.py` como **parches por función** (no copias enteras).
4. Integrar **centralmente en `buscar_por_frase()`** (mcp_server.py lo llama en líneas 775 y 2706), no en cada handler MCP.
5. **Criterios de aceptación**: R@5 ≥ 95.53 (−0.50pp), R@1 ≥ 88.26, MRR ≥ 0.911, FP ≤ 10/40, typos/variantes sin degradar, OOV sin crash, sin escaneo en caliente de `self.indices.vecs.items()` (O(1)).
6. IDs 0649/0746 (diferencia de ranking con OFF): reproducibilidad ×3; posible desempate determinista `(-score, concepto_normalizado)`.
7. Si la ablación falla → flag queda OFF, documentado como experimento (lección PPR v25.1).

## 4. Fases

| Fase | Qué | Estado |
|------|-----|--------|
| **0** | Inventario del fork con SHA-256 | ✅ HECHO — 31 archivos en `/tmp/opencode/neocortex_origen.sha256` |
| **1** | Reproducir baseline 96.03% sobre copia aislada | ✅ HECHO 2026-08-13 — R@5 96.03%, R@1 88.76%, MRR 0.916, FP 10/40. Log: `/tmp/opencode/baseline_repro_20260813.txt`. Fase 1 lista como antes para Fase 3 (ablación). |
| **2** | Instalar módulos en `core/` + flag OFF + parches | ✅ HECHO 2026-08-13 — ver §7 desviaciones y evidencia |
| **3** | Ablación OFF/ON | ⬜ |
| **4** | Criterios de aceptación | ⬜ |
| **5** | Contrato de salida (`estado_epistemico`, `tipo_relacion`, `confianza_epistemica`, `score_base`, `score_adn`, explicación) + adaptador de compatibilidad | ⬜ |

## 7. Fase 2 — Detalle de lo instalado (2026-08-13)

**Branch**: `neocortex-v29-integracion` (creada desde master 906b27c). **Nada commiteado aún** — todo en árbol de trabajo.

**Módulos nuevos en `core/`:**
- `core/adn_conceptual.py` — copia exacta del fork (SHA-256 idéntico al inventario: `0ba7db05...`)
- `core/neocortex_teleologico.py` — copia exacta del fork (SHA-256 idéntico: `6d70aeaf...`)
- `core/hipotesis_teleologica.py` — **ADAPTADO**: el fork importa `CROMOSOMAS_CATALOGO` (vacío `[]` en v29) → usa `self.adn.nombres_cromosomas` (dinámicos). El plan §1.2 lo manda: "Instalar después de adaptar a cromosomas dinámicos".

**Parches por función (no copias):**
- `core/memory_store.py`: +import logging/logger, +import json (⚠️ el fork usa `json` SIN importarlo — bug latente corregido), +init `neocortex`/`adn_engine` (solo si `self._ppmi_index is not None`), +`_cargar_firmas_adn`/`_persistir_firma_adn`, +tablas `adn_firmas` + `hipotesis_teleologicas`, +`_adn_pendiente_recalculo=True` en camino de escritura.
- `core/dmn_engine.py`: +docstring teleología genética, +bloque v29 de reconstrucción ADN nocturna en `ejecutar_ciclo_curiosidad`.
- `core/auto_clustering.py`: **NO TOCADO** — el diff del fork solo duplica `import re` (ya existe en core). Ruido, mínimo necesario.
- Bloque 6 del fork (raise EpistemicUncertaintyError en `buscar_por_frase`) **NO aplicado**: la clase existe pero `evaluar_episteme` NUNCA lanza (verificado en el código del fork) → raise muerto que viola Política A ("nunca raise público"). La señal epistémica se cablea en Fase 3 bajo flag.

**Evidencia de no-regresión (Fase 2):**
- `pytest`: 15 passed, 1 failed (`test_sdm_query_by_example.py::test_03_bit_masking` — **pre-existente en master limpio**, verificado con worktree; ZeroDivisionError ajeno a la integración).
- Eval flag OFF sobre snapshot canónico: **R@5 96.03%, R@1 88.76%, MRR 0.916, FP 10/40 (25%), spreading 20/921 (2.2%)** — paridad exacta con baseline. Log: `/tmp/opencode/eval_integracion_flagOFF_20260813.txt` (743.54s).
- Smoke: `SQLiteMemoryBioRAG(snapshot)` carga neocortex+adn sin crash; `evaluar_episteme("memoria persistente")` → `ignoto_insuficiente_soporte`, C_e=0.3, 0 candidatos (correcto: índice v29 aún no construido, se hará en sueño DMN).

## 8. Hallazgo de raíz — ADN degenerado por grafo sin modularidad (2026-08-13)

**Síntoma**: reconstrucción del índice ADN sobre el snapshot canónico → **1 solo cromosoma** (`auto_nodos_oec_athena`, 866 nodos). `buscar_por_esencia("memoria persistente")` y `buscar_por_esencia("arquitectura")` devuelven los MISMOS 5 nodos con afinidad 1.0. Señal no discriminativa.

**Diagnóstico verificado (evidencia, no hipótesis):**
- Snapshot: 13 755 sinapsis (peso ≥ 0.1), componente gigante **813/851** nodos. DB real: 14 584 sinapsis, componente gigante **852/649** (transita nodos dormidos).
- LPA (`core/auto_clustering.py`, seed 42) genera 14 comunidades RAW pero colapsa a 1 etiqueta dominante de 653 nodos + 186 → el filtro de densidad deja 1 comunidad gigante (params fork `min_densidad=0.1, min_nodos=2`). Con params core `(0.3, 5)`: **0 comunidades** en ambos DB.
- Con 1 cromosoma, la firma ADN es un escalar; coseno entre escalares no-negativos = 1.0 → afinidad uniforme, orden por inserción de membresía, no por significado.
- El espacio PPMI/SVD es SANO (8083 tokens, 866 vectores, `vector_query` OK) — el problema NO es el espacio semántico sino la **topología sináptica saturada** (grafo de una sola masa).

**Implicación**: el clustering LPA sobre este corpus no produce cromosomas discriminativos. La señal ADN v29, tal como está diseñada, no puede aportar asociación semántica útil sobre este grafo. La ablación ON con este índice es un **control de regresión de señal degenerada** (¿el ruido ADN rompe el ranking?), no una medición de mejora semántica.

**Decisión en curso**: correr benchmark ON igualmente (12 min, dato necesario para decidir flag). Si degrada → flag OFF, documentado como experimento (lección PPR v25.1, decisión Manus §3.7). Si no degrada → señal inocua pero sin beneficio; el benchmark asociativo específico (§5) decidirá si la arquitectura necesita un clustering por vectores (comunidades PPMI) en lugar de LPA sobre sinapsis. **No inventar cromosomas artificiales** (Política A: "nunca inventar ejes semánticos").

## 9. Ablación OFF/ON completada — señal degenerada inocua (2026-08-13)

**Tres corridas controladas sobre snapshot canónico (921 casos, cada una ~11 min):**

| Corrida | R@5 | R@1 | MRR | errores | FPs |
|---|---|---|---|---|---|
| OFF, base limpia (`eval_integracion_flagOFF_20260813.txt`) | 96.03% | 88.76% | 0.916 | 35 | 10/40 |
| OFF, base con índice ADN v29 (`eval_integracion_flagOFF_adnbase_20260813.txt`) | 96.03% | 88.76% | 0.916 | 35 | 10/40 |
| ON, base con índice ADN v29 (`eval_integracion_flagON_20260813.txt`) | 96.03% | 88.76% | 0.915 | 35 | 10/40 |

**Atribución limpia (regla 13, un cambio a la vez):**
- El índice ADN v29 presente en la DB **NO altera nada** con flag OFF (OFF limpio = OFF con índice, ambos 0.916).
- El flag ON sobre la misma base produce **únicamente MRR −0.001** (0.916→0.915). R@5, R@1, 45 casos fallidos y 10 FPs **idénticos** (set de fallidos ON == baseline B, verificado caso a caso).
- El −0.001 es reordenamiento en posiciones 2-5 de casos no-fallidos; top-1 intacto (R@1 idéntico).

**Veredicto**: la señal ADN degenerada (1 cromosoma, afinidad 1.0 uniforme) es **inocua** para la búsqueda de recuperación: no rompe el ranking ni introduce FPs nuevos. Cumple todos los criterios de aceptación (R@5 96.03 ≥ 95.53, R@1 88.76 ≥ 88.26, MRR 0.915 ≥ 0.911, FP 10 ≤ 10).

**Decisión**: flag `BIORAG_ADN_RANKING_ENABLED` permanece **OFF por defecto** (no aporta mejora, no rompe nada). El hallazgo de raíz (§8) queda documentado: sobre este corpus, el clustering LPA de sinapsis no produce cromosomas discriminativos; la hipótesis de "señal asociativa real" del Neocórtex v29 **no puede validarse ni refutarse** con este índice degenerado. Cualquier siguiente paso (clustering por vectores PPMI, umbrales de sinapsis, esperar maduración del grafo en la DB viva) es **decisión de Dennys**, no un cambio unilateral.

## 5. Benchmark complementario (pendiente)

- ≥50 consultas de asociación (etiquetas: `directa` / `relacionada` / `sin_evidencia`).
- División de roles acordada: **Athena extrae pares reales del corpus** (sinapsis fuertes, mismas comunidades LPA, vecinos PPMI) → **Dennys etiqueta la verdad** → **auditor externo valida anti-sesgo**.
- Regla dura: el esperado NO debe co-ocurrir léxicamente con la query (si lo hace, mide BM25, no semántica — lección 08-08).
- Consultas de 2-4 palabras con contexto (la única prueba real que funcionó: carro/moto→coche con contexto rico).
- Formato: `.jsonl` tipo `asociacion`, no toca los 921 casos oficiales.

## 6. Cómo retomar (si se pierde esta sesión)

1. `biorag_recordar(query="neocortex integracion estado", parafrasis="...", forzar_rafaga=true, rafaga_palabras="...")` → recuperar los 3 nodos firmados Athena-OEC.
2. Leer este archivo + `docs/Plan de integración verificable — Neocórtex como señal asociativa de la búsqueda real.md`.
3. Ver Fase actual en la tabla de arriba y continuar desde ahí.
4. Nunca evaluar contra la DB viva. Siempre `BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db`.
