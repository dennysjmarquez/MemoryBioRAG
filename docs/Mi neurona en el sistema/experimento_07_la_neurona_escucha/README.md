# Experimento 07 — La neurona escucha

> Motor + agente + neurona son un solo cerebro. La ambigüedad la resuelve el agente
> (paráfrasis, sustantivos_clave, dimensiones, ráfaga); el motor tiene que aprovechar
> al máximo lo que el agente le manda. Por eso este experimento mide y entrena la
> neurona **por el camino real del agente** (`recordar` del MCP), no solo por el de la QA.

## 0. En una línea por hallazgo

| # | Qué | Evidencia | Estado |
|---|-----|-----------|--------|
| 1 | La QA mide el motor sin el agente. Medido por `recordar`, la fórmula a mano tenía **R@5 93.37** (QA: 100). | `resultados/camino_mcp/` | medido |
| 2 | Culpables: **auto-paráfrasis PMI** (−10 R@5 no-literal, 39 entran / 0 salen) y **auto-dimensiones** (−4.4; además apagan el PRF del motor). No deterministas (`list(set)[:10]`). | `resultados/camino_mcp/RESUMEN.md` | **arreglado** (commit `20bbf36`) |
| 3 | Con el arreglo, el camino del agente: **R@1 92.34 · R@5 99.09 · MRR .951** (supera a la QA en R@1/MRR). Corpus no visto: R@1 31.48 → **45.68**. | idem | **arreglado** |
| 4 | Los `print()` del motor corrompían el canal JSON-RPC stdio (120 `vincular` → **77 líneas no-JSON**). | `resultados/canal_stdio.txt` | **arreglado** (commit `bc69d0b`) |
| 5 | Neurona v5: estudia **exactamente** lo que sirve (desfase **0/289** en consultas reales; v4: 46.7 %). | `resultados/v5/desfase.json` | **hecho** |
| 6 | Hueco en la capa anti-memorización: un retador delatado por la guardia ascendía igual con margen 5. | `tests/test_neurona.py` | **arreglado** |
| 7 | Caducidad del MCP: el JOIN usa `categorias c`/`c.nombre` (la tabla es `categories(name)`); la excepción se traga y el **corte duro de 365 días está apagado sin saberlo**. | §5 | **no tocado**: decisión de diseño |

## 1. El camino del agente (antes de tocar la neurona)

`evaluar_camino_mcp.py` llama a la herramienta MCP `recordar` caso por caso con el mismo
arnés que `scripts/evaluar_qa.py` (etiquetas resueltas, `ambiguo`/`negativo` fuera, estado
restaurado entre casos). `sustantivos_clave` = las 3 primeras palabras con significado de la
consulta (un "agente mínimo", tosco a propósito: corta palabras con tilde).

**Validación del evaluador:** quitando las 5 piezas que agrega el MCP reproduce la QA
oficial al decimal (R@1 91.89 · R@5 100 · MRR .9502).

Atribución por ablación y arreglo: ver `resultados/camino_mcp/RESUMEN.md`.

## 2. Neurona v5: qué cambió y por qué

1. **Una sola vista para aprender y para servir.** `neurona.vista()` arma lo que ve la red
   desde la página **tal como se sirve** (después de convergencia, hub, prefijo, despertar).
   El autoexamen guarda esa vista; `reordenar` corrige esa misma vista. Desfase 0 por
   construcción, verificado con prueba (`test_el_examen_ve_exactamente_lo_que_se_sirve`) y
   medido sobre 289 consultas reales (`medir_desfase_v5.py`).
2. **Escucha al agente.** 12 señales nuevas además de las 17 agujas de la fórmula: bono de
   convergencia, evidencia por campo (concepto, sinónimos, sustantivos_clave, contenido),
   peso sináptico, "¿el score incluye peso?", "¿vino con sustantivos del agente?", origen
   (léxico aprendido, hub, no literal) y "sin rasgos" (nodos del hub: ceros + bandera, sin
   inventar valores).
