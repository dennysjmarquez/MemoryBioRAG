# PROYECTO LADERA — Plan Consolidado v2

**Autor:** Athena-OEC (consolidado con aporte de Claude Web)
**Fecha:** 2026-08-11
**Estado:** FASE 0 — Diseño y validación conceptual
**Fuente:** Video @1bit1pixel3 "Grafo red neuronal" + PDF "Grafo red neuronal.pdf"

---

## 1. LO QUE EL PDF ENSEÑA QUE AÚN NO TENEMOS

El PDF describe el ciclo completo de una red neuronal en 7 pasos. Mapeamos cada uno a BioRAG:

| Paso del PDF | Texto literal | BioRAG actual | ¿Tenemos? |
|---|---|---|---|
| 1. Neurona | "multiplica cada entrada por un peso, las suma y aplasta con una curva" | `_calcular_score_hibrido()` | **SÍ** (forward pass) |
| 2. Capas | "apilarlas, de capa en capa aparecen formas complejas" | Señales ortogonales (13) | **SÍ** (una capa) |
| 3. Error | "compara su respuesta con la correcta, esa diferencia es el error" | No existe métrica por query | **NO** |
| 4. Loss landscape | "imagina ese error como un paisaje, cada peso es una dirección" | Nunca se visualizó | **NO** |
| 5. Gradiente | "la pendiente bajo tus pies te dice hacia dónde" | Pesos hardcoded | **NO** |
| 6. Backprop | "mides el error al final y lo empujas hacia atrás repartiendo culpa" | `aplicar_refuerzo_dopaminergico` solo nodo | **PARCIAL** |
| 7. Generalización | "la red nunca guardó ejemplos, solo movió números hasta que la forma quedó grabada" | Overfitting check con holdout | **NO** |

**Insight clave del PDF:** "Esta red tiene 151 pesos. Los modelos de lenguaje tienen cientos de miles de millones. Y bajaron por ese mismo paisaje." — BioRAG tiene **13 pesos**. Es un problema CHIQUITO comparado con cualquier LLM. Esto es una ventaja: se puede resolver con búsqueda por coordenadas, no necesita GPU.

---

## 2. INSIGHTS ESPECÍFICOS PARA NUESTRO SISTEMA

### 2.1 "La gracia es apilarlas" — Pero nosotros ya tenemos una capa
El PDF dice que las capas permiten "formas cada vez más complejas". BioRAG tiene UNA capa (weighted sum). Pero con 13 señales y 13 pesos, ya tiene 13^2 = 169 interacciones posibles si usáramos interacciones cuadráticas. Por ahora, mantener una capa es suficiente — el loss landscape nos dirá si necesitamos más.

### 2.2 "Al principio todos los pesos son al azar, la red está perdidísima"
Los pesos de BioRAG NO empezaron al azar — fueron elegidos por:
- v23.0: Ajuste manual de bm25 (0.18→0.25), concepto (0.12→0.08), sinonimos (0.12→0.08)
- v26.0: Activación de PPMI con weight=0.15
- Predicados SRL: weight=0.20

**Pregunta:** ¿Esos pesos están en un mínimo local o hay margen? El Loss Landscape (Fase 1) lo responde.

### 2.3 "Esa diferencia se resume en un solo número: el error"
Para BioRAG, el "error" de una query es:
```
error = 1.0 - rank_del_nodo_esperado / total_nodos_considerados
```
O más simple: `error = 0 si el nodo esperado está en top-5, 1 si no está`.

### 2.4 "Cada peso es una dirección en la que te puedes mover"
Los 13 pesos definen un espacio de 13 dimensiones. El loss landscape es una superficie en ese espacio. Cada punto es una configuración de pesos, la altura es el error promedio.

### 2.5 "Das un paso cuesta abajo, vuelves a mirar la pendiente y repites"
Esto es exactamente gradient descent:
```python
for epoch in range(max_epochs):
    gradiente = calcular_gradiente(pesos, dataset)
    pesos = pesos - learning_rate * gradiente
    if loss_estabilizado: break
```

