# PLAN MAESTRO — BIORAG: EL SISTEMA QUE NO EXISTE TODAVÍA
**Fecha de creación:** 2026-08-19  
**Autor:** Artemis-OEC + Dennys Marquez  
**Propósito:** Este documento es la memoria completa del proyecto — lo que se intentó, lo que falló y por qué, lo que funciona, lo que se propone, y qué se espera lograr. Es un documento vivo: se actualiza con cada experimento.

---

## CAPÍTULO 0 — POR QUÉ ESTO PUEDE SER ÚNICO EN EL PLANETA

Los sistemas de memoria actuales (Pinecone, Weaviate, ChromaDB, LlamaIndex, Mem0) hacen todos lo mismo:
1. Texto → modelo de embeddings externo (OpenAI, Cohere, BGE, 768–1536 dimensiones) → vector
2. Vector → índice ANN (HNSW, IVF, etc.)
3. Búsqueda → coseno en ese espacio fijo

**Sus debilidades estructurales:**
- La similitud es una caja negra — no saben POR QUÉ dos cosas son parecidas
- El espacio vectorial es estático — no evoluciona con el uso
- No tienen grafo — no pueden razonar por asociación multi-hop
- No tienen memoria temporal — "nuevo" y "viejo" no existen
- No tienen plasticidad — no aprenden de su propio uso
- No tienen autonomía — no piensan cuando nadie los llama
- Requieren GPU, API externa, internet

**BioRAG ya los supera en arquitectura.** Lo que este plan define es cómo llevar esa ventaja a su límite matemático.

**Objetivo final:** Un sistema que, sin GPU, sin embeddings externos, sin internet, con pura matemática y lógica local, encuentre el recuerdo correcto sin importar cómo se busque — literal, semántico, por asociación, por tema, con errores, en otro idioma, con descripción periférica, con una sola palabra, con una pregunta de 50 palabras.

---

## CAPÍTULO 1 — ESTADO ACTUAL (BASELINE VERIFICADO)

### Métricas del baseline actual (v28.1, snapshot `qa_escape_qcr_20260811.db`, 921 casos)

| Métrica | Valor | Referencia |
|---------|-------|------------|
| R@5 global | **96.03%** | `run_b_umbral_060.txt` |
| R@1 global | **88.76%** | idem |
| MRR | **0.916** | idem |
| FP rate (queries negativas) | **25%** — problema activo | idem |
| FP rate live DB | **80%** — umbral absoluto no escala | `medir_ratio_produccion.py` |

### Por categoría (errores actuales sobre 921 casos)

| Categoría | R@5 | Cuello de botella conocido |
|-----------|-----|---------------------------|
| `literal` | ~99% | Casi resuelto |
| `typo` | Alta | FTS5 + Levenshtein |
| `variante_gramatical` | Alta | Stemmer + sinonimos |
| `pregunta_natural` | Alta | BM25 + predicados SRL |
| `cruce_idioma` | Media | Sinonimos explícitos |
| `por_tema` | **81.54%** (+13.85pp con Jaccard) | Señal vectorial + temática |
| `sinonimo` | **77%** | Ambigüedad inherente en queries de 1 palabra |
| `dormido` | Media | Ráfaga de reminiscencia |
| `negativo` (FP) | **FP=25%** | Umbral conforme no escala con corpus |

### Las 13 señales actuales en `_calcular_score_hibrido()`

```
#1  BM25 normalizado         peso=0.25   — FTS5 estadístico
#2  Dimensiones semánticas   peso=0.14   — 13 ejes × 102 valores, coseno binario
#3  Match en concepto        peso=0.08   — exacto en nombre del nodo
#4  Match en sinónimos       peso=0.08   — columna sinonimos
#5  Peso sináptico LTP/LTD   peso=0.10   — historial de uso Hebbiano
#6  Jaccard/cadena multi-hop peso=0.10   — score_latente o score_cadena
#7  Grupo semántico WordNet  peso=0.10   — lexname/grupo WordNet
#8  Similitud temática IDF   peso=0.08   — distribución dimensional
#9  Recencia temporal        peso=0.04   — penaliza nodos viejos
#10 Asociaciones             peso=0.02   — número de co-ocurrencias
#11 JSD                      peso=0.00   — apagado por defecto (JSD_WEIGHT=0)
#12 Predicados SRL           peso=0.20   — el más alto; canibalización documentada
#13 PPMI+SVD+Retrofit        peso=0.15   — vectores distribucionales 100-dims
```

**Total nominal = 1.34 (renormalizado internamente para sumar 1.0)**

---

## CAPÍTULO 2 — HISTORIA COMPLETA DE EXPERIMENTOS

### IMPORTANTÍSIMO — Por qué este capítulo existe

Cada idea que se proponga en este plan debe verificarse contra esta historia. Si ya se intentó algo similar y falló, el nuevo intento debe explicar qué es diferente esta vez — no repetir el camino con el mismo resultado.

---

### EXPERIMENTO E1: PPR — Diffusion of Heat (v25.1) → **DESCARTADO DEFINITIVAMENTE**

**Qué era:** Propagación de calor (Approximate Personalized PageRank push-based) sobre el grafo sináptico para alcanzar nodos no conectados textualmente.

**Por qué parecía prometedor:** la difusión de calor alcanza nodos lejanos en el grafo; parecía resolver queries que no matchean léxicamente.

**Qué salió mal:**
- El benchmark que mostraba mejora tenía un bug: nodos dormidos evaluados como activos (estado no filtrado)
- En evaluación limpia: **0% de mejora** sobre el baseline de 12 señales
- **+100–190ms de latencia** por query — inaceptable
- 100% de fallos con evaluación honesta

**Lección:** el cuello de botella no era el cableado del grafo — era el matching léxico/semántico. Agregar más sinapsis a nodos que no matchean no rescata nada si el sistema ya no los considera candidatos.

