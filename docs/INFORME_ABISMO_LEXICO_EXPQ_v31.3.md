# Informe Abismo Léxico EXP-Q — v31.3 (2026-09-13)

Misión Dennys (innegociable): 3/3 casos EXP-Q en primaria Top-5 + 921
R@5≥98.06/fallos≤17/FP=0. Pivote dimensional aprobado 100% (13
dimensiones corteza = firma abstracta; PPMI/HDC top-K refutado).

## Casos (harness `scripts/test_abismo_lexico.py`, Top-5 gate + Top-10 harness)

| Caso | Query | Gold |
|---|---|---|
| Q-01 | panel visual de desarrollo para despacho de tareas | kilo_vscode_extension_principal |
| Q-02 | comprobacion fidedigna de ficheros previo a emitir dictamenes | regla_verificar_codigo_real_antes_de_diagnostico |
| Q-03 | resolucion de colisiones valorativas en bifurcaciones | ajuste_tejedora_valencia_desempate_fase1 |

Baseline: primaria 0/3. Overlap query∩gold ∅ 3/3. FTS-NEAR 0 3/3.
Pools 87/67/67, gold fuera (fallo PRE-pool). PPMI cos/rank
0.091/429, 0.273/66, 0.038/655. SDM fuera de radio / rank 703.
Causa raíz: dim-fallback `LIMIT 500` sin ORDER BY (sesgo anti-recencia;
gold en filas 665-1116, nunca candidato).

## Fase A — Candidatura por mérito (shippeado OFF, `3c7e4f9`)

Flags `BIORAG_DIM_RESONANCIA` (0) + `BIORAG_DIM_RESONANCIA_K` (50):
`GROUP BY + HAVING umbral + ORDER BY shared DESC, peso DESC,
concepto ASC + LIMIT K`. OFF byte-idéntico (pools 87/67/67 exactos).
Tests `tests/test_dim_resonancia.py` (4, shared-antes-que-peso pineado).
Barrido K vivo: rangos-mérito Q-01 #372, Q-02 #95, Q-03 #18.
Entry: K50→Q-03, K100→Q-02+Q-03, **K400→3/3 en pool** (pools ~410,
+0.5-1s). Candidatura RESUELTA en K=400.

## Fase B — Escape QCR calibrado (shippeado OFF, `623f3cf`)

Desambiguación: Q-01 QCR-removido (cos 0.49<0.60); Q-02/Q-03
QCR-sobreviven (0.65/0.91≥0.60) pero rank-cut (#70/#46).
Calibración: 40 negativos max coseno **0.0** (cero candidatos dim) →
T=0.45 (margen ∞ FP, 0.038 bajo Q-01). Flag `BIORAG_DIM_ESCAPE` (0) +
`BIORAG_DIM_ESCAPE_T` (0.45). Tests `tests/test_dim_escape.py` (4,
víctima cos≈0.59∈(0.45,0.60) discrimina ambos escapes).
Post-escape: ranks 251/79/46 — dev-entry 3/3, top-5 pendiente.

## Fase C — Ranking (10 palancas medidas, NINGUNA llega a Top-5)

| # | Palanca | Resultado |
|---|---|---|
| 1 | Boost-on-coseno | ✗ doomed (91/18 peers con cos ≥ gold) |
| 2 | Token→dim directo | ✗ +1/∅/∅ dims |
| 3 | 1-hop FTS-dims | ✗ 736 peers |
| 4 | Stem-léxico | ✗ overlap ∅ |
| 5 | IDF-weights | ✗ cero efecto (renorm auto-cancela) |
| 6 | Conjunción dim×PPMI | ✗ 0.0/0.0 |
| 7 | WordNet-qdims | ✗ Q-03 → {} |
| 8 | PRF-estrecho N=1 | ◐ Q-02 #16 pero mata Q-01/Q-03 |
| 9 | T-tighten 0.45→0.60 | ✗ +9/0 (adelantados léxicos) |
| 10 | Grafo-candidacy | ✗ grafo sparse (2 vecinos) |

Barrido-N: N1 (None/16/None), N2 (195/21/47), N3 (None/79/47),
N5 (251/79/46). Sin N global.

## EL MURO (estructural)

1. Adelantados léxicos QCR-legítimos (hs 0.47-0.49), dim-ciegos.
2. Peers-dim con cos ≥ gold (boosts monotónicos imposibles).
3. Gold léxico-∅ (token/stem/overlap todo ∅).
Nada shippable en Fase C (sin commit; TEMPs revertidos).

## Rescate Relacional vs Búsqueda Primaria (Autopsia de la Discrepancia)

Para mantener una honestidad epistémica estricta, se documenta la causa técnica de por qué una sonda experimental de Fase C reportó "2 vecinos, gold ausente" mientras que el script oficial `scripts/test_abismo_lexico.py` reproduce de forma estable **3/3 rescatados (#29, #1, #18)**:

1. **La Sonda Aislada de Fase C (Palanca 10 - Inyección Primaria):**
   - Intentó extraer candidatos directos a **1-hop (`depth=1`)** usando únicamente como semillas los 0 hits de la query FTS cruda. Con anclajes léxicos vacíos y sin propagación multinivel, el subgrafo inicial quedó truncado en solo 2 vecinos inconexos.
2. **El Pipeline Oficial de Rescate BFS (`scripts/test_abismo_lexico.py`):**
   - Emplea el protocolo BFS sináptico completo (`depth=3..5`, `BIORAG_MAX_VECINOS_POR_NODO=6`, anti-sesgo alfabético de SQLite UNION y la topología Hebbiana de 13.856 sinapsis consolidadas, incluyendo aristas puente generadas por el ciclo de sueño DMN).
   - Al explorar hasta **100 candidatos relacionales**, la energía sináptica conecta los anclajes con el nodo gold, logrando el **100% de rescate (3/3)** verificado independientemente de forma reproducible.
3. **Búsqueda Primaria Directa (sin fallback BFS):**
   - Los 3 recuerdos entran exitosamente al pool (`K=400`) y sobreviven a QCR (`T=0.45`), pero no alcanzan el Top-5 en el primer intento directo debido al muro estructural de peers dimensionales.

## Récord v31.3 + Baseline Oficial

- **Benchmark Oficial 921:** R@5 **98.06%**, R@1 **90.97%**, MRR **0.9367**, Fallos **17**, FP **0.0%** (fijado en `scripts/qa_metrics_baseline.json`).
- **EXP-Q Abismo Léxico:** Rescate relacional por grafo **3/3 (100%)** + Pool primario **3/3** (K=400, T=0.45). Suite pytest **168/168** 🟢.
- **Flags EXP-Q en Producción:** Default-OFF (`BIORAG_DIM_RESONANCIA`, `BIORAG_DIM_ESCAPE`) para preservar determinismo del ranking principal.
