# Auditoría focalizada: neurona de puentes y conservación de pistas — 2026-11-01

## Propósito y alcance

Retomar los cimientos y el camino hacia las neuronas: comprobar una afirmación de seguridad del adaptador de puentes antes de diseñar o conectar nuevas neuronas. La revisión corresponde al código de `37e67c8`; no es una evaluación integral de búsqueda, MCP, recall ni de ninguna base real. No se entrenó ninguna neurona y no se consultaron bases privadas ni originales.

## Inspección

`core/memory/neurona_puentes.py` describe una compuerta previa de cobertura, un multiplicador entre 0,5 y 1 por defecto, pesos neutros y fallback. `core/concept_hub.py` efectivamente evalúa primero la cobertura; luego multiplica el score del puente por la confianza neuronal, agrupa por hub/recuerdo, aplica competencia y compara la confianza final con el umbral. Si no llega, devuelve `None` para esa expansión.

**Conclusión acotada:** que el multiplicador no cierre la primera compuerta no garantiza por sí solo que el hub siga siendo devuelto al final. La atenuación puede intervenir en una segunda decisión con umbral. Esto contradice una lectura fuerte de la frase «la compuerta y el recall quedan intactos» del módulo: la primera compuerta se conserva, pero el efecto posterior sobre la expansión requiere medición. Que el hub devuelva `None` no significa que se hayan eliminado recuerdos ni que toda la búsqueda deje de encontrarlos: podrían existir otras rutas.

El cargador devuelve parámetros neutros si no hay tabla o son inválidos; el hub omite el multiplicador cuando son neutros. La activación, parámetros y contribución en una memoria concreta **no se comprobaron**. También pueden influir la configuración, otros puentes, el ángulo, la competencia y la consulta.

## Reproducción sintética

Se añadió `scripts/auditar_compuerta_neurona_puentes_sintetica.py` (SHA-256 `b6a9cfa584c4280f277ee9e49f028b33c970bddb83ee9f909ea50ab99580c217`). Ejecuta la función real de expansión con un índice fabricado, conexión SQLite en memoria y parámetros inventados válidos, sin entrenar ni cargar datos o pesos reales. Parcha tokenización y lectura del índice para aislar la rama; no ejercita la construcción real del índice, MCP ni otras rutas de recuperación. Fija suelo 0,5, techo 1 y umbral 0,55.

El puente sintético tiene cobertura 1 y pasa la primera compuerta en ambos brazos. Con el adaptador apagado se devuelve el hub; con el adaptador activo y el estado simulado, se atenúa y no se devuelve el hub porque la confianza final queda por debajo del umbral. Salida literal:

```text
resultado=hub_devuelto_sin_neurona, hub_no_devuelto_con_neurona_simulada; gate_cobertura=aprobado_en_ambos
```

Es una caracterización del comportamiento actual, **no** un test de aceptación que apruebe perder el hub. Si más adelante se modifica esa conducta con autorización, revisar la aserción y conservar la evidencia anterior. La prueba no demuestra que exista pérdida en una base real ni que la ruta aporte una pista útil específica.

## Pruebas y límites

- `python -m pytest tests/test_neurona_puentes.py -k 'not aprende and not entrenar' -q`: **13 passed, 3 deselected**. Las tres excluidas ejercitan entrenamiento. Las pruebas seleccionadas usan datos sintéticos y SQLite en memoria; no demuestran preservación del resultado final del hub.
- El Python inicial del sistema no tenía pytest; se creó un entorno temporal separado con pytest y NumPy para la ejecución. No se modificó la configuración del proyecto.
- No se ejecutó E1, no se midió MCP, no se abrieron bases originales, no se cambiaron motor ni neuronas y no se entrenó nada.

## Siguiente acción

Auditar si alguna configuración activa afecta los resultados en condiciones controladas, únicamente en copias y dentro de los permisos vigentes, antes de proponer un cambio. Si se plantea una mejora, fijar baseline, diff aislado, preservación de pistas y comparación de trayectorias de agente + cerebro. No habilitar, deshabilitar, cablear, entrenar ni cambiar esta neurona sin la autorización correspondiente. La observación no justifica descartar la neurona: identifica una garantía que necesita revisión.