### 2.6 "Repartiendo culpa cuánto tuvo que ver cada peso con el fallo"
Backpropagation para BioRAG:
```python
# Para cada query que falló:
for señal_i in señales:
    culpa_i = pesos[i] * señal_i[query] / score_total
# La señal con más culpa es la que más contribuyó al error
```

### 2.7 "La red nunca guardó ejemplos, solo movió números"
**Anti-sobreajuste:** El holdout del 20% NUNCA se toca durante el entrenamiento. Si el Recall sube en entrenamiento pero no en holdout → sobreajuste, no aprendizaje.

---

## 3. PLAN POR FASES CON METODOLOGÍA DE PRUEBA

### FASE 1 — Loss Landscape

**Objetivo:** Mapear cómo cambia el Recall al variar cada peso.

**Implementación:**
- Script `scripts/loss_landscape.py`
- Para cada peso i ∈ [0, 13]:
  - Fijar todos los pesos excepto i
  - Barre w_i en [0.0, 0.5] con paso 0.02 (25 puntos)
  - Para cada valor, corre los 921 casos QA
  - Registra Recall@1, Recall@5, Recall@10

**CÓMO PROBARLO:**
```bash
# 1. Correr el landscape
python3 scripts/loss_landscape.py --input scripts/casos_qa_baseline_v1.jsonl --output docs/loss_landscape.json

# 2. Verificar que genera gráficas
ls docs/loss_landscape_*.png

# 3. Verificar que los datos son coherentes
python3 -c "
import json
with open('docs/loss_landscape.json') as f:
    data = json.load(f)
print(f'Señales evaluadas: {len(data)}')
for señal in data:
    print(f'  {señal[\"nombre\"]}: recall_max={señal[\"recall_5_max\"]:.3f}, peso_actual={señal[\"peso_actual\"]}, margen={señal[\"margen_mejora\"]:.3f}')
"
```

**Criterio de éxito:** 
- Gráficas generadas ✓
- Al menos 1 señal con margen > 0.05 (si todas son < 0.05, el sistema ya está óptimo)
- Reporte en `docs/loss_landscape_report.md`

**Criterio de PARADA:** Si todas las señales tienen margen < 0.03, el sistema ya está en un mínimo local y las fases siguientes tienen poco sentido. Reportar y discutir con Dennys.

---

### FASE 2 — Gradient Descent Simbólico

**Objetivo:** Optimizar los 13 pesos automáticamente.

**Implementación:**
- Script `scripts/gradient_descent_pesos.py`
- Split: 80% entrenamiento (737 casos) / 20% holdout (184 casos)
- Split estratificado por categoría (literal, sinonimo, por_tema)
- Forward pass: weighted sum de las 13 señales
- Loss: cross-entropy loss (el nodo correcto debe tener score alto)
- Gradiente: diferencias finitas (∂loss/∂w_i ≈ (loss(w_i+ε) - loss(w_i-ε)) / 2ε)
- Update: Adam optimizer simple o SGD con lr adaptativo
- Max 100 épocas, early stop si loss no baja 0.001 en 10 épocas

**CÓMO PROBARLO:**
```bash
# 1. Correr gradient descent
python3 scripts/gradient_descent_pesos.py \
  --input scripts/casos_qa_baseline_v1.jsonl \
  --holdout 0.2 \
  --output scripts/pesos_optimizados.json \
  --report docs/gradient_descent_report.md

# 2. Verificar que los pesos cambiaron
python3 -c "
import json
with open('scripts/pesos_optimizados.json') as f:
    data = json.load(f)
print('Pesos antes vs después:')
for i, (antes, despues) in enumerate(zip(data['pesos_antes'], data['pesos_despues'])):
    delta = despues - antes
    print(f'  Señal {i}: {antes:.3f} → {despues:.3f} (Δ={delta:+.3f})')
print(f'Loss inicial: {data[\"loss_inicial\"]:.4f}')
print(f'Loss final: {data[\"loss_final\"]:.4f}')
print(f'Épocas: {data[\"epocas\"]}')
"

# 3. Verificar que NO hay sobreajuste
python3 -c "
import json
with open('docs/gradient_descent_report.md') as f:
    # Buscar las métricas de holdout
    content = f.read()
    if 'HOLDOUT' in content:
        print('✅ Holdout reportado — verificar que recall_holdout >= recall_baseline')
    else:
        print('⚠️ No se reportó holdout — POSIBLE SOBREAJUSTE')
"
```