3. **Practica los dos caminos**, alternando: *agente* (pool 30, convergencia 10, peso,
   sustantivos sacados de la consulta) y *crudo* (como la QA). El piso es por categoría **y**
   por camino.
4. **La vista cubre lo que verá quien busca**: 10 por el MCP (`convergencia_limite`), 5 si no se
   sabe; tope fijo `topk_max` = 10 (costo constante). Así puede rescatar respuestas del puesto
   6-7 al top-5.
5. **Capa nueva: el R@5 tampoco puede bajar.** Con vistas de 10 la red podría sacar a alguien
   del top-5. El piso ahora cubre R@1, MRR@5 y R@5 por categoría, y ningún caso de guardia que
   la fórmula tenía en el top-5 puede salir de él (`test_con_vista_de_10_el_r5_no_puede_bajar`:
   sin esta capa se aceptaba un margen que sacaba a 43 de 60).
6. **Anti-memorización sin agujero**: si la guardia delata memorización, ese retador no
   asciende aunque un margen grande lo deje "sin dañar" (antes ascendía).

Nota honesta: la pérdida softmax ya se comporta como un error de predicción (lo que la
dopamina señala); no hay "dopamina" nueva aquí, solo la misma matemática bien alimentada.

## 3. Resultados (copias del snapshot y DB desconocida; `PYTHONHASHSEED=1`)

### Uso simulado
| | ciclos | ascensos | retiros | guardia mano → campeón | costo por consolidación |
|---|---|---|---|---|---|
| snapshot | 500 | 7 | 0 | 74.5 % → **83.2 %** (v4: 72.5 → 79.4) | p50 1.6 s · p95 3.5 s |
| python-docs-es | 300 | 1 | 0 | 85.8 % → 88.7 % | — |

### QA oficial (`scripts/evaluar_qa.py`, motor directo) — piso del usuario
| categoría | piso (base) | v4 | **v5** |
|---|---|---|---|
| cruce_idioma | 62.50 | 75.00 | **87.50** |
| dormido | 100 | 100 | 100 |
| literal | 99.59 | 99.59 | 99.59 |
| por_tema | 63.08 | 80.00 | 73.85 |
| pregunta_natural | 93.85 | 95.38 | **96.92** |
| sinonimo | 56.36 | 60.00 | 60.00 |
| typo | 89.23 | 96.92 | 96.92 |
| variante_gramatical | 89.23 | 93.85 | **95.38** |
| **GLOBAL R@1 / MRR** | 91.89 / .950 | 94.51 / .966 | **94.40 / .966** |

R@5 100 en todas, FP 0/40, GATE OK. Ninguna categoría bajo el piso.

### Camino del agente (`recordar`), con el arreglo del MCP
| QA (875) | R@1 | R@5 | MRR | #1 vs mano | top-5 vs mano |
|---|---|---|---|---|---|
| fórmula a mano | 92.34 | 99.09 | .9505 | — | — |
| v4 | 94.51 | 99.09 | .9630 | +19 / −0 | +0 / −0 |
| **v5** | **94.97** | **99.31** | **.9665** | **+24 / −1** | **+3 / −1** |

| python-docs-es, 162 preguntas humanas (nunca vistas) | R@1 | R@5 | MRR | #1 vs mano |
|---|---|---|---|---|
| fórmula a mano | 45.68 | 59.88 | .5175 | — |
| v4 | 45.06 | 59.88 | .5113 | +1 / −2 |
| **v5** | 45.06 | **60.49** | .5151 | +0 / −1 |

Camino crudo en python-docs-es (examen humano, 164): mano 42.07 / .481 → **v5 43.29 / .486**
(3 ganan, 1 pierde, 0 salen del top-5).

### Auditoría del MCP con y sin neurona (120 consultas)
0 ruido · top-5 reordenado en 67 · puestos 6-10 en 52 · **0 violaciones** (mismos recuerdos,
mismos números por posición, mismas decisiones globales).

## 4. Lo que NO logra (para el auditor)

