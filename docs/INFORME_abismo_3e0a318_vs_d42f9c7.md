# INFORME — Fases [3/5] Concept Hub y [4/5] Abismo: `3e0a318` (GOOD) vs `d42f9c7`

- Fecha: 2026-09-11. Rama de trabajo: `arena/01a08e29-memorybiorag` (no se cambió de rama; commits viejos examinados vía `git fetch` + worktrees detached en `/tmp`, ya removidos).
- Alcance: solo arqueología. **No se revirtió nada ni se tocó código.** Decisión de revert queda en manos del usuario.

## 1. Relación entre commits (VERIFICADO)

`3e0a318` (`propagate(retrieval): add Hebbian boost A/B test`) es el **padre directo** de `d42f9c7` (`feat(retrieval): improve semantic matching with stemming and recall`). `git rev-list --count 3e0a318..d42f9c7` = **1**. Toda la diferencia cabe en un solo commit.

## 2. Qué cambió en `d42f9c7` (VERIFICADO, `git show`)

| Archivo | Cambio |
|---|---|
| `core/concept_hub.py` | Scoring de bridges: `_tokenizar_stems` (normalización + stopwords + stemming), `jacc=max(raw,stem)`, recall bidireccional incondicional `max(jacc, rec_q*0.80, rec_b*0.80)` (antes: solo recall crudo `*0.85` y solo si query >10 tokens), tolerancia `1e-6` en el guard de ambigüedad |
| `MemoryBioRAG_Data/memory_biorag.db` | **Refresh del binario: 62.570.496 → 62.619.648 bytes (+49 KB).** Mensaje del commit: "Update the binary database file to reflect the current retrieval implementation" |
| `pyproject.toml` | Solo infra de tests (`pytest.ini_options`: pythonpath/testpaths). No afecta retrieval |
| `scripts/auditoria_causal_report.json` | Reporte regenerado del A/B Hebbiano: `num_no_ops=881`, 0 rescates (el boost Hebbiano de `3e0a318` no movió nada en ese A/B) |

Los scripts de evaluación (`scripts/test_concept_hub.py`, `scripts/test_abismo_lexico.py`) son **byte-idénticos** entre ambos commits: el harness no cambió.

## 3. Reproducción medida: matriz código × DB 2×2 (VERIFICADO)

Cada celda = corrida real del eval con `BIORAG_PATH` apuntando a la DB indicada. Código vía worktree detached; DB extraída con `git show <sha>:MemoryBioRAG_Data/memory_biorag.db`.

**Fase [3/5] Concept Hub — NO hay regresión entre estos commits:**

|  | DB `3e0a318` | DB `d42f9c7` |
|---|---|---|
| code `3e0a318` | **5/5 TOP1** (A) | — |
| code `d42f9c7` | — | **5/5 TOP1** (B, mismos hubs/confianzas que el log GOOD) |

**Fase [4/5] Abismo EXP-Q — SÍ hay regresión, y la causa es la DB, no el código:**

