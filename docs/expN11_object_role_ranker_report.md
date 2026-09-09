# EXP-N11: Object-Role Structural Index — Informe Formal

**Timestamp**: 2026-09-09T00:24:51Z  
**DB SHA-256**: `676827f6b4abc3acaee10b14e273c3c50cae5b2c180593dedcd58048265a2800`  
> **A0-TEST: CIEGO. No ejecutado. Confinado a DEV.**

## 1. Comparativa Histórica de Ranking sobre Candidatos M2

| Experimento | Ranker | DEV CE@5 | DEV CE@10 | DEV CE@20 | Str-A0 CE@20 | POS_19 Rank | POS_29 Rank | POS_30 Rank | POS_40 Rank |
|---|---|---|---|---|---|---:|---:|---:|---:|
| **EXP-N8 (Overlay)** | Heurístico superficial | 1/8 | 1/8 | 2/8 | 1/6 | 34 | 52 | 13 | 5 |
| **EXP-N9 (SCG)** | SCG structural genérico | 1/8 | 1/8 | 2/8 | 1/6 | 130 | 47 | 19 | 2 |
| **EXP-N10 (FCC)** | FCC-lite profile | 0/8 | 0/8 | 1/8 | 0/6 | 31 | 148 | 51 | 16 |
| **EXP-N11 (Object-Role)** | **Object-Role + Structural IDF** | **1/8** | **1/8** | **1/8** | **0/6** | **22** | **111** | **32** | **2** |

## 2. Resultados Detallados por Caso (DEV n=8)

| Case | A0 Status | Gold | Pool | Gen | Rank | CE@1 | CE@5 | CE@10 | CE@20 | C1 Causal |
|---|---|---|---:|---|---:|---|---|---|---|---|
| OOF_POS_11 | STRICT_A0 | `docker_infrastructure_rog` | 22 | NO | – | . | . | . | . | no |
| OOF_POS_19 | STRICT_A0 | `scoring_pesos_bm25` | 135 | YES | 22 | . | . | . | . | YES |
| OOF_POS_21 | STRICT_A0 | `coche_puente_condicional` | 93 | NO | – | . | . | . | . | no |
| OOF_POS_29 | STRICT_A0 | `desde_athena_biorag` | 292 | YES | 111 | . | . | . | . | YES |
| OOF_POS_30 | STRICT_A0 | `activos_dormidos_hermana` | 137 | YES | 32 | . | . | . | . | YES |
| OOF_POS_40 | NO_A0 | `clasificacion_dimensional_comp` | 28 | YES | 2 | . | ✓ | ✓ | ✓ | YES |
| OOF_POS_48 | STRICT_A0 | `cuaternidad-logica-oec` | 125 | NO | – | . | . | . | . | no |
| OOF_POS_49 | NO_A0 | `trayectoria_completa_cronologi` | 159 | NO | – | . | . | . | . | no |

## 3. Integridad Metodológica

- `core/` modificado: **NO**
- Gold o labels usados en generación/ranking: **NO** (auditoría 0 flags)
- A0-TEST evaluado: **NO (permanece ciego)**
