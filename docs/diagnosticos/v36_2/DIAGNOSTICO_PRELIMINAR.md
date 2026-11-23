# Incidente de recuperación de vigencia — diagnóstico preliminar

## Estado
Investigación parcial: restricciones del reordenamiento comprobadas; causa exacta del incidente NO determinada. No se ha cambiado el motor, sus pesos, su modelo ni ninguna DB. No se propone todavía una solución.

## Evidencia disponible
- Working tree de esta sesión; no asumir identidad con el entorno que atendió la consulta original. HEAD es f8c2b166b6f13cd7bbbdffb13135d3d68354b8e0, pero hay modificaciones locales preexistentes: HEAD no identifica los bytes actuales.
- `memory_biorag.db`: archivo de 0 bytes, sin tablas.
- `snapshots/qa_escape_qcr_20260811.db`: snapshot antiguo, contiene version_actual_biorag referido a v26.3, pero no los nodos recientes del incidente.
- Inspección SQLite con URI mode=ro; sin ejecución del motor sobre esas bases.
- No se encontró ~/.biorag ni otra DB candidata en la búsqueda acotada realizada en /home/user y uploads.

## Resultados comprobados en el código actual

### A. Un candidato #7 queda fuera de la neurona con limite=5
`core/mcp_server/search.py`, `_recordar_impl`: recupera `limite_interno = limite * 3`, pero pasa `convergencia_limite=limite` a buscar_por_frase. Con limite=5, pool de hasta 15 y vista neuronal de 5. `core/memory/neurona.py`, `vista`: limita la vista a los primeros k. `reordenar` devuelve `nuevo + pagina[k:]`: no puede promover el séptimo al top-5.

Probado con funciones reales extraídas mediante AST y dependencias/campeón simulados: incluso una corrección extrema no introduce al séptimo. Esto demuestra la restricción; NO demuestra que el canónico ocupase realmente esa posición en la ejecución reportada.

Corrección a nuestra observación anterior: limite=5 no hace imposible una posición interna 7. Sí exige una traza interna o consulta ampliada para acreditarla; no se observa directamente en cinco resultados públicos.

### B. La regla de identidad puede vetar a la neurona
`neurona._es_su_nombre` normaliza guiones bajos a espacios. Si el primer candidato se llama ultima_version_biorag y la consulta es ultima version biorag, `reordenar` conserva el índice 0 aunque el campeón prefiera otro candidato. Prueba controlada con correcciones [-100, +100]: identidad conserva el primero; cambiando solo la consulta, el segundo gana.

Esta restricción es adicional al bono +2.94 log-odds de `core/memory/scoring.py`. No afirmar que alguno se activó en la consulta real sin traza del entorno original.

### C. Dormir no equivale a declarar sustituido
`_recordar_impl` usa deep=False por defecto, que se traduce a profundidad=activos. Hay filtros de estado activo. `core/memory/search.py` despierta nodos dormidos en la rama profundidad=profundo y suma 0.15 al peso en esa rama.

La llamada reportada no incluye deep=True. Por ello, NO está explicado que un dormido se reactive por esa llamada, ni el incremento exacto 0.05→0.27. Hay que auditar la ejecución real completa, fallbacks, llamadas adicionales, configuración, tareas concurrentes y código efectivo. No deducir que el nombre exacto por sí solo evade el estado en todas las rutas.

### D. Antigüedad MCP: defecto independiente
La consulta usa categorias/c.nombre mientras el esquema define categories/name. Se silencia el error con except Exception: pass. No se corrigió: es independiente del diagnóstico causal de ranking y la antigüedad no prueba vigencia.

## Prueba reproducible ejecutada
`verificar_limites.py` requiere numpy. No importa el motor ni abre DB. Extrae las funciones reales vista/reordenar/normalización/base y simula el campeón y auxiliares para aislar restricciones estructurales.

Resultado: 3 PASS (exclusión del #7, veto por identidad y control sin identidad). No es un E2E, una evaluación del modelo aprendido ni una reproducción del incidente.

SHA-256 de core/memory/neurona.py utilizado:
`da5943dab2d32c512c303a8fe8e3ab78cb01a8e87bcf180dbfdfc0f1eb38abe7`

## Evidencia necesaria para continuar hasta causa exacta
1. Snapshot SQLite consistente del entorno del incidente, idealmente anterior a los cambios manuales y consultas de réplica. Usar backup API de SQLite o equivalente; no copiar solo el .db si WAL está activo. Compartir por adjunto privado, no subir la memoria a Git.
2. Código efectivo/commit y modificaciones locales del servidor MCP que atendió la consulta.
3. Configuración BIORAG_* pertinente (sin secretos), versión Python y dependencias, estado y campeón neuronal persistido.
4. Llamada y respuesta originales completas y secuencia de llamadas/mutaciones. Indicar si hubo deep, ráfaga, herramientas de lectura profunda o procesos concurrentes.

Si solo existe snapshot posterior a las intervenciones, se podrá diagnosticar ese estado y reproducir mecanismos, pero no acreditar exactamente el ranking histórico anterior.

## Siguiente ensayo
Sobre backups aislados idénticos: consulta original con traza de candidatos y scores antes/después de cada etapa; estado/peso/accesos antes/después; vista y decisión neuronal; controles sin campeón y sin identidad SOLO en instrumentación experimental, no cambios productivos. Repetición secuencial en otra copia. No ejecutar sobre DB viva.
