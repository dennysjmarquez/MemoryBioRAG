# E3: rutas de creación y densidad de grafo en fixtures sintéticas

- **Fecha:** 2026-11-02
- **Alcance:** continuación experimental del inventario E3; sin cambio de motor, política de etiquetas ni avance a E4.

## Diseño

Se amplió el control MCP stdio a la creación por `aprender` y su alias `guardar`, seguida de la transferencia explícita `consolidar` desde corto a largo plazo. En cada copia se hizo una búsqueda previa; se verificó que el objetivo aún no estaba presente, se creó el recuerdo y se consultó una pista histórica después de consolidar.

Matriz: tres historias sintéticas (historia útil con pista solo en etiqueta; término contradictorio conservado en el contenido; pista alternativa en un vecino), cuatro densidades y dos rutas de escritura, con pista activa/control neutral de igual longitud: **48 sesiones**, **24 pares**. Las densidades cruzan dos factores por separado: cero o dos vecinos que la ruta de creación puede enlazar, y cero o dos nodos candidatos adicionales. Todas las copias conservan un ancla fija. El orden de las búsquedas no se volvió a variar en esta matriz; esa pregunta está cubierta por la prueba anterior.

Cada sesión usó una copia SQLite y estado DMN aislados, reloj fijo y snapshots tras initialize, primera llamada, búsqueda previa, creación, lectura en corto, consolidación, lectura en largo y recuperación histórica. Se guardaron 432 snapshots con filas completas de las tablas de grafo incluidas en el alcance más la proyección de asociaciones; también se leyeron directamente las columnas plegada/exacta en corto y largo. El manifiesto íntegro de pistas y textos sintéticos y todas las trazas quedan privados.

## Resultados observados

- **48/48 brazos** y **24/24 pares** fueron válidos; cero errores MCP, errores de herramientas, errores de lectura de grafo o de almacenamiento. El objetivo no apareció en ninguna búsqueda previa.
- Las dos columnas de etiquetas coincidieron con sus valores esperados mediante lectura SQL directa en corto y después de consolidar en largo: **48/48** en cada etapa. Las filas completas del grafo fueron iguales entre brazos activo/control en todas las etapas comparables: **24/24 pares**.
- Por cada ruta (`aprender` y `guardar`) y en las cuatro densidades: la historia útil recuperó el objetivo como primario **4/4** con pista activa y **0/4** con neutral; la historia contradicha lo recuperó **4/4** en ambos brazos; la familia de vecino lo recuperó como primario **4/4** con pista activa, mientras el neutral no tuvo hits primarios (**0/4**) y sí apareció en contexto **2/4**, en las dos densidades que incluían vecinos.
- Se contaron filas `dmn_synthesized` añadidas entre el snapshot previo a stdio y el posterior a la primera llamada. Por densidad —12 brazos por condición— los totales observados fueron: dispersa **0**, solo vecinos **12**, solo candidatos **12** y densa **64**. Son filas observadas en ese intervalo, no recuentos de candidatos recuperados ni prueba de un subpaso interno concreto.
- Tras la creación, en las dos condiciones con vecinos se observaron **24 filas de tipo `manual` por condición** (dos por brazo); las condiciones sin vecinos tuvieron cero. El snapshot completo también conserva las otras aristas creadas por la ruta de escritura; la métrica manual no se usa como sinónimo de todo el grafo.

## Límites y trabajo E3 restante

La combinación de ruta de escritura, densidad, historia y brazo fue sintética y acotada. La recuperación del término contradicho no adjudica vigencia ni verdad; la recuperación por contexto no determina por sí sola la procedencia de cada pista. Los resultados apoyan observaciones en estas copias, no una regla general ni una elección entre reemplazo y acumulación.

Esta matriz cubre `aprender`/`guardar`, la ruta de percepción que invocan y `consolidar` corto→largo; no aísla cada función interna ni cubre todas las entradas de escritura del sistema, otros idiomas o todos los frentes del inventario. E3 sigue abierto. Las pistas no se fusionaron ni descartaron; no hubo backfill ni reetiquetado.

## Evidencia y reproducibilidad

El agregado de este documento es publicable. El manifiesto detallado y trazas por caso permanecen en `.private_evidence/e3_rutas_creacion_densidad_20261102_run02/`, excluidos de Git. Los archivos incluyen hashes canónicos y de bytes exactos, verificados después de escribir; las evidencias anteriores permanecen separadas.

```bash
PYTHONHASHSEED=0 /tmp/e3-mcp-venv/bin/python scripts/diagnosticar_rutas_creacion_densidad_e3.py \
  --evidence-dir .private_evidence/<directorio-nuevo>
```

El arnés rechaza destinos existentes y rutas fuera de `.private_evidence/`. No toca bases reales ni código del motor. E4 permanece en espera.