- **"0 pérdidas contra la fórmula" no se cumple en consultas nunca vistas.** Snapshot por MCP:
  1 pérdida en el #1 ("fin-aprendizaje-creerse-completando", casi literal: la regla de
  identidad solo protege nombres exactos) y 1 que sale del top-5 ("metodologia", una palabra
  ambigua, del 3 al 6). python-docs-es por MCP: 1 pérdida, 0 ganancias en el #1. Las garantías
  duras (0 pérdidas de guardia, ≤5 % en total, piso por categoría) valen sobre el examen de la
  neurona; sobre consultas nuevas ningún aprendiz puede garantizar cero. Una regla de "casi su
  nombre" arreglaría el primer caso, pero salió de mirar el examen de prueba: queda como
  candidata a medir en un conjunto nuevo, no se aplicó.
- En el corpus no visto la neurona por el camino del agente es **neutra** (no mejora el #1).
  La ganancia grande en ese corpus vino del arreglo del MCP (+14.2 R@1), no de la neurona.
- La neurona no ve las paráfrasis/dimensiones que inventaba el MCP (ahora apagadas) ni la
  ráfaga (sucede después de ella).

## 5. Caducidad del MCP (hallazgo #7, decidido)

`core/mcp_server/search.py` (bloque "CADUCIDAD TEMPORAL") hace `JOIN categorias c ... c.nombre`;
la tabla real es `categories(name)`. La consulta falla siempre, la excepción se traga y:
- las marcas de "viejo" (>90 días) nunca se calculan (hoy serían 436 nodos no protegidos);
- el corte duro de 365 días nunca excluye nada. Hoy no excluiría ninguno (el nodo más viejo es
  de 2026-06-20), pero **arreglar el JOIN activaría desde junio de 2027 la exclusión de
  lecciones y arquitectura del MCP**. Eso es decisión de diseño (¿debe la memoria esconder
  lecciones viejas?), no un arreglo mecánico: queda para Dennys.

**Decisión de Dennys: no.** BioRAG es memoria de largo plazo y no esconde recuerdos por fecha
salvo que se pida. `BIORAG_STALE_HARD_CUTOFF` pasa a `0` por defecto (`core/mcp_server/_shared.py`,
`.env.example`, README), con `tests/test_mcp_sin_caducidad.py` fijándolo. Hoy el comportamiento no
cambia (el corte nunca disparaba); lo que cambia es que ya no puede encenderse solo si alguien
corrige el JOIN. El JOIN y las marcas "stale" de 90 días siguen sin tocar (otra decisión).

## 6. Reproducir

```bash
# camino del agente (fórmula a mano), sobre una COPIA
BIORAG_PATH=/copia.db BIORAG_NEURONA=0 python evaluar_camino_mcp.py --salida res.json [--quitar parafrasis,dims]
# neurona v5 completa (uso simulado, QA, python-docs-es, camino MCP)
bash v5.sh
# desfase y auditoría
BIORAG_NEURONA=1 python medir_desfase_v5.py --db /copia_con_campeon.db --n 150
BIORAG_PATH=/copia_con_campeon.db python mcp_con_y_sin_neurona_v5.py --n 120
# canal stdio
N_VINC=120 python canal_stdio_cliente.py "$(which python)" tasajera
```

## 7. Archivos
- `evaluar_camino_mcp.py` — QA por `recordar` (+ ablaciones `--quitar`, `--casos`, `--sin`).
- `medir_desfase_v5.py` — desfase entre lo estudiado y lo servido.
- `mcp_con_y_sin_neurona_v5.py` — invariantes del MCP con la vista de 10.
- `canal_stdio_cliente.py` — cliente stdio que detecta ruido en el canal JSON-RPC.
- `v5.sh` — pipeline completo.
- `resultados/camino_mcp/` — ablaciones, arreglo, v4 por MCP (txt verbatim + json por caso).
- `resultados/v5/` — curvas de uso, QA oficial, examen humano, camino MCP, desfase, invariantes.
- `resultados/canal_stdio.txt`, `resultados/pytest.txt`.
