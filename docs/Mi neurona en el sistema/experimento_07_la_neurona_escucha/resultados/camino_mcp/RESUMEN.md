# QA por el camino real del agente (`recordar` del MCP), fórmula a mano

Evaluador: `../../evaluar_camino_mcp.py` (mismo arnés que `scripts/evaluar_qa.py`:
etiquetas resueltas, `ambiguo`/`negativo` fuera, estado restaurado caso a caso).
Copia del snapshot, `PYTHONHASHSEED=1`, `BIORAG_NEURONA=0`. Salidas verbatim en `*.txt`,
puesto por caso en `*.json`.

## 1. Validación del evaluador
Quitando las 5 piezas que agrega el MCP (`ab_sin_todo.txt`) reproduce la QA oficial
al decimal: R@1 91.89 · R@5 100.00 · MRR 0.9502.

## 2. Atribución (388 casos no literales; `ab_sin_<pieza>.txt`)

| pieza del camino MCP        | R@1   | R@5   | entran / salen del top-5 |
|-----------------------------|-------|-------|--------------------------|
| todo (hoy)                  | 67.27 | 85.05 | —                        |
| sin peso sináptico          | 67.01 | 85.05 | 5 / 5                    |
| sin sustantivos_clave       | 66.49 | 84.54 | 1 / 3                    |
| **sin auto-paráfrasis PMI** | 79.64 | 95.10 | **39 / 0**               |
| **sin auto-dimensiones**    | 70.36 | 89.43 | **23 / 6**               |
| sin pool 30 + convergencia 10 | 65.98 | 81.18 | 2 / 17                 |

## 3. Arreglo (auto-expansión apagada por defecto), código real (`real_*.txt`)

| QA (875)                      | R@1   | R@5    | MRR    |
|-------------------------------|-------|--------|--------|
| MCP antes (`ab_mano`)         | 85.14 | 93.37  | 0.8837 |
| **MCP después (`real_mano`)** | 92.34 | 99.09  | 0.9505 |
| QA oficial, motor solo        | 91.89 | 100.00 | 0.9502 |

Corpus no visto (python-docs-es, 162 preguntas humanas, `real_py_mano` vs `ab_py_mano`):
R@1 31.48 → **45.68** · R@5 53.09 → **59.88** · MRR 0.3999 → **0.5175**
(top-1 +30 / −7; top-5 +15 / −4).

La QA oficial no cambia (llama al motor directo, no al MCP).
Quedan 8 casos de frontera (6 por_tema, 2 sinónimo) que la QA tiene en el puesto 4-5
y el MCP en el 6-7: terreno de la neurona v5 (vista de 10 = lo que ve el agente).
