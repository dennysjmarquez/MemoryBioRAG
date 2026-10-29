# Control: ¿los cambios de la PR #12 recortaron lo que llega? (2026-10-29)

Pregunta de Dennys: "¿No han dañado nada?" La QA oficial solo mide el recuerdo **exacto**. Aquí se compara la **lista completa** del top 5, es decir, también lo parecido que llega.

- **Versiones:** `master` `f8c2b16` (lo que está en uso; nada se mergeó) contra la PR #12 `47f7f60` (motor `c695310`: B1–B4a, reparación del hub, Cambio 1; el Cambio 2 todavía no está aplicado).
- **Base:** copia del snapshot (sha `104dd290…`), una copia por versión. 921 consultas oficiales, `profundidad="activos"`, `limite=5`, **peso sináptico activo** (como en producción), `BIORAG_NEURONA=0`, `PYTHONHASHSEED=0`.
- **Script:** `scripts/comparar_listas_completas_top5.py`.

| Medida | master | PR #12 |
|---|---:|---:|
| Listas idénticas, mismo orden | — | **921/921** |
| Resultados entregados en total | 3877 | 3877 |
| Listas vacías (son los 40 controles absurdos) | 40 | 40 |
| Errores | 0 | 0 |

Los dos archivos de salida son **byte a byte idénticos** (`cmp`).

**Límites:**
1. Es el snapshot, no la viva.
2. La reparación del hub (umbral de expansión de 0,40 a 0,55, porque disparaba con una sola palabra común: 154 disparos y 8 aciertos) **sí reduce asociaciones en la viva**. Es la primera pieza que debe revisar la QA de intuición (P11).
3. Es una consulta por pregunta, no el ciclo completo agente + cerebro.
