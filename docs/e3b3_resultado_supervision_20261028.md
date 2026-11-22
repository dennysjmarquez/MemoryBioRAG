# E3B3 — resultado de las cuatro QA oficiales

Códigos de salida: {'snapshot_normal': 0, 'viva_normal': 0, 'snapshot_ruido': 1, 'viva_ruido': 1}. Las salidas 1 con ruido requieren comparación emparejada.

| Condición | Snapshot R@5 / R@1 / FP (B2 → B3) | Viva R@5 / R@1 / FP (B2 → B3) |
|---|---|---|
| Normal | 100.00 → 100.00 % / 95.31 → 95.31 % / 0/40 → 0/40 | 99.88 → 99.88 % / 93.53 → 93.53 % / 0/40 → 0/40 |
| Ruido zzqx | 97.34 → 97.34 % / 88.63 → 88.63 % / 0/40 → 0/40 | 96.63 → 96.63 % / 88.12 → 88.12 % / 0/40 → 0/40 |

Comparación oficial: sin regresión.

Patch productivo revertido: no.

**B3 cumplido en coreano; pendiente hueco 1.** Dennys aceptó 16→16: los tres puentes ya pasan, y el bloqueo restante es por sustantivos de un carácter.
Dennys autorizó publicar solo si las cuatro QA coinciden con B2 por categoría, R@1 y FP 0/40; esta supervisión no hace commit, push ni merge.

[Comparación completa](e3b3_comparacion_oficial_20261028.json) · [Categorías lado a lado](e3b3_categorias_oficial_20261028.md) · [Informe provisional](e3b3_validacion_puentes_20261028.md)
