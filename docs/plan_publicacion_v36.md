# Plan de publicación v36.0 (decisión de Dennys, 2026-10-27)

> Documento de trabajo del auditor. Se ejecuta **cuando el operador cierre la limpieza del motor (E4)**. El auditor avisa a Dennys cuando llegue ese punto.

## Decisión
- **No se etiquetan** v35.1, v35.2 ni v35.3. Nunca se publicaron: en esos commits `VERSION` y el README siguen diciendo v35.0.
- Todo se publica junto como **v36.0 (motor robusto)**, con **una sola etiqueta**.
- **Quién lo escribe:** el **auditor** redacta la documentación de v36.0 (README, `CHANGELOG.md`, `VERSION`) en su rama. Dennys revisa y fusiona.
- **Cómo:** los cambios que entraron sin documentar van **dentro** de la sección v36.0, como parte de ella, **sin numerarlos como versiones** sueltas.

## Orden aceptado por Dennys (2026-10-27)
1. El operador cierra el motor: E2c → E3 → E4. **No toca README, `VERSION` ni `CHANGELOG.md`.**
2. El auditor redacta v36.0 en su rama con las métricas finales.
3. Dennys fusiona la rama del auditor con la del operador.
4. El auditor audita la rama combinada (pytest, QA de control y documentos).
5. Dennys pasa a master (PR #12) y pone la etiqueta v36.0.
6. **Después** empiezan las neuronas (asociativa + capa definitiva, visión §2l–§2o), que serán la v37. Así la v36 sirve de base fija de comparación y de punto de regreso.

## Qué entra en "Novedades de la versión v36.0"
1. **Cambios del motor que entraron a master después de v35.0 sin documentar** (fusión `f8c2b16`), descritos dentro de v36.0, sin número de versión:

   | Cambio | Commit |
   |---|---|
   | Escala: el recall base no depende del tamaño de la memoria (4 arreglos, `BIORAG_ESCALA=1`) | `f317a9a` |
   | Concept hub a escala: funciona igual con 6 o con miles de hubs | `3cce403` |
   | Concept hub: las palabras de función cuentan con tope de 1 bit | `ff571fb` |
   | Concept hub: el puente "ingenuo" deja de castigar (×0,85 → ×1,0) | `d776a49` |
   | QA: muestra la neurona de ranking; `--con-neurona` pregunta antes de entrenar | `daffa6f`, `e70daaf` |
   | Herramientas de diagnóstico de solo lectura (`diagnostico_fallos.py`, `diagnostico_hub.py`) | `eab3f68`, `6a2662f`, `c2a8681`, `0cc1fed` |

2. **El trabajo del operador** (rama `arena/33a8df67`, PR #12 y los que sigan):
   - E1: QA honesta (obsoletas y ambiguas, aparte);
   - E2 y E2b: diagnóstico del 0848, tolerancia al ruido, temático saturado, la QA ya no deja archivos junto al snapshot;
   - E2c y siguientes: las reparaciones del motor que se aprueben;
   - E3: léxico independiente del idioma (aprobada por Dennys el 2026-10-27; sustituye al diccionario solo en español);
   - E4: que el motor no dependa de la base;
   - fecha de modificación (C1), si entra.
3. **Métricas antes y después** en el snapshot y en una copia de la viva: R@5, R@1, MRR y FP; QA clásica y honesta; con y sin ruido. Y el recuento de pruebas.
4. **Compatibilidad:** qué cambia para el agente y el MCP (si nada, se dice).

## Reglas del README
- Se **añade**; nunca se recorta ni se divide.
- Se actualiza la línea "Versión Oficial", la tabla de métricas vigentes y el recuento de pruebas.
- `CHANGELOG.md` recibe la misma entrada.

## Etiqueta
- Después de que Dennys fusione a master, **una sola etiqueta** en el commit de la fusión: `git tag -a v36.0 <commit> -m "v36.0: motor robusto"` y `git push origin v36.0`. El auditor da el commit exacto.

## Regla desde ahora
Ninguna versión se nombra en un commit sin cambiar `VERSION`, el README y `CHANGELOG.md` en el mismo trabajo.
