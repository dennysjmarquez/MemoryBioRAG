# Resultado: QA del snapshot en GitHub Actions (B3 frente a B4a), 2026-10-28

**Corrida:** https://github.com/dennysjmarquez/MemoryBioRAG/actions/runs/40753126307 (flujo `auditoria_qa_snapshot.yml`, commit `c454d0b`).
**Código medido:** rama del operador fijada en `4d8306155246e6f4bea4d28e9151cbd6630bad7f`; B4a = ese código + `docs/e3b4a_diff_aplicado_20261028.patch`.
**Huellas verificadas en cada trabajo, al inicio y al final:** `search.py` `f4479e7d…`, `memory_store.py` `b7e7219c…`, test `68f89c4c…`, snapshot `104dd290…`.
**Entorno:** contenedor Debian 12 (Python 3.11.2 / SQLite 3.40.1), dependencias de `requirements.txt`.
**Duración:** normal 12–15 min; con ruido 27–35 min. Todo en verde.

El cuadro de resumen lo transcribió el auditor de la captura que envió Dennys (la máquina del auditor no puede descargar los registros de GitHub).

| Escenario | B3 en GitHub (R@5 / R@1 / FP) | B4a en GitHub (R@5 / R@1 / FP) | B3 vs B4a (mismo entorno) | B3 Arena vs B3 GitHub |
|---|---|---|---|---|
| snapshot sin ruido | 100,0 / 95,31 / 0 de 40 | 100,0 / 95,31 / 0 de 40 | **IGUALES** | **IGUALES** |
| snapshot con ruido `zzqx` | 97,34 / 88,63 / 0 de 40 | 97,34 / 88,63 / 0 de 40 | **IGUALES** | **IGUALES** |

MRR: sin ruido 0,9718; con ruido 0,9281 (iguales en B3 y B4a). "IGUALES" significa que `comprobar_escenario` (de `scripts/comprobar_igualdad_qa_b3.py`) no encontró diferencias en: fuente, corpus, cada categoría, R@5 y R@1 honestos, métricas globales, FP 0/40 y censo temático.

**Conclusiones:**
1. En el snapshot, B4a no cambia nada respecto de B3: piso respetado.
2. **Reproducibilidad:** B3 medido en GitHub es idéntico, categoría por categoría, a B3 medido en Arena por el operador. El resultado se repite en otra máquina.
3. Pendiente para cerrar B4a: las 2 QA de la base viva (no se sube a GitHub; se corren en las máquinas de trabajo).