**Criterio de éxito:**
- Loss final < loss inicial ✓
- Recall@5 en HOLDOUT ≥ Recall@5 baseline (86%)
- Si Recall@5 holdout < Recall@5 baseline → SOBREAJUSTE, reportar

**Criterio de PARADA:** Si después de 100 épocas el loss no bajó 0.01, el problema no es lineal y necesitamos otra aproximación.

---

### FASE 3 — Back Attribution

**Objetivo:** Para cada query fallida, qué señal causó el error.

**Implementación:**
- Script `scripts/back_attribution.py`
- Para cada query donde el nodo esperado NO está en top-5:
  - Corre forward pass con pesos actuales
  - Para cada señal i: `contribución_i = w_i * señal_i / sum(w_j * señal_j)`
  - Identifica qué señal le dio más score al nodo GANADOR (incorrecto)
  - Identifica qué señal le dio MENOS score al nodo ESPERADO (correcto)
  - Reporta la "brecha de culpabilidad"

**CÓMO PROBARLO:**
```bash
# 1. Correr back attribution
python3 scripts/back_attribution.py \
  --input scripts/casos_qa_baseline_v1.jsonl \
  --pesos scripts/pesos_optimizados.json \
  --output docs/back_attribution_report.md

# 2. Verificar que genera insights accionables
python3 -c "
with open('docs/back_attribution_report.md') as f:
    content = f.read()
    # Contar queries analizadas
    queries = content.count('Query')
    print(f'Queries analizadas: {queries}')
    # Verificar que hay recomendaciones
    if 'Recomendación' in content:
        print('✅ Hay recomendaciones accionables')
    else:
        print('⚠️ No hay recomendaciones')
"
```

**Criterio de éxito:**
- Lista de top-5 señales que más causan errores
- Al menos 3 queries con atribución clara (ej: "bm25 le dio 0.8 al nodo incorrecto")
- Recomendaciones accionables (ej: "subir peso de dim_score para queries por_tema")

---

### FASE 4 — Integración con Ciclo de Sueño

**Objetivo:** Que el sistema aprenda continuamente de queries reales.

**Implementación:**
- Modificar `ciclo_sueno_consolidacion()` para agregar:
  1. Leer últimas N queries de `log_busquedas`
  2. Para cada query con feedback (éxito/fallo):
     - Aplicar `aplicar_refuerzo_dopaminergico()` al nodo destino
     - Extender con back attribution: ajustar pesos de señales
  3. Guardar log de ajustes en `log_pesos_adaptivos`

- Nuevo parámetro: `BIORAG_ADAPTIVE_WEIGHTS=true/false` (default: false)

**CÓMO PROBARLO:**
```bash
# 1. Activar modo adaptativo
export BIORAG_ADAPTIVE_WEIGHTS=true

# 2. Correr 5 ciclos de sueño simulados
python3 -c "
from core.memory_store import BioRAG
rag = BioRAG('/path/to/db')
for i in range(5):
    print(f'Ciclo {i+1}...')
    rag.ciclo_sueno_consolidacion()
    pesos = rag.obtener_pesos_adaptivos()
    print(f'  Pesos: {pesos}')
"

# 3. Verificar que los pesos cambiaron
python3 -c "
import json
with open('log_pesos_adaptivos.jsonl') as f:
    lines = f.readlines()
print(f'Ciclos de ajuste: {len(lines)}')
ultimo = json.loads(lines[-1])
print(f'Pesos finales: {ultimo[\"pesos\"]}')
"

# 4. Verificar reversibilidad
export BIORAG_ADAPTIVE_WEIGHTS=false
# Correr query → debe volver al comportamiento anterior
```

**Criterio de éxito:**
- Los pesos se ajustan después de cada ciclo
- El Recall@5 no empeora (idealmente mejora)
- `BIORAG_ADAPTIVE_WEIGHTS=false` restaura comportamiento original

