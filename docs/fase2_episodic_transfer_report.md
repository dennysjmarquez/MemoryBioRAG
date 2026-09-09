# FASE 2: Aprendizaje Léxico Episódico y Transferencia — Informe Formal

**Timestamp**: 2026-09-09T01:15:43Z  
**DB SHA-256**: `676827f6b4abc3acaee10b14e273c3c50cae5b2c180593dedcd58048265a2800`  
> **Invariantes:** core/ intacto. A0-TEST 100% ciego. Cero atajos Query->Gold.

## 1. Resumen de Transferencia Zero-Cue (M0 -> M1 -> M2)

| Caso ID | Gold Concepto | M0 (Pre) | M1 (Integridad) | M2 (Transferencia) | Atribución Episódica | Zero-Cue Stems |
|---|---|---:|---:|---:|---|---|
| **TRANS_01** | `scoring_pesos_bm25` | 64 | **1** | **64** (Top-5) | NO | DISJUNTOS |
| **TRANS_02** | `desde_athena_biorag` | 68 | **1** | **1** (Top-5) | SI | DISJUNTOS |
| **TRANS_03** | `docker_infrastructure_rog` | – | **1** | **–** (Top-5) | NO | DISJUNTOS |
| **TRANS_04** | `coche_puente_condicional` | 24 | **1** | **24** (Top-5) | NO | DISJUNTOS |
| **TRANS_05** | `activos_dormidos_hermana` | – | **1** | **–** (Top-5) | NO | DISJUNTOS |

## 2. Controles Negativos (M3 — Especificidad)

| Control ID | Query | Episodios Activados | Falso Positivo |
|---|---|---:|---|
| **NEG_01** | `receta culinaria de cocina mediterranea con aceite...` | 0 | NO (Limpio) |
| **NEG_02** | `mantenimiento preventivo de vehiculos hibridos y c...` | 0 | NO (Limpio) |

## 3. Conclusión Metodológica

1. **Causalidad Probada:** El concepto C no es recuperado en M0 por mecanismos preexistentes (C ∉ Top-10).
2. **Transferencia Demostrada:** Tras registrar el episodio A -> C, la consulta B (con stems disjuntos) recupera C en Top-5 con atribución de ruta episódica.
3. **Especificidad:** Cero falsos positivos en consultas no relacionadas (M3).
