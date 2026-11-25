# Experimento 18 — Protocolo v3: autoexamen sináptico, resonancia limpia, homeostasis y puentes que solo ordenan

**Fijado y subido ANTES de medir** (2026-11-25).
- Aprobado por Dennys el mismo día: norma 4 intacta; PPMI, LSA y SDM fuera; autoexamen sináptico; homeostasis;
  el puente solo ordena; E3 bloqueada hasta pasar E1 y E2; los «ojos Unicode» del nacimiento van en otro ciclo.
- **Sustituye a la v2.** La v1 y la v2 quedan como están: con la v2 no se midió nada.

## 0. Enmiendas antes de medir (25-11, prueba de humo con 1 idioma; ningún criterio calculado todavía)

- **A1 — `profundidad="profundo"` en el repaso.** §2 decía `buscar_por_frase(pista, limite=6, …)` sin fijar la
  profundidad. Con el valor por defecto (`"activos"`), las 9 de 24 memorias que el sueño deja en estado `dormido`
  solo aparecen por el atajo «Snap» (`search.py` L1047–1060), que depende de `ultimo_acceso`. Ese campo lo
  reescriben las búsquedas anteriores: es una vía de estado. En la prueba, `activos` dejó entre 6 y 28 de 132
  pistas sin resultado, según el estado; `profundo` dejó 0 (X se encontró a sí mismo 129/132). El sueño repasa
  todas las memorias, también las dormidas. `activos` se reporta solo como diagnóstico.
- **A2 — Categoría «General» en lugar de «Nota».** «Nota» no existe en el catálogo de categorías del motor.
  «General» es la categoría neutra. No cambia lo que se mide.
- **A3 — Se verificó que `ignore_peso_sinaptico` existe** en la firma de `buscar_por_frase` (L58; se usa en L2277 y
  L2792). No hace falta enmienda.
- **A4 — Dos vías de bucle que la copia limpia no tapaba (auditoría posterior a E1, 25-11; fijada antes de volver a
  medir).**
  - `largo_plazo.asociaciones` es una copia en CSV de los vecinos sinápticos (`sinapsis.py` L524–535). La búsqueda
    la convierte en `asoc_count` (`search.py` L2282) y suma `0.02·min(1, asoc_count/20)` (`scoring.py` L342).
  - Las dimensiones con `auto_generada = 1` nacen de comunidades del grafo de sinapsis (`auto_clustering.py`,
    llamado en `consolidation.py` L610). Se guardan en el eje `dominio`, el mismo del agente.
  - Prueba: inyectar una dimensión emergente falsa en 8 recuerdos cambió 6 de los 276 pares en es y 5 en en.
  - **Cambio:** la copia limpia también vacía `asociaciones` y quita de `largo_plazo_dimensiones` las dimensiones
    `auto_generada = 1`.
  - **Criterio nuevo C1.2c:** sobre una copia de D se inyecta una dimensión emergente falsa en un recuerdo de cada
    tema y un CSV `asociaciones` falso (20 vecinos al azar por recuerdo). R y U deben ser **idénticos 276/276**
    frente a D, en los 4 idiomas.
  - Los resultados van a `resultados/e1_a4.json`; `resultados/e1.json` queda como histórico. El veredicto de E1 no
    cambia (C1.1 ya había fallado); A4 solo cierra las vías.
- **Diagnósticos añadidos (informativos, sin umbral):** D construida dos veces (ruido de la propia construcción),
  invariancia con `activos` y número de dormidas en D y en DI. Sirven para leer C1.1 si falla.

## 1. Qué cambia frente a la v2

| v2 | v3 | Motivo |
|---|---|---|
| Señales S, R, K, V | **+ U, el autoexamen sináptico** | Propuesta de Gemini aprobada. Mide la **utilidad**: si el enlace rescata un recuerdo que la búsqueda directa no encuentra |
| `ignorar_sinapsis` como parámetro del motor | En el laboratorio se implementa **sin tocar el repo**: el repaso corre sobre una **copia con `sinapsis` y `sinapsis_latentes` vacías**, con `BIORAG_PPMI_WEIGHT=0`, `BIORAG_SDM_FALLBACK=0`, `BIORAG_DMN_SINTESIS_ACTIVA=0`, `BIORAG_NO_LOG=1`, `usar_inferencia=False`, `context_window=0` e **`ignore_peso_sinaptico=True`** | Ninguna lectura directa ve sinapsis. El PPMI no se calcula (L2048). El SDM no actúa. **Nuevo:** el peso del nodo también se ignora, porque sube +0,05 al evocar a un vecino por sinapsis (`search.py` L3021–3027): otra vía indirecta |
| Homeostasis «relativa a la mediana de esta memoria» (biología §4) | **Presupuesto fijo por nodo** | La mediana es una estadística global: cambia con D∪I y rompe la invariancia |
| Puente sin definir | **Rol `puente` que solo ordena** en el canal 2 | Pilar 12: nunca oculta ni filtra |
| Mundo de E1 de 8 × 6 | **E1 usa el corpus espejo 8 × 3 ya escrito**; el 8 × 6 queda para E2 | E1 mide la limpieza de las señales (invariancia, bucle, reproducibilidad), no su valor |

## 2. Las señales del sueño

Todas son **sin idioma**, **sin telemetría** y **sin el agente**.

