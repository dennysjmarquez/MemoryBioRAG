# Auditoría de posicionamiento — MemoryBioRAG v31.1 (2026-09-13)

Objetivo norte: **que el recuerdo correcto APAREZCA, siempre** (abismo léxico 100%).
Método: solo lectura sobre `arena/01a08e29-memorybiorag` @ `40990c8`. Todo lo marcado
VERIFICADO tiene línea de código; lo demás es HIPÓTESIS explícita.

## 1. Camino completo de una búsqueda (VERIFICADO)

Entrada: MCP `_recordar` → `buscar_por_frase(..., context_window=0)` hardcoded
(`mcp_server.py:848-861`). El 921 usa el mismo entry (+`ignore_peso_sinaptico=True`).

```
query
  │ ① probe FTS5-AND → _necesita_expansion (=True solo si 0 hits) [4816-4836]
  │ ② expansión query: Hub-terms [4853-4867] + WordNet [4873+] — SOLO si probe=0
  │ ③ POOL (todos): LIKE → FTS-AND → unicode61 → trigram-typo → latente →
  │    substring → snap → 1.9 cadena (pool<3) → 2.1 simbólico → 2.2 spreading
  │    (pool<3) → 2.5 SDM/E1 (pool<3, ≥3 toks) → merge concepto → sinónimos →
  │    episodios léxicos Fase-C (SIEMPRE) → semántica → por_tema → PRF-dims →
  │    fallback dimensional (umbral)
  │ ④ precompute pool: bm25, grupo-WN, pred-SRL, jsd-E7, PPMI-vec, NCD-E6,
  │    episodio-F2, analogía-F3(OFF), campo-F5, multihop(OFF)
  │ ⑤ loop → _calcular_score_hibrido (14 señales) → sort [6292-6320]
  │ ⑥ promo lexico_aprendido (≥0.88) → QCR-E3 (compuestas) → hub-canónico
  │    competitivo → GABA (top1≥0.80) → PALABRA_PREFIJO (1 palabra) →
  │    monotonía → fecha → multiplicador(opt) → paginar → wake-on-access →
  │    context_window (=0 en prod: NO corre) → preview → variaciones →
  │    SRL-fallback → trazabilidad → episodio expans.(OFF) → ADN (OFF) →
  │    telemetría → epistémico side-channel → RETURN [6637-6708]
```

Ramas SEPARADAS (no compiten en el ranking primario): `buscar_por_rafaga`
(contingencia MCP, señales reducidas), `expandir_contexto_vecinos` (rescate
grafo: append, no ranking), sueño/DMN (escritura diferida).

## 2. Señales calculadas pero no aprovechadas (VERIFICADO)

| Señal | Costo pagado | Uso real |
|---|---|---|
| Vectores SDM 2048-bit ×N nodos + dirty/reindex | escritura, indexación, tablas | solo E1 (pool<3, ≥3 toks); en 921 ≈ 0 rescates |
| Grafo 13.8k sinapsis | sueño, DMN, E10, BFS | generación solo pool<3 (8/921 = cadena-1.9); ranking 0% |
| Epistémico (`last_estado_epistemico`) | hook en cada búsqueda | **cero consumidores** (write-only) |
| Hub matching | cada búsqueda | 5 hubs = cobertura ~0 fuera de sus temas |
| Expansión Hub-terms + WordNet | código + probe | solo si probe FTS-AND = 0 (casi nunca) |
| F3 analogía / F4 termo / multihop / ADN / jaccard-rerank | mantenido, testeado | OFF (documentado, pendiente A/B) |
| Ráfaga (rescate MCP) | path completo | sin hub/ppmi/pred/señales-pool cuando más importan |

Bien aprovechadas (lo que SÍ funciona): PPMI 0.15, hub-canónico 0.20,
NCD 0.05, F2 0.05, F5 0.05, JSD-E7, QCR-E3, GABA, SRL-live, dimensional-umbral.

## 3. Mecanismos que podrían conectarse y no lo están (VERIFICADO)

1. **Grafo → ranking primario (LA #1).** `expandir_contexto_vecinos` corre fuera
   del híbrido; sus candidatos nunca compiten. El abismo #29 es el síntoma.
2. **Episodios léxicos → MCP aprender.** `ensenar_lexico` solo vía service/bench;
   MCP enseña solo vía hubs (bridges manuales del agente). Dos canales sin puente.
3. **Epistémico → retrieval.** Publica vacío/incierto; nadie lo lee (E13 purgado).
4. **DMN/sueño → retrieval.** E10 A/B plano (0.00): sus aristas solo importan en
   paths pool<3. Lo aprendido de noche no mueve el día.
5. **Hubs → cobertura.** 5 hubs manuales; `log_busquedas` + fallos-921 existen y
   nadie mina bridges de ellos.
6. **C1-morfología → core.** Validada (EXP-N8), archivada en `experimentos/`.
7. **F3/F4 → gate.** Pendientes del Plan Maestro.
8. **Multihop → admission policy.** Falta el separador (veredicto documentado).
9. HIPÓTESIS: feedback (log guarda top-5 para atribución) → ¿quién lo consume
   para enseñar? No verificado.

## 4. Tecnología desperdiciada (ranking)

1. Grafo + sueño + DMN + E10 (≈0% efecto en primaria). 2. Vectores SDM.
3. C1 validada sin integrar. 4. Epistémico write-only. 5. HDC huérfano,
   RCIL/FCC prototipos, 50 scripts en `experimentos/`. 6. Islas/LPA (9/13
   oracular huérfano). 7. F3/F4 OFF. 8. Episodios sin MCP. 9. Bridges manuales.

## 5. Siguiente paso inteligente (PROPUESTA, no ejecutado)

**Conexión #1: candidatos del grafo al pool primario con admisión estricta**
(top-K por energía + score_floor) para que COMPITAN en híbrido+QCR. Convierte el
rescate #29 en ranking medible. Gate propuesto: posiciones abismo + 921 sin
regresión + FP=0. Requiere autorización explícita (regla no-F6).
Alternativa menor: cablear `ensenar_lexico` a MCP aprender (cierra el loop).