**Relación con propuestas nuevas:** La "Búsqueda por Resonancia" (OPT-NUEVA-1) NO es PPR. La diferencia crítica: PPR propaga calor indiscriminadamente. La Resonancia cuenta cuántos caminos INDEPENDIENTES desde SEMILLAS FTS5 YA MATCHEADAS convergen en un nodo candidato. Los candidatos ya son nodos que matchearon — la resonancia refina el ranking, no inventa candidatos nuevos. Este error no se repetiría.

---

### EXPERIMENTO E2: FCA — Reticulados de Galois (v25.1) → **DESCARTADO DEFINITIVAMENTE**

**Qué era:** Análisis Formal de Conceptos (reticulados de Galois) sobre las dimensiones semánticas para generar señal `por_tema`.

**Refutación en 3 capas:**
1. Frecuencia de dimensiones ≠ señal semántica (las más frecuentes son las genéricas, no las discriminantes)
2. Retículo completo 665×104 → explosión combinatoria; ninguna dimensión individual sostiene la jerarquía
3. Los clusters del retículo no son temáticamente coherentes — son intersecciones arbitrarias de dimensiones

**Lección:** la frecuencia no es semántica. Necesitas IDF dimensional, no conteo bruto. Esta lección ya está incorporada en OPT-5 (IDF dimensional en la Señal #2).

---

### EXPERIMENTO E3: Boost dimensional adicional (v25.0–v25.1) → **DESCARTADO**

**Qué era:** expandir el catálogo de 13 ejes a más dimensiones para mejorar discriminación.

**Resultado:** techo estructural medido < 2pp de mejora adicional. El catálogo de 13 ejes ya cubre el espacio semántico necesario. Más dimensiones = más ruido de combinación.

**Lección:** el problema no es cuántas dimensiones hay, sino cómo se ponderan (IDF dimensional pendiente).

---

### EXPERIMENTO E4: Fix de segmento SDM de dimensiones (v25.1) → **REVERTIDO**

**Qué era:** aplicar multi-proyección K al segmento de dimensiones del vector SDM 2048-bit.

**Resultado:** regresión de recall (54.3% → 43.1%). El segmento de dimensiones SDM funciona mejor con ventana contigua que con bits dispersos.

**Lección directa para propuestas SDM:** el layout actual del vector SDM (0-512: contenido, 512-768: concepto, 768-1792: dimensiones con ventana contigua, 1792-1920: categoría, 1920-2048: vecinos) es correcto tal como está. No tocar la estructura interna del vector SDM — usarlo, no modificarlo.

---

### EXPERIMENTO E5: Signal #12 Predicados SRL → **REFUTADO COMO GANANCIA REAL**

**Qué era:** señal de predicados SRL con peso 0.20 — el más alto del sistema.

**El engaño:** el +13.85pp histórico correspondía a un snapshot parcial (backfill de 614 nodos). El backfill completo canibaliza la señal — señales redundantes compitiendo por el mismo score.

**Estado actual:** peso 0.20 queda en el código con nota de canibalización documentada. No se recomienda subir este peso sin resolver primero la canibalización.

**Lección:** una señal aditiva con peso alto puede canibalizar otras señales cuando hay redundancia semántica. Esto motiva OPT-8 (Predicados como gate condicional, no señal aditiva siempre activa).

---

### EXPERIMENTO E6: Re-ranking Jaccard léxico (v25.2) → **GANADOR CONFIRMADO**

**Qué era:** re-ordenar el head (top-20) con score + 0.25 × jaccard/max_j, activado solo si el max jaccard de la ventana (50) supera el gate 0.04. Protect-r0: el nodo en posición 0 antes del re-ranking no se puede mover hacia abajo.

**Validación rigurosa:** holdout 50/50 estratificado, seed fija, 921 casos.

**Resultado verificado:**
- `por_tema` R@5: 67.69% → **81.54%** (+13.85pp)
- `por_tema` R@1: 60.00% → **76.92%** (+16.92pp)
- Cero regresiones en otras categorías (con protect-r0)
- Sensibilidad: `sinonimo` pierde 1 caso (id 0656) — conocido y aceptado

**Estado:** integrado en producción con flag `BIORAG_RERANKING_JACCARD_ENABLED=1`.

---

### EXPERIMENTO E7: Tejedora — Agujeros Estructurales (v25.2+) → **DESCARTADO DEFINITIVAMENTE**

**Qué era:** tejer sinapsis estructurales (Adamic-Adar) entre nodos con degree bajo y dimensiones compartidas.

**Resultado:** 13 sinapsis tejidas, 921 casos, R@5 idéntico al baseline (+0.000pp, byte a byte).

**Por qué no funcionó:** el cuello de botella NO es el cableado del grafo. Las aristas nuevas conectan islas que no llegan al top-5 de todas formas — el problema está antes, en el matching léxico/semántico.

**Lección crítica:** VERIFICADA EXPERIMENTALMENTE — agregar sinapsis no rescata casos. Para rescatar casos hay que mejorar el matching (recuperación de candidatos) o el scoring (clasificación de candidatos). No el grafo en sí.

**Implicación directa:** La propuesta de DMN → sinapsis latentes (OPT-6) no debe buscar mejorar el recall directamente vía sinapsis nuevas. Su valor está en alimentar la evocación multi-hop y el spreading activation, no en crear atajos estructurales que el sistema ya no usa.

---

### EXPERIMENTO E8: Retrofitting de vectores PPMI (Faruqui 2015) → **DESCARTADO EN ESTA FORMA**

**Qué era:** ajustar los vectores PPMI con el grafo de sinapsis `sinonimo_explicito` (7685 aristas). 8 configuraciones probadas.

**Por qué falló:** el grafo tiene nodos-hub de hasta 305 vecinos (mediana 9). Con alpha fijo, un hub de 305 vecinos reduce el vector original a ~0.4% del resultado. El retrofitting está diseñado para lexicones WordNet con pocos sinónimos por nodo — no para grafos de alta densidad.

**Lo que funciona:** el PPMI+SVD sin retrofitting sí aporta (ablación verificada: -0.57pp global, concentrado en `sinonimo` y `por_tema` cuando se apaga).

**Implicación:** el OPT-10 (PPMI enriquecido con paráfrasis) NO usa retrofitting — usa promedio ponderado de vectores de la query. No toca los vectores almacenados. No tiene el problema de hubs.

---

### EXPERIMENTO E9: Expansión de query por grafo 1 salto (sinonimo) → **SEÑAL REAL, NO LISTA**

**Qué era:** expandir la query a conceptos vecinos vía `sinonimo_explicito`, boost=MAX (no SUMA — la versión SUMA explotó por hubs).

**Resultado:** `sinonimo` 2/14→3/14 (+1 caso), pero `por_tema` 13/21→1/21 (colapso total).

**Por qué:** un solo peso global no puede servir a dos categorías con naturaleza distinta. Queries sinonímicas necesitan boost de expansión; queries temáticas se destruyen con él.

**Lección:** el ruteo por tipo de query (Sistema Dual, propuesta OPT-NUEVA-7) es la solución correcta. No una sola señal global para todo tipo de query.

---

### EXPERIMENTO E10: JSD con peso 0.05 → **SIN CASO CLARO TODAVÍA**

**Qué era:** activar la señal JSD con peso 0.05 (ya calculada en cada búsqueda, pero apagada por defecto).

**Resultado:** R@5 sin cambio global, R@1 +0.11pp, `por_tema` +1.5pp, `sinonimo` −1.6pp. Se cancelan casi exacto.

**Lección:** JSD necesita peso adaptativo por tipo de query (OPT-7) — peso bajo para `sinonimo` (una palabra), peso mayor para `por_tema` (múltiples tokens). Un peso global no funciona.

---

### EXPERIMENTO E11: Calibración conforme → **REVERTIDA (ratio de producción invalida el umbral)**

**Qué era:** activar `BIORAG_CALIBRACION_ACTIVA` con umbral 0.53.

**Primera decisión:** activar — FP bajó de 80% a 2.5% en evaluación sintética.

**Reversión inmediata:** `medir_ratio_produccion.py` midió ratio real 15–36:1 (con:sin respuesta) en 6134 consultas reales. Con este ratio, activar umbral 0.53 destruye más recall del que protege de FP. Se revirtió en la misma sesión.

**Lección:** el calibrador de umbral siempre depende del ratio real de producción, no de evaluaciones sintéticas. El ratio real (15–36:1) favorece umbral bajo. La calibración conforme correcta es la que implementa `calibrar_y_persistir()` — percentil invariante que se recalibra automáticamente cuando el corpus crece >20%.

---

### EXPERIMENTO E12: Ablación de GABA → **MECANISMO DE COLA, NO TOCA 6134 CONSULTAS**

**Resultado:** GABA dispara en 64.7% de consultas reales (top1≥0.80), pero caso por caso 0 rankings cambian. El mecanismo atenúa competidores con score < top_score×0.70 — combinación que no ocurrió en ninguna de las 6134 consultas + 921 del benchmark.

**Estado:** correcto pero inerte con el corpus actual. Puede ser necesario con documentos casi-duplicados compitiendo cerca del líder.

---

### EXPERIMENTO E13: Ampliación de ventana por empate (18-ago-2026) → **INTEGRADO**

**Qué era:** para queries ≤2 palabras (página 1), ampliar la ventana devuelta (+10) si hay candidatos justo debajo del corte con score ≥90% del último incluido.

**Resultado verificado:** 7 casos que antes tenían found_rank=null ahora aparecen en posición 6-11. 0 regresiones. 0 nuevos FP.

**Límite conocido:** tope +10 es arbitrario. No rescata casos con rank real > 15 (ej. "buscar", rank 21).

---

## CAPÍTULO 3 — DIAGNÓSTICO DE TECNOLOGÍA DORMIDA (hallazgos de auditoría real del código)

### SDM completamente desconectada del pipeline de búsqueda

**Verificado en código:** `buscar_sdm()` existe en `core/sdm.py:502`. El sistema indexa vectores 2048-bit por nodo. Los mantiene actualizados con dirty-sets y reindex selectivo automático en cada consolidación. Pero hay **cero llamadas** a `buscar_sdm()` en `memory_store.py` o `mcp_server.py` dentro del path de búsqueda.

El vector SDM de 2048 bits tiene estructura rica:
- bits 0-512: tokens de contenido (ventana 4 bits/token, IDF ponderada)
- bits 512-768: tokens de concepto
- bits 768-1792: dimensiones semánticas hebbianas (PESO_DIMENSION=2.5 — las más pesadas)
- bits 1792-1920: categoría
- bits 1920-2048: vecinos sinápticos

Y la similitud ponderada por segmento (`similitud_sdm()`, L272) ya existe. Solo falta llamarla desde la búsqueda.

**Nota crítica:** el segmento de dimensiones (E4) se probó con multi-proyección K y regresó. La solución correcta es usar el vector SDM tal como está actualmente, sin modificar su estructura interna.

### Spreading activation llega demasiado tarde

`_evocacion_por_cadena()` (Fallback 1.9) solo se activa cuando hay `< 3 resultados` de todas las capas anteriores. Si FTS5 devuelve 5 nodos incorrectos, la evocación nunca dispara. Los nodos equivocados bloquean el mecanismo más bio-inspirado del sistema.

### HDC Binding construye vectores ricos pero nadie los consulta para buscar

El binding HDC (`hdc_bind_bytes()`, L153 de `core/sdm.py`) codifica contexto + categoría en el vector. Esto se usa al indexar pero el vector resultante nunca se usa para ranking.

### DMN genera insights pero no los retroalimenta al grafo de búsqueda

Las hipótesis del daemon DMN se guardan como nodos normales. No crean sinapsis reforzadas entre los conceptos que sintetizaron. El razonamiento autónomo del sistema no tiene impacto en búsquedas futuras.

### Comunidades de Label Propagation existen pero no se usan en scoring

`core/auto_clustering.py` detecta comunidades densas en consolidación. Se guardan con nombre temático. Pero en `buscar_por_frase`, ninguna señal usa la membresía de comunidad del candidato vs. la comunidad inferida de la query.

### JSD calculada pero peso=0 por defecto

JSD se calcula en cada búsqueda pero no aporta al score final. El experimento E10 mostró que con peso global no funciona — necesita activación adaptativa.

### Señal de feedback (dopamina/RPE) sin uso real

6134 consultas en `log_busquedas`, solo 38 (0.6%) con feedback explícito, y todas con `util=0` — nunca se registró un `util=1`. El mecanismo existe y está cableado pero no se usa en la práctica.

---

## CAPÍTULO 4 — PROPUESTAS DE MEJORA (ordenadas por prioridad)

### CRITERIO DE PRIORIDAD
Toda propuesta debe pasar este filtro antes de implementarse:
1. ¿Ya se intentó algo similar? (ver Capítulo 2)
2. ¿Cuál es el mecanismo exacto por el que esperamos mejora?
3. ¿Cómo lo verificamos contra los 921 casos con DB fresca por config?
4. ¿Qué regresiones podemos esperar y en qué categorías?

---

### OPT-1: Activar SDM como Fallback 2.5 (**PRIORIDAD ALTA**)

**Diferencia respecto a experimentos fallidos:** PPR (E1) propagaba calor a nodos que no matcheaban como candidatos. SDM como Fallback 2.5 se activa solo cuando TODAS las capas léxicas fallan (< 3 resultados) — genera candidatos por similitud binaria estructural, no por propaganda de calor. La analogía correcta: es un tipo distinto de recuperación de candidatos, no un ajuste de ranking sobre candidatos léxicos.

**Mecanismo:** generar vector SDM de la query → buscar en tabla `nodos_sdm` por distancia de Hamming (ya implementado en `buscar_sdm()`) → merging con la lista de candidatos actual.

**Implementación (~ 20 líneas):**
```python
# En buscar_por_frase(), después del Fallback 2.1 (simbólico/Levenshtein)
# Solo si: < 3 resultados Y query tiene >= 3 tokens Y no es modo estricto
if not modo_estricto and len(todos) < 3 and len(q_tokens_qcr) >= 3:
    try:
        from core.sdm import buscar_sdm, generar_vector_sdm
        sdm_results = buscar_sdm(cerebro=self, query=query, radio_max=400, limite=5)
        for r in sdm_results:
            if r['concepto'] not in seen_conceptos:
                todos.append(r)
                seen_conceptos.add(r['concepto'])
    except Exception:
        pass  # SDM es opcional, no bloquea
```

**Verificación:** comparar R@5/R@1/MRR/FP antes y después contra snapshot. Atención especial a categorías `dormido` y consultas de descripción periférica.

**Riesgo:** bajo — es el último fallback, no toca el scoring de capas anteriores. Si no ayuda, se desactiva con flag.

---

### OPT-2: SDM score como Señal #14 en el scoring loop (**PRIORIDAD ALTA**)

**Mecanismo:** pre-calcular el vector SDM de la query una sola vez antes del loop de scoring (igual que se hace con el vector PPMI). Para cada candidato, recuperar su vector SDM de `nodos_sdm` y calcular `similitud_sdm()`. Añadir como señal con peso 0.05–0.08.

**Nota sobre el layout SDM:** NO modificar la estructura interna del vector. El layout actual (probado y validado en v25.1) es correcto. Solo leer los vectores existentes.

**Costo computacional:** un SELECT por candidato a `nodos_sdm` puede ser caro en corpus grande. Solución: pre-cargar el diccionario `{concepto: vector_bytes}` en memoria al inicio de la búsqueda (misma estrategia que el índice PPMI).

**Verificación:** ablación OFF→ON, mismo protocolo que E12 (DB fresca por config).

---

### OPT-3: QCR ponderado por IDF (**PRIORIDAD ALTA — mejora matemática más correcta**)

**El problema actual:** el QCR Gate decide si un candidato pasa o no con:
```
ratio_qcr = tokens_que_matchean / tokens_totales_query
umbral = 0.50
```
Un candidato donde matchean 2 tokens muy raros sobre 5 tokens de la query da ratio 0.40 y se filtra. Pero esos 2 tokens raros pueden ser los más informativos de toda la query.

**La solución:**
```python
# IDF ya disponible en self._ppmi_index.token_freq (o calcular desde large_plazo)
def calcular_qcr_idf(q_tokens, contenido_candidato, token_freq, n_docs):
    q_tokens_set = set(q_tokens)
    matches = q_tokens_set & set(_tokenizar(contenido_candidato))
    if not matches or not q_tokens_set:
        return 0.0
    idf = lambda t: math.log((n_docs + 1) / (token_freq.get(t, 1) + 1)) + 1.0
    return sum(idf(t) for t in matches) / sum(idf(t) for t in q_tokens_set)
```

**Calibración del nuevo umbral:** probablemente 0.35–0.45 (más bajo que 0.50 porque tokens raros aportan más señal, el denominador sube). Verificar contra los 921 casos que el cambio de umbral no sube FP.

**Por qué es diferente de E2/E3:** no agrega dimensiones ni sinapsis. Cambia la función de decisión del gate QCR — de binaria/uniforme a ponderada-por-información.

---

### OPT-4: Spreading activation como señal proactiva, no fallback (**PRIORIDAD MEDIA**)

**El problema:** `_evocacion_por_cadena()` solo se activa si hay < 3 resultados. Una query temática puede traer 5 nodos incorrectos y bloquear el mecanismo.

**La solución:** calcular un score de "caminos sinápticos" para los top-50 candidatos post-FTS5:
```python
def score_cadena_proactivo(semillas_fts, candidato, grafo_sinapsis, max_saltos=2):
    """¿Está el candidato alcanzable desde alguna semilla FTS en ≤ max_saltos?"""
    for semilla in semillas_fts:
        visitados = {semilla}
        frontera = [(semilla, 1.0, 0)]  # (nodo, peso_acumulado, saltos)
        while frontera:
            nodo, peso, saltos = frontera.pop(0)
            if saltos >= max_saltos:
                continue
            for vecino, peso_arista in grafo.get(nodo, []):
                if vecino == candidato:
                    return min(1.0, peso * peso_arista)
                if vecino not in visitados and peso * peso_arista >= 0.1:
                    visitados.add(vecino)
                    frontera.append((vecino, peso * peso_arista, saltos + 1))
    return 0.0
```
Añadir como señal con peso 0.05 en `_calcular_score_hibrido()`.

**Costo computacional:** O(semillas × grado_promedio²). Con 5 semillas y grado promedio 10 (mediana 9, verificado): 500 operaciones por candidato. Aceptable para top-50.

**Precaución:** verificar que no genera los mismos problemas de hub que el retrofitting (E8). Los hubs del grafo (hasta 305 vecinos) podrían dominar el score de cadena. Solución: limitar a aristas con peso >= 0.3.

---

### OPT-5: IDF dimensional en la Señal #2 (**PRIORIDAD MEDIA**)

**El problema:** el coseno dimensional usa peso binario. Una dimensión compartida por 5% de nodos discrimina igual que una compartida por 80%.

**Solución:** calcular IDF por dimensión al inicio de la búsqueda (o pre-calcular en consolidación):
```python
dim_counts = {dim_id: count for dim_id, count in 
              self.cursor.execute("SELECT dimension_id, COUNT(*) FROM largo_plazo_dimensiones GROUP BY dimension_id")}
n_nodos = self._contar_nodos_corpus()
idf_dim = {d: math.log((n_nodos + 1) / (c + 1)) + 1.0 for d, c in dim_counts.items()}
```
Usar `idf_dim[d]` en el coseno dimensional en lugar del peso fijo del eje.

**Diferencia respecto a E2 (FCA):** E2 usó frecuencia de dimensiones como señal semántica directa. OPT-5 usa IDF dimensional como PESO en el coseno existente — es diferente en concepto y en implementación. La frecuencia baja = raro = peso MAYOR en OPT-5, exactamente lo contrario del error de E2.

---

### OPT-6: DMN cierra el loop → sinapsis latentes de síntesis (**PRIORIDAD MEDIA**)

**Qué hace actualmente el DMN:** genera hipótesis A→B→C en `_bucle_dmn()` y las guarda como nodos normales. No crea conexiones entre A y C.

**Propuesta:** cuando el DMN sintetiza una hipótesis conectando A→B→C, crear sinapsis `A↔C` tipo `dmn_synthesized` con peso inicial 0.3 (baja confianza — se refuerza si una búsqueda futura la activa vía feedback dopaminérgico).

**Diferencia respecto a E7 (Tejedora):** E7 creó sinapsis estructurales entre nodos con degree bajo — no mejoró recall porque los nodos no llegaban al top-5 de todas formas. OPT-6 crea sinapsis de SÍNTESIS SEMÁNTICA entre nodos que el DMN conectó por razonamiento, no por estructura del grafo. Son conexiones con significado conceptual, no topológico.

**Advertencia derivada de E7:** incluso las sinapsis semánticas no mejoran el recall directamente si los nodos no entran al pool de candidatos. El valor de esta propuesta está en alimentar el spreading activation (OPT-4), no en crear atajos directos.

---

### OPT-7: JSD con peso adaptativo por tipo de query (**PRIORIDAD MEDIA**)

**Derivado de E10:** JSD con peso global 0.05 no funciona. Se cancela entre `por_tema` (+1.5pp) y `sinonimo` (-1.6pp).

**Solución:** peso dinámico según la query:
```python
jsd_weight_efectivo = JSD_WEIGHT * (2.5 if len(q_tokens_qcr) >= 4 else 0.5)
```
Queries largas (temáticas, ≥4 tokens) → JSD pesa más.
Queries cortas (sinonímicas, 1-2 tokens) → JSD pesa menos o nada.

**Verificación:** medir impacto separado por categoría con este ajuste. Esperar ganancia en `por_tema`, neutralidad en `sinonimo`.

---

### OPT-8: Predicados SRL como gate condicional (**PRIORIDAD MEDIA**)

**Problema documentado:** Signal #12 (peso 0.20 — el más alto) tiene canibalización documentada con el Jaccard re-ranking. El peso alto siempre activo puede robar relevancia en queries donde los predicados no aportan (ej. queries de 1-2 palabras).

**Propuesta:**
```python
from core.srl_extractor import extraer_predicados_query
preds_query = extraer_predicados_query(query)
# Solo usar pred_score si la query tiene estructura predicativa detectada
pred_weight_efectivo = 0.20 if (preds_query and len(preds_query) > 0) else 0.0
```

**Advertencia:** el SRL extractor puede ser costoso. Pre-calcularlo una sola vez por búsqueda, antes del loop de candidatos.

---

### OPT-NUEVA-1: Búsqueda por Resonancia (**PRIORIDAD ALTA — NUEVA, no intentada**)

**Concepto:** la query genera semillas FTS5 (nodos que matchean léxicamente). Cada semilla se propaga por el grafo de sinapsis (BFS, ≤3 saltos). Un nodo candidato que es alcanzado por **múltiples semillas independientes** resuena — tiene evidencia convergente de múltiples fuentes semánticas distintas.

**Diferencia crítica respecto a E1 (PPR):**
- PPR: propaga calor desde UN nodo semilla a TODO el grafo, sin distinción de candidatos
- Resonancia: propaga BFS desde MÚLTIPLES semillas FTS5 YA MATCHEADAS, mide convergencia en candidatos conocidos

La resonancia no genera candidatos nuevos — refina el ranking de candidatos que ya pasaron el filtro léxico. PPR generaba candidatos sin ningún filtro.

```python
def calcular_resonancia(semillas_fts5, grafo_sinapsis, max_saltos=2):
    """Para cada nodo en el grafo, cuenta cuántas semillas FTS5 lo alcanzan independientemente."""
    alcanzado_por = defaultdict(set)
    for semilla in semillas_fts5:
        visitados = {semilla}
        frontera = [(semilla, 0)]
        while frontera:
            nodo, saltos = frontera.pop(0)
            if saltos >= max_saltos:
                continue
            for vecino, peso in grafo_sinapsis.get(nodo, []):
                if vecino not in visitados and peso >= 0.3:
                    visitados.add(vecino)
                    alcanzado_por[vecino].add(semilla)
                    frontera.append((vecino, saltos + 1))
    # Score de resonancia: ratio de semillas que alcanzan el nodo
    n_semillas = max(len(semillas_fts5), 1)
    return {nodo: len(semillas) / n_semillas 
            for nodo, semillas in alcanzado_por.items()
            if len(semillas) >= 2}  # Mínimo 2 caminos convergentes para resonar
```
Peso sugerido en scoring: 0.08 (a evaluar con benchmark).

---

### OPT-NUEVA-2: NCD — Similitud por Compresión (Kolmogorov aproximado) (**PRIORIDAD MEDIA — NUEVA**)

**Concepto:** si comprimimos la query y un nodo juntos, y el resultado comprimido es más corto que comprimirlos separados, comparten estructura informacional — son "sobre lo mismo" aunque no compartan palabras.

```python
import zlib
def ncd(x: str, y: str) -> float:
    """Normalized Compression Distance — similitud universal sin léxico ni idioma."""
    xb, yb = x.encode('utf-8'), y.encode('utf-8')
    cx = len(zlib.compress(xb, level=9))
    cy = len(zlib.compress(yb, level=9))
    cxy = len(zlib.compress(xb + b' ' + yb, level=9))
    if max(cx, cy) == 0:
        return 1.0
    return (cxy - min(cx, cy)) / max(cx, cy)

# score_ncd = 1.0 - ncd(query, f"{concepto} {contenido[:300]}")
```

**Por qué es ortogonal a todas las señales actuales:**
- BM25: estadístico sobre frecuencia de tokens
- PPMI+SVD: distribucional sobre co-ocurrencia
- SDM: binario estructural sobre features del nodo
- NCD: informacional sobre patrón comprimible compartido

Un artículo técnico sobre "gestión de errores en sistemas distribuidos" y una memoria sobre "cómo manejé el fallo de mi servidor" tienen NCD bajo aunque no compartan ni una palabra técnica.

**Costo:** ~50μs por par (zlib es C nativo). Para 1000 candidatos: 50ms. Solo calcular para candidatos ya en el pool post-FTS5 (no para todo el corpus). Peso sugerido: 0.05.

---

### OPT-NUEVA-3: Hopfield + SDM — Recuperación de Queries Parciales (**PRIORIDAD MEDIA — NUEVA**)

**Concepto:** la query incompleta es un vector SDM parcialmente conocido. Los vectores SDM de los nodos son los "atractores" de una red de Hopfield. El sistema "relaja" el vector de la query hacia el atractor más cercano — completando la información faltante.

**Diferencia con SDM simple (OPT-1, OPT-2):** SDM hace búsqueda por distancia de Hamming directa. Hopfield+SDM hace iteración convergente — el vector de la query se actualiza en cada paso acercándose al patrón almacenado, lo que amplifica señales débiles y suprime ruido.

**Implementación (sin GPU, puras operaciones numpy sobre arrays binarios):**
```python
def hopfield_recall_binario(vec_query: bytes, memorias: list[tuple[str, bytes]], 
                             max_iter: int = 5) -> list[tuple[float, str]]:
    state = np.unpackbits(np.frombuffer(vec_query, dtype=np.uint8)).astype(np.float64)
    patterns = [(nombre, np.unpackbits(np.frombuffer(v, dtype=np.uint8)).astype(np.float64)) 
                for nombre, v in memorias]
    
    for _ in range(max_iter):
        similarities = np.array([np.dot(state, p) for _, p in patterns])
        # Softmax moderno (Ramsauer 2020) — capacidad exponencial
        exp_s = np.exp(similarities - similarities.max())
        weights = exp_s / exp_s.sum()
        new_state = sum(w * p for w, (_, p) in zip(weights, patterns))
        new_state = (new_state > 0.5).astype(np.float64)
        if np.allclose(new_state, state, atol=0.01):
            break
        state = new_state
    
    final_sims = [(np.dot(state, p) / len(state), nombre) 
                  for nombre, p in patterns]
    final_sims.sort(reverse=True)
    return final_sims

# Usar: solo cuando len(todos) == 0 (Fallback de último recurso)
# Los patrones son nodos_sdm pre-cargados en memoria
```

**Cuándo activa:** cuando todas las capas fallan (0 resultados). Converge en 3-5 iteraciones.

**Advertencia de rendimiento:** el bucle sobre todos los nodos es O(N). Para corpus de 1000 nodos con vectores 2048-bit: ~200ms. Aceptable como fallback de último recurso. Optimizable con pre-carga en RAM.

---

### OPT-NUEVA-4: Pesos Hebbianos Adaptativos entre Señales (**PRIORIDAD BAJA — NUEVA**)

**Concepto:** los 13 pesos del scoring son estáticos. Pero el peso óptimo de cada señal depende del tipo de query. Una query de nombre exacto necesita BM25 alto y predicados bajo. Una query temática necesita PPMI alto y BM25 bajo.

**Implementación:** matriz de correlación W almacenada en SQLite, actualizada con cada feedback real:
```python
# Tabla nueva: scoring_adaptativo
# ctx: vector de features binarias de la query (8 features)
# signals: vector de scores de las 13 señales para el hit ganador
# W: matriz 8 × 13 de pesos aprendidos

# En biorag_feedback() positivo:
ctx = extraer_contexto_query(query)   # 8 features binarias
signals = scores_del_top1_ganador     # 13 floats
W += eta * np.outer(ctx, signals)     # regla Hebbiana
# En búsqueda futura:
pesos_dinamicos = softmax(W @ ctx)    # 13 pesos normalizados
```

**Precondición:** el mecanismo de feedback (biorag_feedback) tiene que empezar a usarse. Actualmente 38/6134 consultas tienen feedback, todas con util=0. Antes de implementar pesos adaptativos, resolver por qué el feedback no se registra en producción.

---

### OPT-NUEVA-5: Detección de Huecos de Conocimiento (**PRIORIDAD MEDIA — NUEVA, metacognición**)

**Concepto:** cuando la query cae en una región del grafo donde los nodos cercanos pertenecen a comunidades DISTINTAS y están POCO conectados entre sí, el sistema está en un "hueco de conocimiento" — no tiene información directa sobre ese tema.

En lugar de devolver un resultado de baja confianza (lo que hace ahora), el sistema debería decirlo explícitamente:
```json
{
  "estado": "hueco_de_conocimiento",
  "fronteras": [
    {"comunidad": "neurociencia_computacional", "nodo_frontera": "redes_hopfield"},
    {"comunidad": "teoria_informacion", "nodo_frontera": "entropia_shannon"}
  ],
  "sugerencia": "No tengo información directa. El tema está entre neurociencia computacional y teoría de información."
}
```

**Implementación eficiente:** verificar comunidad de los top-5 candidatos. Si ≥ 2 comunidades distintas y la densidad de sinapsis entre esos candidatos es < 0.2 → hueco detectado.

**Valor:** el sistema sabe cuándo no sabe — metacognición artificial. Esto es más honesto que devolver un resultado de score 0.35 como si fuera confiable.

---

## CAPÍTULO 5 — OBJETIVOS Y EXPECTATIVAS POR PROPUESTA

### Qué se espera lograr con cada propuesta

| Propuesta | Categorías objetivo | Mejora esperada | Riesgo de regresión |
|-----------|--------------------|-----------------|--------------------|
| OPT-1 SDM Fallback | `dormido`, queries vagas sin match léxico | +2-5% en casos que hoy dan 0 resultados | Bajo (último fallback) |
| OPT-2 SDM Señal #14 | `sinonimo`, `por_tema` | +0.5-1.5pp si hay candidatos SDM relevantes | Bajo-medio (señal pequeña 0.05-0.08) |
| OPT-3 QCR-IDF | Todos — reduce filtrado incorrecto | +0.5-2pp en categorías que usan tokens raros | Medio (puede subir FP si umbral mal calibrado) |
| OPT-4 Spreading activation | `por_tema`, `dormido` | +1-3pp en queries temáticas con red sináptica rica | Medio (costo computacional, hubs) |
| OPT-5 IDF dimensional | `por_tema`, dimensiones específicas | +0.5-1pp | Bajo |
| OPT-6 DMN→sinapsis | Largo plazo — asociaciones | Mejora gradual con el tiempo | Bajo (sinapsis con peso bajo) |
| OPT-7 JSD adaptativo | `por_tema` +1pp, `sinonimo` neutro | Suma limpia donde E10 se cancelaba | Bajo |
| OPT-8 SRL gate | Queries largas temáticas | Reducción de canibalización | Bajo-medio |
| OPT-NUEVA-1 Resonancia | `por_tema` multi-token | +2-4pp en queries con semillas ricas | Medio |
| OPT-NUEVA-2 NCD | Queries trans-vocabulario | Rescata casos sin match léxico ni vectorial | Bajo (señal pequeña) |
| OPT-NUEVA-3 Hopfield | Fallback de último recurso | Rescata queries con 0 resultados actualmente | Bajo (solo como fallback) |
| OPT-NUEVA-4 Pesos Hebbianos | Todos — largo plazo | Auto-optimización con el uso real | Alto — requiere feedback activo primero |
| OPT-NUEVA-5 Huecos | UX + honestidad epistémica | No mejora R@5, mejora calidad de respuesta | Ninguno |

---

## CAPÍTULO 6 — LO QUE HABRÍA QUE INVENTAR (MATEMÁTICA NUEVA)

### INVENCIÓN 1: Score de Coherencia Narrativa

Un conjunto de nodos tiene coherencia narrativa si sus predicados SRL forman una cadena causal: objeto(A) ≈ sujeto(B) ≈ objeto(B) ≈ sujeto(C). Este score colectivo debería ser mayor que la suma de sus partes individuales.

```
score_narrativa(A,B,C) = Σ score_individual + 0.2 × coherencia_srl(A→B→C)
coherencia_srl = 1.0 si objeto(A) == sujeto(B) AND objeto(B) == sujeto(C)
```

Ningún motor de recuperación del mundo puntúa la coherencia narrativa de un conjunto de resultados.

### INVENCIÓN 2: Memoria Episódica Temporal

Los nodos creados en la misma sesión (ventana ±24h) forman un "episodio". Una query con intención temporal activa el episodio completo, no nodos individuales. Esto es recuperación episódica — distinta de la recuperación semántica y la recuperación por asociación.

### INVENCIÓN 3: Campo Semántico Contextual

En lugar de representar nodos como puntos (vectores), representarlos como campos gaussianos en el espacio PPMI:
```
Φ_N(x) = peso_sinaptico × exp(-||x - pos_N||² / (2σ²_N))
```
La búsqueda no encuentra el punto más cercano — encuentra la región del espacio donde el campo combinado de todos los nodos es máximo. Nodos aislados generan campo débil; clusters temáticos generan campo fuerte colectivo.

### INVENCIÓN 4: Termodinámica Cognitiva (diagnóstico del sistema)

Modelar el sistema como termodinámico: E (energía sináptica), S (entropía de activación), T (temperatura = tasa de actividad reciente). La energía libre F = E - T·S determina cuándo el DMN debe activarse y qué debe explorar. Los sistemas termodinámicos tienen "temperatura de trabajo" óptima — F muy alta o muy baja indica desequilibrio.

### INVENCIÓN 5: Analogía Relacional (de búsqueda a razonamiento)

Si la DB sabe que "Dennys CREÓ BioRAG", y se pregunta "¿qué CREÓ Einstein?", la respuesta es el nodo cuyo vector PPMI es más cercano a `vec(Einstein) - vec(Dennys) + vec(BioRAG)`. Razonamiento por analogía semántica con los vectores distribucionales ya existentes — sin LLM.

---

## CAPÍTULO 7 — PLAN DE IMPLEMENTACIÓN POR FASES

### Fase 0 — Pre-requisito: activar el feedback real
**Duración estimada:** 1 sesión  
**Por qué:** OPT-NUEVA-4 (pesos adaptativos) depende de feedback real. Actualmente 0/6134 consultas tienen util=1. Investigar por qué y resolver antes de depender de esa señal.

### Fase 1 — Conectar tecnología dormida (SDM)
**Duración estimada:** 1-2 sesiones  
**Propuestas:** OPT-1 + OPT-2  
**Verificación:** eval QA antes/después vs. snapshot. DB fresca por config (lección de E12).  
**Gate de progreso:** R@5 debe mantenerse ≥ 96.03%. R@1 debe mantenerse ≥ 88.76%.

### Fase 2 — Mejora matemática del gate QCR
**Duración estimada:** 1 sesión  
**Propuestas:** OPT-3  
**Verificación:** medir FP rate antes/después (no debe subir). Medir por categoría.  
**Calibración:** usar IDF del índice PPMI ya calculado. Umbral nuevo: barrido 0.30-0.45.

### Fase 3 — Señales proactivas
**Duración estimada:** 2-3 sesiones  
**Propuestas:** OPT-4 (spreading activation proactivo) + OPT-NUEVA-1 (Resonancia)  
**Advertencia de rendimiento:** medir latencia antes de integrar. OPT-NUEVA-1 es O(semillas × grado²), aceptable. OPT-4 puede ser costoso con hubs de 305 vecinos — limitar a peso_arista ≥ 0.3.

### Fase 4 — Señales ortogonales nuevas
**Duración estimada:** 2-3 sesiones  
**Propuestas:** OPT-NUEVA-2 (NCD) + OPT-7 (JSD adaptativo) + OPT-8 (SRL gate)  
**Metodología:** un cambio a la vez, benchmark completo entre cada cambio.

### Fase 5 — Refinamiento de señales existentes
**Duración estimada:** 1-2 sesiones  
**Propuestas:** OPT-5 (IDF dimensional) + OPT-6 (DMN→sinapsis)

### Fase 6 — Matemática avanzada (investigación activa)
**Duración estimada:** indefinida  
**Propuestas:** OPT-NUEVA-3 (Hopfield), OPT-NUEVA-4 (pesos adaptativos), OPT-NUEVA-5 (huecos)  
**Metodología:** un experimento a la vez con benchmark antes/después. Si no supera baseline, documentar en EXPERIMENTS.md y descartar.

### Fase 7 — Inventar (requiere fundamento empírico previo)
**Propuestas:** Coherencia narrativa, Memoria episódica, Campo semántico, Termodinámica  
**Pre-requisito:** Fases 1-5 completas. Métricas actuales > 97% R@5, > 91% R@1.

---

## CAPÍTULO 8 — REGLAS INMUTABLES DE ESTE PROYECTO

1. **Un cambio a la vez.** Nunca implementar dos propuestas simultáneamente.
2. **DB fresca por config.** buscar_por_frase despierta nodos dormidos — contamina comparaciones (lección E12).
3. **Verificación dual obligatoria.** Snapshot + copia de DB viva. Un fix que solo pasa en snapshot no es fix de producción (caso 0757, commit d6678b3).
4. **Si el número cambió, explicar por qué.** Nunca sobrescribir una métrica sin decir qué la cambió.
5. **El ratio de producción decide el umbral.** No el benchmark sintético. Ratio real medido: 15-36:1 (lección de E11).
6. **Medir también si el benchmark puede medir el mecanismo** (lección de E12, DMN). Un resultado idéntico puede ser contaminación, no que el mecanismo no aporte.
7. **La imaginación construye la hipótesis. El experimento real decide si es verdad.** (Einstein + Eddington, 1919)

---

## CAPÍTULO 9 — ESTADO AL DÍA (actualizar con cada sesión)

**Última actualización:** 2026-08-19  
**Fase activa:** Pre-implementación (análisis y documentación)  
**Próxima acción:** iniciar Fase 1 (SDM como Fallback 2.5 + Señal #14)  
**Baseline de referencia:** R@5 96.03%, R@1 88.76%, MRR 0.916, FP 25% (snapshot `qa_escape_qcr_20260811.db`)  

---

*"Nosotros vamos a quedar mejor que cualquier otro sistema. Vamos a ser únicos en el planeta Tierra."  
— Dennys Marquez, 2026-08-19*

*Ese objetivo no es aspiracional. Es el resultado lógico de implementar, con rigor experimental, lo que este documento describe.*
