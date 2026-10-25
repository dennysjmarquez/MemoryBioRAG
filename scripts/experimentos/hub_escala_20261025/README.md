# Concept Hub a escala (v35.2) — 2026-10-25

## Qué fallaba
El diagnóstico de la base viva (`scripts/diagnostico_fallos.py`, 13 fallos) mostró un
recuerdo traído por el **concept hub** entre los 3 primeros en 10 de los 13 fallos, y en el
primer lugar en 7, a veces con **0 palabras** de la pregunta.

**Por qué.** El hub nació en v29 como un puñado de conceptos curados (10 hubs; 17 en la base
viva de v30.1) para cruzar el *abismo léxico*: preguntas que no comparten palabras con el
recuerdo. Después `aprender` empezó a crear **un hub con 5 puentes por cada recuerdo**
(`core/mcp_server/write.py`). La base viva tiene hoy **1086 hubs / 5025 puentes**, y el
snapshot de la QA solo **6 / 30**. La fórmula seguía siendo la de 17 hubs, y la QA nunca la
probaba a escala.

## Los 5 defectos encontrados (verificados)
1. **Toda palabra valía lo mismo.** "regla", "cv" o "agente" aparecen en decenas de puentes y
   daban confianza 1.0 igual que una palabra única.
2. **Empates resueltos por orden alfabético.** Con "agente" empataban 81 hubs en 1.0 y ganaba
   `aforismo_criterio_agente` porque empieza con "a". El recuerdo ganador se forzaba al TOP1.
3. **El freno contra la ambigüedad no funcionaba.** Solo actuaba por debajo del umbral,
   donde el hub ya no devolvía nada.
4. **Palabras vacías contaban como coincidencia.** `test_concept_hub_5_angulos::test_08`
   pasaba solo por la palabra "de". Sin el "de", el hub viejo tampoco emparejaba.
5. **Lento y creciendo en línea recta.** Releía y procesaba todos los puentes en cada
   búsqueda: ~0.5 s por consulta con 866 hubs (4 ms con 6).

## La solución (`core/concept_hub.py`, `_expandir_a_escala`)
Cada pieza se basa en cómo el cerebro discrimina recuerdos:

| Principio | Qué hace |
|---|---|
| Efecto abanico (ACT-R, Anderson 1974) / sobrecarga de pista (Watkins & Watkins 1975) | Cada palabra pesa ln(1 + (H − abanico + 0.5)/(abanico + 0.5)), donde el abanico es el número de hubs que la usan. Es el IDF, siempre positivo, también con 1 hub. Las palabras vacías no cuentan. |
| Priming por repetición > priming morfológico | La palabra idéntica cuenta entera; la misma familia (solo la raíz) cuenta la mitad. |
| Completar un patrón exige parecido | La cobertura del puente se reemplaza por el coseno (Ochiai). Un puente diminuto contenido en la pregunta vale solo lo que explica de ella. |
| Elección de Luce / recuperación de ACT-R | confianza = parecido × ventaja, con ventaja = e^(s/T) / Σ e^(s_k/T) entre los **recuerdos** activados (T = 0.10). Dos hubs del mismo recuerdo son aliados. Si 10 empatan, ninguno se impone. |
| Índice invertido en memoria | Se reconstruye solo si cambian las tablas del hub (huella de ~1–7 ms). Cada consulta mira solo los hubs que comparten alguna palabra. |

Todo lo demás queda igual: multiplicador por ángulo, bonus de consenso, umbral 0.40 y lo que el
motor hace después con el hub (expansión, señal #14, paso por el QCR, promoción competitiva).
**Ablación:** `BIORAG_HUB_ESCALA=0` vuelve exactamente al cálculo anterior.

## Cómo se midió
- Copias del snapshot con **un hub por recuerdo**, como hace `aprender` (`construir_copias.py`):
  - **H-todos**: 866 hubs / 3980 puentes. Un usuario nuevo que empieza de cero con v35.
  - **H-mitad**: 436 hubs, solo en la mitad más nueva. Imita la historia de la base viva:
    los recuerdos viejos nacieron sin hub.
  - *Aproximación honesta:* los puentes salen de los datos del propio recuerdo (sinónimos,
    frases del contenido, sustantivos clave), no de un agente escribiendo paráfrasis.
- QA oficial `scripts/evaluar_qa.py` (921 casos), `BIORAG_NEURONA=0`, `PYTHONHASHSEED=1`,
  siempre sobre copias. El sha256 del snapshot (`104dd2902aaf…`) fue el mismo antes y después.
- Hub solo, sobre las 921 preguntas (`medir_hub_solo.py`), y los 5 casos del abismo léxico
  (`abismo_5_casos.py`).

## Resultado (detalle por categoría en `tabla_final.txt`; métricas y fallos en `resultados/`)

| Base | R@1 antes → después | R@5 antes → después | MRR | Errores |
|---|---|---|---|---|
| **S0 snapshot (piso oficial)** | 92.57 → **93.14** | 100 → **100** | 0.954 → 0.957 | 0 → 0 |
| H-mitad (436 hubs) | 76.34 → **93.03** | 98.97 → **100** | 0.866 → 0.957 | 9 → **0** |
| H-todos (866 hubs) | 80.91 → **93.83** | 99.20 → **99.89** | 0.892 → 0.961 | 7 → **1** |

FP 0/40 en todas. En el snapshot ninguna categoría baja (suben pregunta_natural, typo y
variante). Los 5 casos del abismo léxico: 5/5 en las tres bases, igual que antes.

**Hub solo (921 preguntas):**

| | Se equivoca con confianza ≥ 0.8 | Tiempo por consulta |
|---|---|---|
| H-todos viejo → nuevo | 255 → **3** | 593 ms → **~8 ms** |
| H-mitad viejo → nuevo | 216 → **11** | 284 ms → **~4 ms** |

La QA completa bajó de ~1820 s a ~1000–1100 s por corrida.

## Lo que queda, sin maquillar
- **Sinónimo R@1 en H-todos: 65.45 → 58.18** (su R@5 sube de 98.18 a 100). Verificado caso por
  caso: los aciertos "perdidos" eran empates de 3 a 81 hubs en 1.0 que el hub viejo resolvía por
  orden alfabético. En H-mitad, la base parecida a la viva, sinónimo **sube** de 41.82 a 56.36.
  Una sola palabra compartida por decenas de recuerdos no identifica a ninguno: eso es el Reto 1.
- **0501** "blueprint dimensiones ortogonales" (H-todos) sigue fallando, como con el hub viejo.
  El hub elige otro recuerdo, ahora con confianza 0.41 (antes 1.0), y el caso queda al límite.
- Falta medir en la base viva. Eso lo corre Dennys (ver abajo).

## Reproducir
```
python3 construir_copias.py ../../../snapshots/qa_escape_qcr_20260811.db /tmp/v
python3 abismo_5_casos.py /tmp/v/H_todos.db
python3 medir_hub_solo.py /tmp/v/H_todos.db
cd ../../.. && BIORAG_PATH=/tmp/v/H_todos.db BIORAG_NEURONA=0 PYTHONHASHSEED=1 python3 scripts/evaluar_qa.py
```
Pruebas: `tests/test_hub_escala.py` (11). Suite completa: 500 passed.
