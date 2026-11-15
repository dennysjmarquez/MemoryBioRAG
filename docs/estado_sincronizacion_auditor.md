# Estado para continuar tras sincronizar con la rama del auditor

## Sincronización de ramas

La rama de trabajo sigue siendo `arena/9a54babb-memorybiorag`; no se cambió de rama. Se sincronizó localmente con `arena/6459e2d0-memorybiorag` (punta observada `27f84163c94d575d376eca10f404e4c1d3c98afa`) y se integró también la punta previa de esta rama (`a551975874f9ae9a574f181b42d4e884f18986bc`) para no perder el informe/script SQLite ya publicado. El merge de sincronización es `5f3f249fe71d49ab15cec99c9b007d1a69521ed0`; los cambios locales de documentación/instrumentación E3 se conservaron. No se hizo push en esta etapa.

## Qué cambió en la rama sincronizada

- **Base viva externa:** `core/paths.py` prioriza `BIORAG_PATH`, luego la ruta canónica `~/.biorag/memory_biorag.db` si existe, usa la ruta legacy del repo como compatibilidad y, por último, el default externo. `install.py` contiene el flujo zero-touch de checkpoint, respaldo y migración de `.db`, `-wal` y `-shm`. El path de base que estaba versionado bajo `MemoryBioRAG_Data/` fue retirado del árbol Git.
- **Importante sobre el estado real:** el merge sincroniza código y documentación; **no confirma** si una base ya fue trasladada, no inspecciona `~/.biorag/`, no ejecuta la migración y no certifica la base del operador. No se abrió ni modificó ninguna base.
- **v36.0 publicada/documentada en esa rama:** aislamiento del córtex, instalador zero-touch, parada prudente del daemon, detección del plugin OpenCode y configuración MCP por stdio. Los commits finales incluyen uniformar stdio en los agentes y eliminar la ruta SSE de instalación.
- **Discrepancia de publicación pendiente:** `README.md` declara v36.0 y `pyproject.toml` tiene `36.0.0`, pero `VERSION` aún dice `v35.0`. No se alteró aquí; debe reconciliarse antes de una etiqueta/release.
- El README del auditor reporta 838/838 tests para v36.0. No repetí la suite después de sincronizar: podría resolver la DB externa por defecto. Ese número queda atribuido a la evidencia/documentación de la rama, no a una ejecución nueva en esta sesión.

## Plan de publicación y numeración

Se movió el plan que estaba en `docs/plan_publicacion_v36.md` a `docs/plan_publicacion_v37.md`. El contenido ahora reserva **v37.0** para el trabajo del motor que el plan antiguo situaba en v36, y pasa la fase de neuronas que figuraba como siguiente v37 a **v38.0**. La rama del auditor no contenía un `docs/plan_publicacion_v37.md` independiente; por eso no se inventó un segundo plan ni se creó un `plan_publicacion_v38.md` sin decisiones de alcance. El plan v37 mantiene ese límite explícito.

## Dónde quedó E3 / siguiente paso

- **E3 sigue abierto.** La auditoría sintética de atribución/historial (`docs/auditoria_e3_atribucion_8a7fa13_20261103.md`) también señala que el origen de la ráfaga y su relación con paráfrasis siguen sin resolverse; las sondas no identifican la puerta de exclusión ni justifican un parche de motor.
- No se cambió el filtro ni se aprobó una corrección de producción durante esta sincronización. Los scripts e informes de diagnóstico se conservaron como trabajo exploratorio.
- **E4 no se inició.** La ruta de DB externalizada es un cambio de infraestructura ya incluido en la rama del auditor; no equivale a cerrar E3/E4 ni a validar el estado de la base real.
- Antes de proseguir con el plan v37: revisar la discrepancia `VERSION`/README/`pyproject`, continuar E3 con controles sintéticos y atribución por consulta, y no usar/abrir la DB externa como fixture. Después de la decisión de cierre E3 se puede reordenar el paso E4 conforme al plan.

## Límites de esta actualización

No se ejecutó el instalador, no se probó la migración sobre una DB real, no se abrió/copió/reparó la base original, no se tocaron tests ni se cambiaron dependencias. La sincronización integró los commits ya presentes en la rama del auditor; el siguiente cambio de release debe resolver explícitamente el `VERSION` desfasado, no asumir que quedó corregido por el merge.
