# Constitución del Proyecto MemoryBioRAG

> **Versión:** 1.0 | **Fecha:** 2026-09-16
> **Propósito:** Principios innegociables que rigen todo desarrollo en este proyecto.

---

## 1. Identidad del Proyecto

**MemoryBioRAG** es una arquitectura de memoria cognitiva biomimética y simbólica para agentes de IA.

- **Paradigma:** Python puro + SQLite FTS5. Cero embeddings densos, cero GPU, cero llamadas a APIs externas en el path de búsqueda.
- **Motor:** SQLite FTS5 WAL + Factorización PPMI-SVD (100 dims) + Espacio Semántico de 13 Ejes + Grafo Sináptico Hebbiano + Sparse Distributed Memory (SDM 2048-bit) + Calibración Conforme.
- **Idiomas:** Español + Inglés (stemming bilingüe ES/EN + expansión simbólica vía WordNet + Domain Dict automático).

## 2. El Inverso Fundamental

> **BioRAG no piensa. El agente piensa.**

BioRAG es la **memoria externa** del agente — no su cognición. El trabajo cognitivo (entender la pregunta, diseñar la estrategia de búsqueda, interpretar los resultados) lo hace el agente. BioRAG aporta la memoria. El agente aporta la inteligencia.

**Consecuencia directa:** Cuando el usuario habla en lenguaje natural, el agente **no puede** reenviar las palabras literales a la memoria. Debe descomponer, reformular y traducir al vocabulario del dominio.

## 3. Pilares Inmutables

### Pilar 1: Cero Regresiones
- Antes de cualquier cambio, medir métricas baseline.
- Después del cambio, verificar que NINGUNA métrica empeoró.
- Si hay regresión: **REVERSIÓN INMEDIATA**. No se negocia.

### Pilar 2: Un Cambio a la Vez
- Nunca probar múltiples hipótesis o cambios simultáneamente.
- Aislar cada cambio, medir Antes vs Después, registrar métricas exactas.
- Si cualquier métrica regresa: revertir inmediatamente.

### Pilar 3: Fallos Visibles
- Datos faltantes, tokens no indexados, discrepancias de DB deben fallar de forma visible (excepciones, logs descriptivos).
- **NUNCA** devolver defaults silenciosos (como `0.0`, arrays vacíos, o fallback null) que puedan confundirse con resultados válidos.

### Pilar 4: Sin Prosas sin Resultados Concretos
- Nunca reportar números asumidos, simulados o esperados como hechos verificados.
- Cada afirmación de éxito, mejora o regresión debe probarse con outputs de comandos verbatim (diffs, resúmenes de benchmark, corridas de pytest).

### Pilar 5: Verificación Dual
- Verificar contra el snapshot congelado **NO** es suficiente.
- **Dual Verification:** Snapshot (regresión matemática) + Copia de DB activa (resolución en mundo real).
- Si un fix pasa en el snapshot pero falla en la copia activa: **NO está resuelto**.

### Pilar 6: Diseño Universal UX-First
- Antes de construir, justificar: ¿Quién lo usa? ¿Existe otra ruta natural? ¿Vale la pena el peso técnico?
- **PROHIBICIÓN ESTRICTA:** Nunca hardcodear vocabularios de dominio, diccionarios o términos internos del proyecto en el motor. El sistema debe permanecer 100% agnóstico al dominio.

### Pilar 7: Validación Fail-Fast
- Toda validación de parámetros ocurre ANTES de escribir en la base de datos.
- Si un parámetro es inválido, retornar error accionable INMEDIATAMENTE.
- Nunca dejar estado parcial en la DB.

### Pilar 8: Sin Features Fantasma
- Campos opcionales sin consecuencias reales se convierten en campos fantasma (97% de nodos sin bridges lo demuestran).
- Si un campo es importante, debe ser obligatorio o tener nudge visible que fuerce su uso.

## 4. Stack Técnico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.x puro |
| Base de datos | SQLite 3 + FTS5 (WAL mode) |
| Motor semántico | PPMI + SVD (100 dims) + Retrofitting Hebbiano |
| Grafo | Sinapsis Hebbianas (tabla `sinapsis`) |
| Memoria hiperdimensional | SDM 2048-bit (Kanerva 1988) |
| Calibración | Conforme (Vovk 2005, α=0.10) |
| Servidor | MCP (Model Context Protocol) via FastAPI/Stdio |
| Tests | pytest |
| Snapshot congelado | `snapshots/qa_escape_qcr_20260811.db` |

## 5. Comandos de Verificación (Obligatorios antes de cualquier release)

```bash
# 1. Suite de tests unitarios
python3 -m pytest tests/ -v

# 2. Benchmark QA completo (921 casos, snapshot congelado)
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/evaluar_qa.py

# 3. Abismo Léxico (cero solapamiento léxico)
BIORAG_PATH=snapshots/qa_escape_qcr_20260811.db python3 scripts/test_abismo_lexico.py

# 4. Fuzzing adversarial (33 casos)
python3 scripts/fuzz_qa.py

# 5. Concurrencia (20 hilos + 20 clientes HTTP)
python3 scripts/concurrencia_qa.py
```

## 6. Métricas Oficiales de Referencia (v31.3)

| Métrica | Valor | Gate |
|---|---|---|
| Recall@5 Global | 98.06% | ≥ 97.0% |
| Recall@1 (Top-1) | 90.74% | ≥ 88.0% |
| MRR | 0.9355 | ≥ 0.90 |
| Tasa de FP | 0.0% (0/40) | = 0.0% |
| Tests Unitarios | 168/168 PASSED | 100% |

## 7. Flujo de Desarrollo Obligatorio

1. **Leer** AGENTS.md y esta constitución antes de tocar código.
2. **Medir** baseline: `pytest tests/ -v` + `evaluar_qa.py` + `test_abismo_lexico.py`.
3. **Planear** el cambio (spec → plan → tasks).
4. **Implementar** un cambio a la vez.
5. **Verificar** post-cambio: mismos comandos que el paso 2.
6. **Comparar** métricas Antes vs Después.
7. **Si hay regresión:** revertir inmediatamente.
8. **Si no hay regresión:** documentar el cambio con evidencia concreta.

## 8. Fuera de Alcance Permanente

- Dependencias de hardware pesado (GPU, TPU).
- Llamadas a APIs externas en el path de búsqueda.
- Hardcoding de vocabularios de dominio.
- Modificación de pesos BM25 sin verificación completa de regresión.
- Campos opcionales sin consecuencias (anti-patrón "campo fantasma").
