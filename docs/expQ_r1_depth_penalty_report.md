# EXP-Q-R1: Depth-Penalized BFS — Fix del Comportamiento No-Monótono

**Fecha**: 2026-09-08T23:10:29  
**DB SHA-256**: `5f37b11b7163ac7e3284640a80ad5674da7978608b6e2c371cfc6512d998ec29`

## Hipótesis (Claude, verificada matemáticamente)

El comportamiento no-monótono de EXP-Q (gold rescatado en cw=2 pero
perdido en cw=3) es una consecuencia determinista de:
- Pool crudo crece **combinatoriamente** con la profundidad
- `max_contextos` crece **linealmente** (15 × depth)
- La fórmula de score actual no penaliza nodos de mayor profundidad

**Fix**: aplicar un factor multiplicativo `depth_decay^nivel` al score
de cada nodo según su profundidad en el BFS.

## Tabla Comparativa

| depth_decay | Generaciones | Casos Rescatados | Violaciones Monótonas | FP Negativos |
|:--:|:--:|:--:|:--:|:--:|
| 1.0 | 2 | 2/5 | 2 | 0 |
| 0.8 | 2 | 2/5 | 0 | 0 | ✅ ÓPTIMO
| 0.7 | 2 | 2/5 | 0 | 0 | ✅ ÓPTIMO
| 0.6 | 2 | 2/5 | 0 | 0 | ✅ ÓPTIMO
| 0.5 | 2 | 2/5 | 0 | 0 | ✅ ÓPTIMO

## Veredicto

**DEPTH_DECAY_MEJORA_MONOTONIA**

depth_decay=0.8 maximiza generaciones (2) con 0 violaciones monotónicas y 0 FP. La hipótesis de Claude es correcta: el BFS no-monótono se resuelve con penalización de score por profundidad.

---
*EXP-Q-R1 — core/ invariante — snapshot read-only*