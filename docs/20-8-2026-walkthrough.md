# Walkthrough — Sesión de Búsqueda del "Acertijo" (20 fallos restantes)

## Estado Final
- **Baseline preservada**: R@5 97.73%, R@1 87.40%, MRR 0.912, 20 fallos retrieval
- **Código**: `memory_store.py` solo tiene +8 líneas (comentario documentando AUDIT #15)
- **0 regresiones**

## Descubrimiento Principal: La Causa Raíz Real

> [!IMPORTANT]
> **El problema NO es de scoring — es el tokenizador trigram de FTS5 que genera un "efecto embudo invertido".**

### El Efecto Embudo Invertido (descubierto empíricamente)

Para queries con variantes morfológicas (ej. "cuando usado dimensione biorags"):

```
FTS5 AND: 0 resultados (ningún nodo tiene TODOS los tokens)
FTS5 OR:  200 resultados (trigram matchea substrings de "cuando", "usado" en todo el corpus)
```

Esto genera un **pool de 200+ nodos de ruido** donde el target **NO está** (porque "dimensione" ≠ "dimensiones" para trigram con LIMIT 200).

**Consecuencia catastrófica**: TODOS los fallbacks inteligentes tienen guarda `len(todos) < 3`:
- Spreading Activation ✅ funciona (rescata 27 queries) — pero no para estos casos
- Content Expansion: target SÍ está ahí (matches=2), pero `len(todos) = 200` → **BLOQUEADO**
- PPMI Vector: target tiene coseno 0.7255 (rank #1), pero `len(todos) = 200` → **BLOQUEADO**

**Los fallbacks que rescatarían al target están bloqueados por el ruido de FTS5 OR.**

## Experimentos Realizados (todos revertidos)

| # | Experimento | Tipo | Resultado | Causa del fallo |
|---|---|---|---|---|
| 1 | Signal #14 Content Coverage (aditivo, peso 0.10) | Scoring | 21 fallos (+1) | Boost de 0.07 insuficiente para gap de 0.17; ruido en queries 1 palabra |
| 2 | Signal #14 Logit Bonus (+1.0) | Scoring | 22 fallos (+2) | Competidores también cumplen condición; scores inflados |
| 3 | PPMI Retrieval (pool < 3, antes de SA) | Retrieval | 22 fallos (+2) | Mató Spreading Activation (27→1 queries) |
| 4 | PPMI Retrieval (pool < 3, después de SA) | Retrieval | 20 fallos (=) | Pool siempre ≥ 3 por fallbacks previos — 0 rescates |
| 5 | PPMI Retrieval (always-on, cos > 0.55) | Retrieval | 26 fallos (+6) | Inyecta ruido masivo en queries funcionales |
| 6 | Auditoría C Adamic-Adar (sesión anterior) | Retrieval | 21 fallos (+1) | Expansión ruidosa; target no tiene sinapsis directa |

## Los 20 Fallos: Clasificación Definitiva

### Grupo A — FTS5 Trigram Noise (6+2 = 8 casos)
**variante_gramatical (6)** + **typo (2)**

Target EXISTE en mecanismos alternativos (PPMI coseno 0.72, Content Expansion matches=2) pero FTS5 OR llena el pool con 200+ nodos de ruido → fallbacks bloqueados.

**Solución propuesta** (no implementada): **Quality Gate en FTS5 OR** — podar resultados con BM25 < umbral ANTES de contar pool size. O usar **MinHash LSH** (Hack 3 del reviewer) para bypass directo.

### Grupo B — Pool Saturation (4 casos por_tema)
Target ESTÁ en el pool (#19 de 50) pero 18 competidores lo superan en hybrid score.

**Caso 0640** "ráfaga después resultado" → mentalidad_biorag_para_agentes:
- FTS5 lo encuentra (#3 por BM25)
- Los 3 tokens de la query están en el contenido del target
- PPMI coseno = 0.4871 (mejor que 3 de 5 competidores)
- Pero hybrid score = 0.3018 vs líder 0.4749 (gap 0.17)

**Solución propuesta**: **Hack 1** del reviewer (A×A^T Higher-Order Proximity) para que la SVD coloque "ráfaga" y "mentalidad" cercanos en el espacio latente.

### Grupo C — Ambigüedad Genuina (4 sinónimo + 1 pregunta_natural = 5 casos)
Queries de 1 palabra ("memoria", "buscar", "identidad") donde 10+ nodos legítimos compiten.

**Sin solución algorítmica** — requiere contexto de sesión del usuario.

### Grupo D — Datos (3 literal)
Nodos con coma vs "y" en el nombre. Corrección de datos.

## Siguientes Pasos Viables (ordenados por impacto/costo)

### 1. Quality Gate para FTS5 OR (impacto: 6-8 casos, costo: bajo)
Podar el pool de FTS5 OR eliminando nodos con BM25 muy bajo antes de contar `len(todos)`. Esto permite que Content Expansion y PPMI retrieval (con guarda `< 3`) se activen para queries con matches ruidosos.

### 2. MinHash LSH para variantes morfológicas (impacto: 6 casos, costo: medio)
Hack 3 del reviewer: tabla SQLite con firmas MinHash de n-gramas de caracteres. "dimensione" y "dimensiones" generan la misma firma. Bypass completo de FTS5 para matching morfológico.

### 3. Higher-Order Proximity Matrix (impacto: 4 casos por_tema, costo: alto)
Hack 1: computar A×A^T antes de SVD para que nodos con vecinos comunes (como "ráfaga" y "mentalidad") queden cercanos en el espacio espectral.

## Archivos Modificados
- [`memory_store.py`](file:///mnt/recursos_compartidos_y_otros/MemoryBioRAG/core/memory_store.py#L4921-L4926) — solo comentario AUDIT #15 (+8 líneas)

## Commits Pendientes
El único cambio es el comentario documentando por qué se descartó AUDIT #15. Se puede hacer commit como documentación o descartar.
