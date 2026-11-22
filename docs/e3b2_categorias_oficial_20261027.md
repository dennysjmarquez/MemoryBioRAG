# E3B2 — QA oficial por categoría

Cada celda expresa **B1 → B2**. R@5 y R@1 son honestas.
Snapshot y copia viva aparecen lado a lado.

## Sin ruido

| Categoría | Snapshot R@5 | Snapshot R@1 | Viva R@5 | Viva R@1 |
|---|---:|---:|---:|---:|
| cruce_idioma | 8/8 → 8/8 | 5/8 → 5/8 | 8/8 → 8/8 | 5/8 → 5/8 |
| dormido | 65/65 → 65/65 | 65/65 → 65/65 | 65/65 → 65/65 | 65/65 → 65/65 |
| literal | 487/487 → 487/487 | 485/487 → 485/487 | 487/487 → 487/487 | 484/487 → 484/487 |
| por_tema | 65/65 → 65/65 | 45/65 → 45/65 | 64/65 → 64/65 | 41/65 → 41/65 |
| pregunta_natural | 65/65 → 65/65 | 63/65 → 63/65 | 65/65 → 65/65 | 62/65 → 62/65 |
| sinonimo | 45/45 → 45/45 | 29/33 → 29/33 | 41/41 → 41/41 | 27/30 → 27/30 |
| typo | 65/65 → 65/65 | 60/65 → 60/65 | 65/65 → 65/65 | 57/65 → 57/65 |
| variante_gramatical | 65/65 → 65/65 | 61/65 → 61/65 | 65/65 → 65/65 | 54/65 → 54/65 |
| **Global** | 865/865 → 865/865 | 813/853 → 813/853 | 860/861 → 860/861 | 795/850 → 795/850 |

| Negativos (FP) | Snapshot B1 → B2 | Viva B1 → B2 |
|---|---:|---:|
| negativo | 0/40 → 0/40 | 0/40 → 0/40 |

- Snapshot: 0 fallos R@5 nuevos; 0 recuperados.
- Viva: 0 fallos R@5 nuevos; 0 recuperados.

## Con ruido `zzqx`

| Categoría | Snapshot R@5 | Snapshot R@1 | Viva R@5 | Viva R@1 |
|---|---:|---:|---:|---:|
| cruce_idioma | 5/8 → 5/8 | 4/8 → 4/8 | 5/8 → 5/8 | 5/8 → 5/8 |
| dormido | 64/65 → 64/65 | 62/65 → 62/65 | 64/65 → 64/65 | 64/65 → 64/65 |
| literal | 484/487 → 484/487 | 445/487 → 445/487 | 480/487 → 480/487 | 445/487 → 445/487 |
| por_tema | 62/65 → 62/65 | 44/65 → 44/65 | 60/65 → 60/65 | 37/65 → 37/65 |
| pregunta_natural | 64/65 → 64/65 | 61/65 → 61/65 | 65/65 → 65/65 | 63/65 → 63/65 |
| sinonimo | 40/45 → 40/45 | 26/33 → 26/33 | 35/41 → 35/41 | 24/30 → 24/30 |
| typo | 61/65 → 61/65 | 59/65 → 59/65 | 63/65 → 63/65 | 59/65 → 59/65 |
| variante_gramatical | 62/65 → 62/65 | 55/65 → 55/65 | 60/65 → 60/65 | 52/65 → 52/65 |
| **Global** | 842/865 → 842/865 | 756/853 → 756/853 | 832/861 → 832/861 | 749/850 → 749/850 |

| Negativos (FP) | Snapshot B1 → B2 | Viva B1 → B2 |
|---|---:|---:|
| negativo | 0/40 → 0/40 | 0/40 → 0/40 |

- Snapshot: 0 fallos R@5 nuevos; 0 recuperados.
- Viva: 0 fallos R@5 nuevos; 0 recuperados.
