# Registro de Deuda Técnica

Bitácora formal de bugs de producción activos y deuda estructural pendiente. Cada item es independiente y trazable por ID. Un item no se cierra sin evidencia de fix (diff, test, repro) — ver lección `claim_passed_sin_artefacto_reproducible`.

Formato por item: `TD-<n>` · título · severidad · estado · fecha de detección · cita de código · impacto · fix propuesto.

---

## TD-001 — `vincular_por_sinonimos` genera aristas espurias por matching de substring

- **Severidad:** Alta (producción activa)
- **Estado:** Abierto
- **Fecha de detección:** 2026-08-09
- **Detectado por:** Claude Web (auditor externo) + Athena-OEC (verificación en código)

### Cita exacta

`core/sinapsis.py:391-393`:

```python
cerebro.cursor.execute(
    "SELECT concepto FROM largo_plazo WHERE estado = 'activo' AND concepto != ? "
    "AND (concepto LIKE ? OR sinonimos LIKE ?)",
    (concepto, f"%{termino}%", f"%{termino}%")
)
```

### Problema

El `SELECT` matchea por **substring** (`LIKE %termino%`) contra `concepto` y `sinonimos` de **todos** los nodos activos. Cualquier declaración manual de sinónimos que pase por `vincular_por_sinonimos` crea aristas `sinonimo_explicito` hacia conceptos que solo *contienen* el término como subcadena.

**Ejemplo concreto:** declarar `auto` como sinónimo matchea `auto_vincular`, `auto_guardado`, cualquier concepto con "auto" embebido → aristas espurias en el grafo, ruido en el salto multi-hop (`TIPOS_HOP` incluye `sinonimo_explicito` en `ppmi_hybrid_search.py:28`) y en el vectorizador (`ppmi_vectorizer.py:155`).

### Impacto

- Contamina el grafo de sinapsis con conexiones falsas.
- Se propaga a: búsqueda multi-hop (señal #13), `auto_vincular` de 3 capas, y PPMI vectorizer.
- **No es exclusivo del puente LLM nuevo** — afecta cualquier llamada a la función hoy, incluso sin el puente construido. Es un bug de producción vigente.

### Fix propuesto (candidato, no aplicado)

- Match por **token exacto** (split + comparación de token completo) en lugar de `LIKE %term%`, o
- Validación de candidatos: solo vincular si el término coincide exactamente con `concepto` (o token de `sinonimos`), no con prefijos/sufijos.

### Relación

- El puente LLM de sinonimia (`puente_llm_sinonimos_*`) **no** usa esta función para su upgrade selectivo: usa INSERT directo con par exacto (decisión 2026-08-09). Este bug es independiente y queda para fix aparte.