**Pistas de cada recuerdo X en el sueño s**, generadas sin listas de palabras ni plantillas:
- **c1:** una ventana del contenido de X.
  - El texto se normaliza (NFKC, casefold; lo que no es letra ni número pasa a espacio) y se parte por
    **fronteras Unicode**.
  - Si hay escritura sin espacios (ideogramas chinos o japoneses, hiragana, katakana o hangul, detectados por el
    nombre Unicode del carácter), la unidad es el **bigrama** de caracteres; si no, la palabra entre espacios.
  - La ventana tiene 4 unidades consecutivas. En chino y japonés son 4 bigramas, es decir, 5 caracteres
    seguidos.
  - El punto de inicio se elige con `sha256(X | s)`.
- **c2:** los sustantivos clave de X, unidos con espacios. Es la misma pista en todos los sueños y se omite si
  no hay.

**La búsqueda del repaso:** `buscar_por_frase(pista, limite=6, …)` sobre la copia limpia (§1). De cada
resultado se toma el **top-5 sin contar a X**, y además se anota si X quedó en el top-5.

| Señal | Definición | Rango |
|---|---|---|
| **R (resonancia)** | número de sueños s ∈ {1, 2, 3} en que B sale con una pista de A, o A con una de B | 0–3 |
| **U (autoexamen sináptico)** | `U(A→B)` = fracción de las pistas de B en que **B no queda en el top-5** pero **A sí**. Es decir, la sinapsis A–B lo rescata: **con** el enlace, el agente llega a B desde A por el canal 2; **sin** él, no llega. `U(par) = max(U(A→B), U(B→A))` | 0–1 |
| **S (estructura)** | dimensiones (por ID) y sustantivos clave compartidos por igualdad exacta normalizada | entero |

**Control contra enlaces al azar.** Un recuerdo que sale en todos los top-5 (un «hub») «rescataría» cualquier
cosa. Por eso se reporta la distribución de U en pares **relacionados** frente a **no relacionados** (AUC) y la
fracción de rescates que se llevan los 3 recuerdos que más aparecen. U **no** se normaliza con frecuencias
globales: eso rompería la invariancia.

## 3. E1: limpieza de las señales (laboratorio)

**Mundo:**
- Las 24 memorias espejo × 4 idiomas, más las 8 irrelevantes (`mundos_espejo.py`).
- Estructura generada con semilla 18 (`e1_mundo.py`), idéntica en los 4 idiomas:
  - dimensión de tema (eje `dominio`, un valor por tema), con p = 0,707;
  - más 1 dimensión al azar de un pozo de 5 (eje `cualidad`);
  - el sustantivo clave del tema (8 × 4, escritos a mano), con p = 0,548;
  - más 1 genérico de un pozo de 5, con p = 0,5;
  - categoría única («General», enmienda A2) y sin sinónimos.
- Las 8 de I usan **otros** valores de dimensión y **otro** pozo de genéricos: son irrelevantes también por
  estructura.

**Bases** (motor real, camino de `aprender`, en `/tmp`):
- **D** = D → sueño → sueño.
- **DI** = D → sueño → I → sueño.
- Así D y DI difieren **solo** en I, con el mismo número de sueños.

| # | Criterio | Umbral |
|---|---|---|
| C1.1 | Invariancia: R y U de los 276 pares de D, comparando D frente a DI, por idioma | ≥ 98 % idénticos en cada idioma |
| C1.2 | Bucle (directo): multiplicar por 3 el peso de 20 sinapsis al azar | R y U idénticos 276/276 |
| C1.2b | Bucle (indirecto): agregar 20 sinapsis falsas (peso 1,0, entre temas distintos) **y dormir**, frente a dormir sin agregarlas | ≥ 98 % idénticos |
| C1.3 | Reproducibilidad: dos repasos de la misma base | idénticos |
| C1.4 | Regresión: el repaso no toca la base original (sha256) y 5 búsquedas normales dan lo mismo antes y después | idéntico |
| C1.5 | La copia limpia sigue con 0 sinapsis al terminar el repaso | 0 |
| C1.6 | Informativo, sin umbral: AUC de R, U y S (relacionados frente a no relacionados), fracción de pares relacionados con U > 0 y concentración en hubs, por idioma | — |

**Lectura fijada antes:**
- Si C1.1–C1.5 pasan, R y U son **señales limpias**, aptas para E2.
- Si C1.1 falla, la causa está en la **invariancia del canal 1** (por ejemplo, el BM25 depende del corpus), no
  en la señal. Se reporta, no se ajusta, y E2 hereda esa tolerancia como límite conocido.

## 4. E2 (fijado ahora; se corre si E1 pasa)

Sigue los criterios C2.1–C2.9 de la v2 (puerta del MLP incluida), con estos agregados:

- **Piso «≥ 2 de 3»:** (a) S ≥ 1 · (b) R ≥ 2 · (c) **U > 0** o competencia ganada (top-5 del nodo por S + R + U).
- **Homeostasis:**
  - presupuesto fijo de **3,0** por nodo (suma de pesos automáticos consolidados);
  - si se pasa, se escalan todos por el mismo factor: cambia el total, no el orden;
  - los `manual` no se escalan ni cuentan.
- **Rol `puente`:** par consolidado con S = 0, entre temas distintos y con U > 0 o R ≥ 2.
  - En el canal 2 **solo se reordena**: el puente sube si la consulta contiene la unidad que comparten A y B
    (la misma segmentación Unicode). Nunca se oculta.
  - Se añade **C2.10:** el conjunto del canal 2 es idéntico con y sin este orden.
- **El MLP** recibe S, R, U, K, V y el grado (en logaritmo). Mismas reglas que la v2.

## 5. Bloqueadas

- **E3** (examen real en copia de solo lectura) hasta que pasen E1 y E2.
- **E4** (motor) hasta el OK explícito de Dennys.
- Los «ojos Unicode» del nacimiento, en su propio ciclo.
