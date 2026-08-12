# Reporte de implementación: umbral de capa 0.6 en gate QCR (2026-08-11)

## Cambio aplicado
`core/memory_store.py:4444-4463` — el escape binario del gate QCR
(`origen_tipo in ESCAPE_SET`) se reemplaza por umbral de capa configurable:
- `BIORAG_QCR_ESCAPE_CAPA_MIN` (default `0.60`)
- Condición: `ratio_qcr >= 0.50 OR (origen in ESCAPE_SET AND score_capa >= 0.60)`
- Documentado en el código el motivo y el costo residual aceptado.

## Re-run A/B real (evaluador real, 921 casos, snapshot congelado `snapshots/qa_escape_qcr_20260811.db`)
Corridas: `run_a_baseline_escape_binario.txt` (umbral -10 ≈ binario) vs `run_b_umbral_060.txt` (0.60).
Fallidos: `casos_fallidos_run_a_binario.jsonl` / `casos_fallidos_run_b_umbral060.jsonl`.

| Métrica | Binario | Umbral 0.6 | Δ |
|---|---|---|---|
| Recall@5 | 95.12% | 96.03% | +0.91pp |
| Recall@1 | 88.31% | 88.76% | +0.45pp |
| MRR | 0.910 | 0.916 | +0.006 |
| Errores positivas | 43 | 35 | -8 |
| FP binario (40 neg) | 10 | 10 | 0 |

## Resultado: POSITIVO, pero corrige la predicción post-hoc
- **Mejora real**: 8 queries ganadas, 0 perdidas; todas typo/variante_gramatical
  (el patrón que el análisis decía proteger). 0 TP perdidos.
- **El umbral NO redujo los FP binarios (10→10)**. Motivo: el gate es
  **NO-MONOTÓNICO** — si `filtrados_qcr` queda vacío, el `if filtrados_qcr:`
  no reemplaza la lista y el gate se auto-desactiva, dejando pasar ruido
  literal de score alto (ej. `'bufanda guitarra isla río'` → `ajuste_tejedora`
  0.735 literal; antes daba semantica 0.498). Los 17 FP-semantica se eliminan
  a nivel candidato, pero en queries negativas puras emerge ruido literal peor.
- Los 2 FP anómalos `simbolico` aceptados como costo (balón playa, fresa
  chocolate) siguen presentes — como se predijo.

## Decisión pendiente (no ejecutada)
Los FP de queries negativas requieren atacar el **ruido literal que emerge al
desactivarse el gate**, no el umbral de capa (ya probado: no ayuda). Opciones:
(a) definir comportamiento del filtrado vacío (riesgo de vaciar resultados
legítimos), (b) atacar ruido literal por otra vía (score/ranking), (c) aceptar
los 10 FP como costo conocido (2.5% de las negativas ya era el piso de diseño).

## Artefactos
- `core/memory_store.py` (cambio activo)
- `scripts/run_a_baseline_escape_binario.txt`, `scripts/run_b_umbral_060.txt`
- `scripts/casos_fallidos_run_a_binario.jsonl`, `scripts/casos_fallidos_run_b_umbral060.jsonl`
- `snapshots/qa_escape_qcr_20260811.db` (congelado, reproducible)
