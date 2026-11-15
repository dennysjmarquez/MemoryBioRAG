# Plan de publicación v37.0 (decisión de Dennys, 2026-10-27)

> Documento de trabajo del auditor. Se ejecuta **cuando el operador cierre la limpieza del motor (E4)**. El auditor avisa a Dennys cuando llegue ese punto.

> **Reasignación tras sincronizar con la rama del auditor:** v36.0 ya quedó ocupado por el aislamiento del córtex en `~/.biorag/`, el instalador zero-touch, el ciclo de vida del daemon y cambios de integración de agentes. El plan de motor que antes se llamaba v36.0 se desplaza a **v37.0**; la fase de neuronas que ese plan asignaba a v37 se desplaza a **v38.0**. En esa rama no existía un archivo independiente `plan_publicacion_v37.md` para renombrar: este documento es la versión reubicada del plan v36, y no inventa un segundo plan de alcance no acordado. La lista de posibles novedades que se conserva abajo es un inventario para reconciliar con lo que ya entró a v36, no una afirmación de que todo eso siga pendiente o deba duplicarse en v37.

## Decisión
- **v36.0 ya está documentada en la rama sincronizada** con los cambios de córtex externo, instalador zero-touch y parada prudente del daemon; no se reutiliza su número para el trabajo pendiente del motor.
- **No se etiquetan** v35.1, v35.2 ni v35.3. Nunca se publicaron: en esos commits `VERSION` y el README siguen diciendo v35.0.
- Todo se publica junto como **v37.0 (motor robusto)**, con **una sola etiqueta**.
- **Quién lo escribe:** el **auditor** redacta la documentación de v37.0 (README, `CHANGELOG.md`, `VERSION`) en su rama. Dennys revisa y fusiona.
- **Cómo:** los cambios que entraron sin documentar van **dentro** de la sección v37.0, como parte de ella, **sin numerarlos como versiones** sueltas.

## Orden aceptado por Dennys (2026-10-27)
1. El operador cierra el motor: E2c → E3 → E4. **No toca README, `VERSION` ni `CHANGELOG.md`.**
   - **Después de E4, modularización fase 2 (decisión de Dennys, 2026-10-28):** el operador separa en subpaquetes (`core/lexico/`, `core/memory/busqueda/`, `ranking/`, `neuronas/`, `sueno/`), un paquete por cambio, dejando la ruta vieja como puente y con las 4 QA **idénticas**. La fase 1 (un README con el mapa de cada carpeta de `core/` y `scripts/mapa_dependencias_core.py`) ya está hecha en la rama del auditor (`b7df96a`). Reglas: Constitución, Pilares 9–11.
2. El auditor redacta v37.0 en su rama con las métricas finales.
3. Dennys fusiona la rama del auditor con la del operador.
4. El auditor audita la rama combinada (pytest, QA de control y documentos).
5. Dennys pasa a master (PR #12) y pone la etiqueta v37.0.
6. **Después** empiezan las neuronas (asociativa + capa definitiva, visión §2l–§2o), que serán la v38. Así la v37 sirve de base fija de comparación y de punto de regreso.

## Qué entra en "Novedades de la versión v37.0"
1. **Cambios del motor que entraron a master después de v35.0 sin documentar** (fusión `f8c2b16`), descritos dentro de v37.0, sin número de versión:

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
   - E2c y siguientes: las reparaciones del motor que se aprueben. E2c (quitar el gate del temático) y E2e (peso temático a 0) se **rechazaron y revirtieron** con pruebas; E2d documentó por qué el temático satura. Se cuentan como investigación, no como cambios;
   - E3: sigue abierto. La investigación reciente no autorizó cambiar el filtro; no se declara cerrada ni se atribuyen al motor efectos aún no demostrados;
   - E4: pendiente; no iniciado hasta cerrar E3. La rama sincronizada externaliza la ruta de la base en la aplicación, pero eso no equivale a cerrar E4 ni a verificar/migrar la base real del operador;
   - fecha de modificación (C1), si entra.
3. **Métricas antes y después** en el snapshot y en una copia de la viva: R@5, R@1, MRR y FP; QA clásica y honesta; con y sin ruido. Y el recuento de pruebas.
4. **Compatibilidad:** qué cambia para el agente y el MCP (si nada, se dice).
5. **Compatibilidad Python.** La decisión aceptada es Python ≥3.11. En la rama sincronizada `pyproject.toml` ya declara `requires-python = ">=3.11"` y `install.py` exige 3.11+; confirmar CI y documentar cualquier ajuste remanente al cerrar v37. No es un cambio de código nuevo para este plan.

6. **Versión del paquete.** Estado al sincronizar: `pyproject.toml` declara `36.0.0`, pero el archivo `VERSION` todavía dice `v35.0`; es una inconsistencia que queda pendiente de reconciliar con el release v36.0. Al publicar v37.0, alinear `pyproject.toml` en `37.0.0`, `VERSION`, README y `CHANGELOG.md` en el mismo trabajo.

7. **Estructura del código:** la modularización (fase 1 y fase 2) se describe en las Novedades: qué se movió, por qué, y que la QA quedó idéntica.

## Reglas del README
- Se **añade**; nunca se recorta ni se divide.
- Se actualiza la línea "Versión Oficial", la tabla de métricas vigentes y el recuento de pruebas.
- `CHANGELOG.md` recibe la misma entrada.

## Etiqueta
- Después de que Dennys fusione a master, **una sola etiqueta** en el commit de la fusión: `git tag -a v37.0 <commit> -m "v37.0: motor robusto"` y `git push origin v37.0`. El auditor da el commit exacto.

## Regla desde ahora
Ninguna versión se nombra en un commit sin cambiar `VERSION`, el README y `CHANGELOG.md` en el mismo trabajo.