|  | DB `3e0a318` | DB `d42f9c7` |
|---|---|---|
| code `3e0a318` | **A: 3/3** (Q-01 #12, Q-02 #83, Q-03 primaria-TOP) | **D: 1/3** (solo Q-02 #74) |
| code `d42f9c7` | **C: 3/3** (idéntico a A) | **B: 1/3** (idéntico a D) |

- C (código nuevo + DB vieja) = 3/3 → **el cambio de stemming/recall es inocente.**
- D (código viejo + DB nueva) = 1/3 → **la DB commiteada es la culpable.**
- A reproduce el log GOOD del usuario (Q-02 #83 vs #80 del log: ruido de orden, no material).

## 4. Causa raíz: evento de sueño masivo dentro de la DB commiteada (VERIFICADO)

| Métrica | DB `3e0a318` | DB `d42f9c7` |
|---|---|---|
| Nodos / sinapsis | 1014 / 18947 | 1021 (+7) / 19255 (+308) |
| **activos / dormidos** | **1001 / 13** | **386 / 635** |
| Nodos activo→dormido | — | **622** |
| Sinapsis activo↔activo (grafo transitable) | 18617 | **4765 (−74%)** |
| Sinapsis que tocan un dormido | — | 14480/19255 (**75.2%**) |
| Peso medio dormidos vs activos (DB nueva) | — | **0.033** vs 0.647 |

El peso medio 0.033 de los dormidos calza exacto con el umbral de poda del ciclo de olvido/LTD (`core/memory_store.py`, `consolidar_memoria`, paso 3: `SET estado='dormido' WHERE peso_sinaptico <= 0.05`, idéntico en ambos commits — ese archivo no lo tocó `d42f9c7`). Entre un commit y otro, en la laptop corrió consolidación (decaimiento LTD + poda ≤0.05 + poda de sinapsis muertas + inhibición lateral) y durmió 622 nodos. `d42f9c7` commiteó esa DB viva tal cual.

Por qué rompe el rescate (mecanismo exacto, código idéntico en ambos commits):

- `expandir_contexto_vecinos(depth=2)` → `_expandir_contexto_bfs(profundidad="activos")` filtra `AND l.estado='activo'` y expande **máximo 6 vecinos por nodo** (`BIORAG_MAX_VECINOS_POR_NODO=6`) ordenados por `s.peso DESC, s.rowid DESC`.
- **EXP-Q-01** (`kilo_vscode_extension_principal`, sigue activo): misma ancla primaria en ambas DBs (`ejemplo_star_cv_dennys_resultado_final`), mismos 42 vecinos BFS. En la DB vieja el rescate entraba por el puente nivel-1 `memorybiorag_osf_preregistration` (arista 0.9 → target). En la DB nueva **ese puente está dormido** → el filtro de activos lo poda, el top-6 del ancla se rellena con nodos débiles (0.63) y el target queda fuera → IRRESUELTO. Replicación BFS exacta instrumentada: 42 nodos en ambas, target SÍ (vía ese puente, nivel 2) vs NO.
- **EXP-Q-03** (`ajuste_tejedora_valencia_desempate_fase1`): **el target mismo está dormido** en la DB nueva → primaria lo pierde (era TOP) y el BFS no lo puede devolver → IRRESUELTO.
- **EXP-Q-02**: su ruta sobrevivió (rescate #74 vs #83 — menos competidores, rank distinto).

## 5. HIPÓTESIS (no verificado, fuera del alcance medido)

- Por qué corrió la consolidación en la laptop entre commits (¿ciclo automático al cerrar sistema? ¿script manual? ¿MCP?). El código del olvido es el mismo en ambos commits; el evento fue estado, no código.
- Si en la laptop la fase [3/5] también falló "desde `d42f9c7`": **aquí no se reprodujo** (5/5 en ambas celdas con las DBs commiteadas). Si allá falló, fue contra la DB viva de ese momento (distinta de ambas commiteadas), no por el diff de este commit.

## 6. Datos para decidir el revert (sin acción tomada)

- Revertir `d42f9c7` completo restauraría la DB vieja (1001 activos) pero también sacaría el stemming/recall, que **no rompió nada medido** y cuyo propósito (robustez léxica) es legítimo.
- Alternativa quirúrgica: restaurar **solo** `MemoryBioRAG_Data/memory_biorag.db` a `3e0a318` y conservar el código. Nota: la DB viva real ya divergió de ambas; cualquier restore debe hacerse sobre copia y re-validando [3/5]+[4/5].
- Riesgo estructural (independiente del revert): el rescate a depth=2 con fan-out 6 es frágil ante sueño de puentes — un solo nodo dormido (`memorybiorag_osf_preregistration`) tumbó EXP-Q-01. Si el olvido LTD sigue corriendo sobre la DB viva, estos casos pueden recaer sin ningún cambio de código.

## 7. Repro (comandos exactos usados)

```bash
git fetch origin 3e0a318ac56922d7a171cd0532a1efc1446cea46
git fetch origin d42f9c73459f6c95c9f109c595ca554d45194298
git worktree add /tmp/wt_3e0a318 3e0a318ac56922d7a171cd0532a1efc1446cea46
git worktree add /tmp/wt_d42f9c7 d42f9c73459f6c95c9f109c595ca554d45194298
git show 3e0a318:MemoryBioRAG_Data/memory_biorag.db > /tmp/db_3e0a318.db
git show d42f9c7:MemoryBioRAG_Data/memory_biorag.db > /tmp/db_d42f9c7.db
cp /tmp/db_3e0a318.db /tmp/run_A.db   # A: code viejo + DB vieja → 3/3
cp /tmp/db_d42f9c7.db /tmp/run_B.db   # B: code nuevo + DB nueva → 1/3
cp /tmp/db_3e0a318.db /tmp/run_C.db   # C: code nuevo + DB vieja → 3/3
cp /tmp/db_d42f9c7.db /tmp/run_D.db   # D: code viejo + DB nueva → 1/3
cd /tmp/wt_3e0a318 && BIORAG_PATH=/tmp/run_A.db python scripts/test_abismo_lexico.py
cd /tmp/wt_d42f9c7  && BIORAG_PATH=/tmp/run_B.db python scripts/test_abismo_lexico.py
# ... etc. Fase 3: scripts/test_concept_hub.py con la misma BIORAG_PATH.
```

Limpieza: worktrees `/tmp/wt_*` removidos con `git worktree remove --force` y DBs `/tmp/*.db` borradas al cerrar el informe. Los objetos de ambos commits quedan en `.git` local (fetch), sin ramas creadas ni cambios de HEAD.
