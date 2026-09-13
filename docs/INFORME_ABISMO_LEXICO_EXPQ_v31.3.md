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

## Retracción

El "grafo 3/3" de orientación (pos 3/1/18) NO replica (5 sondas:
2 vecinos, gold ausente). Retractado. Primaria-0/3 (harness) válida.

## Récord v31.3 + flags EXP-Q

921: R@5 **98.06** R@1 **90.74** MRR **0.9355** fallos **17** FP **0**
(`db4152c`). EXP-Q: pool 3/3 + dev 3/3 (K=400, T=0.45). Suite **168**.
Flags EXP-Q default-OFF: `BIORAG_DIM_RESONANCIA(_K)`, `BIORAG_DIM_ESCAPE(_T)`.
Decisión: cerrar v31.3 con A/B shippeados OFF + muro documentado.
