# EXP-Q-R2: Absolute Depth Decay — Fix del Compounding de EXP-Q-R1

**Fecha**: 2026-09-08T23:30:16
**SHA inicial**: `1574d72178f21f057edd4841cc545c63be6507273fe55e6cd58709e4666d4b00`  
**SHA final**: `1574d72178f21f057edd4841cc545c63be6507273fe55e6cd58709e4666d4b00`  
**SHA estable**: ✅

## Corrección Implementada (Claude, 2026-09-08)

EXP-Q-R1 aplicaba el decay dos veces (compuesto recursivamente).
Este experimento aplica el decay una sola vez sobre el score del
primario de origen (`score_raiz`), sin heredar el decay del padre.

```
EXP-Q-R1: score_nivel2 = (score_nivel1 * 0.6 + w * 0.2) * decay²
           donde score_nivel1 = (score_raiz * 0.6 + w * 0.2) * decay¹
           → decay compuesto: más agresivo de lo documentado

EXP-Q-R2: score_nivel2 = (score_raiz * 0.6 + w * 0.2) * decay²
           donde score_raiz es el score del primario original
           → decay absoluto: una sola aplicación, predecible
```

## Tabla Comparativa

| decay | Gen | MonoViol | FP_neg | CASE_02 | CASE_05 |
|:--:|:--:|:--:|:--:|:--:|:--:|
| 1.0 | 2 | 1 | 0 | cw=2/R29 | cw=1/R7 |
| 0.9 | 2 | 0 | 0 | cw=3/R38 | cw=1/R7 |
| 0.8 | 2 | 0 | 0 | cw=3/R38 | cw=1/R7 |
| 0.7 | 2 | 0 | 0 | cw=3/R38 | cw=1/R7 |
| 0.6 | 2 | 0 | 0 | cw=3/R38 | cw=1/R7 |
| 0.5 | 2 | 0 | 0 | cw=3/R38 | cw=1/R7 |

## Veredicto

**ABSOLUTE_DECAY_MEJORA_PERO_NO_CW2**

decay=0.9 logra 0 violaciones y 0 FP, pero CASE_02 sigue en cw=3. El decay absoluto mejora la precisión del score pero el problema de CASE_02 es estructural (camino de nivel-2 genuinamente saturado).

---
*EXP-Q-R2 — core/ invariante — BFS usa con_ro (read-only)*