---

### FASE 5 — Benchmark Ablation (Evidencia Verificable)

**Objetivo:** Documentar mejora con rigor científico.

**Implementación:**
- Script `scripts/ablation_ladera.py`
- Flujo:
  1. Congelar snapshot ANTES: `snapshot_before_ladera.db`
  2. Correr 921 casos QA → baseline
  3. Aplicar Fase 2 (gradient descent) → pesos ajustados
  4. Correr 921 casos QA → post-ajuste
  5. Generar JSON con métricas antes/después
  6. Verificar holdout ≠ entrenamiento

**CÓMO PROBARLO:**
```bash
# 1. Correr ablation completa
python3 scripts/ablation_ladera.py \
  --input scripts/casos_qa_baseline_v1.jsonl \
  --output docs/ablation_ladera_$(date +%Y%m%d_%H%M%S).json

# 2. Verificar que el JSON tiene todo
python3 -c "
import json, glob
files = sorted(glob.glob('docs/ablation_ladera_*.json'))
with open(files[-1]) as f:
    data = json.load(f)
print(f'Fecha: {data[\"fecha\"]}')
print(f'Baseline Recall@5: {data[\"baseline\"][\"recall_5\"]:.3f}')
print(f'Post-ajuste Recall@5: {data[\"post_ajuste\"][\"recall_5\"]:.3f}')
print(f'Delta: {data[\"delta\"][\"recall_5\"]:+.3f}')
print(f'Holdout Recall@5: {data[\"holdout\"][\"recall_5\"]:.3f}')
print(f'Pesos antes: {data[\"pesos_antes\"]}')
print(f'Pesos después: {data[\"pesos_despues\"]}')
"

# 3. Verificar reproducibilidad (clean room)
python3 scripts/ablation_ladera.py \
  --input scripts/casos_qa_baseline_v1.jsonl \
  --output /tmp/verificacion.json
# Comparar con el original — deben ser idénticos
```

**Criterio de éxito:**
- JSON con baseline, post-ajuste, holdout, pesos antes/después
- Recall@5 holdout ≥ Recall@5 baseline (si no → sobreajuste)
- Snapshot congelado verificable
- Otro agente puede reproducir en clean room

---

## 4. ORDEN Y DEPENDENCIAS

```
FASE 1 (Loss Landscape) ← EMPEZAR AQUÍ
    │
    ├──→ ¿Margen > 0.03? ──NO──→ REPORTE: "Pesos ya óptimos, sistema en mínimo local"
    │
    └──→ SÍ ──→ FASE 2 (Gradient Descent)
                      │
                      ├──→ ¿Recall holdout ≥ baseline? ──NO──→ REPORTE: "Sobreajuste"
                      │
                      └──→ SÍ ──→ FASE 5 (Ablation) ← PRIMERO VERIFICAR
                                    │
                                    └──→ FASE 4 (Integración ciclo sueño)
                                          
         FASE 3 (Back Attribution) ← PUEDE CORRER EN PARALELO CON FASE 2
```

---

## 5. INVARIANTES

1. **Cero dependencias nuevas** — Python puro + numpy (ya instalado)
2. **Holdout siempre separado** — 20% nunca visto durante ajuste
3. **Evidencia verificable** — todo claim tiene snapshot + JSON reproducible
4. **Reversibilidad** — `BIORAG_ADAPTIVE_WEIGHTS=false` vuelve al original
5. **Honestidad** — si hay sobreajuste, se reporta como sobreajuste

---

## 6. RIESGOS

| Riesgo | Se detecta en | Acción |
|---|---|---|
| Loss landscape plano | Fase 1 | Parar, reportar que sistema ya está óptimo |
| Sobreajuste | Fase 2 (holdout) | Reducir learning rate, agregar regularización |
| Degradación post-ajuste | Fase 5 | Revertir pesos, reportar |
| Performance lenta | Fase 1 | Batch processing, cachear señales |

---

*"Entrenar es una sola cosa, bajar." — @1bit1pixel3*
*"Esta red tiene 151 pesos. BioRAG tiene 13. Es un problema chiquito." — Athena-OEC*
