# E3 — investigación aislada de falsos positivos ingleses y etiquetas pendientes

**02 de noviembre de 2026.** Investigación de baseline únicamente. No se cambió el motor, no se aplicó ninguno de los parches CJK, no se reetiquetó gold ni se abrió una base real. El diagnóstico privado completo y su manifiesto SHA-256 se archivaron en Drive privado; este informe no contiene textos de consulta, respuestas gold ni crosswalk.

## Método y baseline

- Baseline actual: commit `0fff2b0dd25b4869299e84d737ba2dd3490598f7`; SHA-256 de `core/memory/search.py`: `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6`.
- Se reconstruyó una fixture sintética temporal de 120 recuerdos (`integrity_check=ok`). Se midieron dos controles negativos ingleses y los 14 casos que el registro de E3B3 clasifica como **«pendiente hueco 1»**. Cada consulta directa y MCP usó una copia limpia; se repitió el recorrido en orden inverso. La fuente permaneció intacta.
- Los dos negativos ingleses son una sonda pequeña, no una estimación de tasa general. El destino `--salida` del script nuevo contiene detalle por caso y textos, por lo que debe ser privado.

## Dos falsos positivos ingleses

Los dos controles negativos devolvieron un resultado en la búsqueda directa y en MCP (**2/2 en cada modo**). La ablación aislada de WordNet separa dos mecanismos distintos:

1. El primer falso positivo persiste con el mismo score al desactivar WordNet solo como diagnóstico. El FTS subraya un **fragmento dentro de un token más largo**, no una palabra completa; la comprobación de límite de palabra no encuentra coincidencia.
2. El segundo desaparece al desactivar WordNet. La traza muestra que una expansión añadió un lema corto que vuelve a coincidir como fragmento dentro de un token más largo; tampoco es una coincidencia de palabra completa.

Esto acota las causas de estos dos casos; **no** justifica apagar WordNet ni quitar filtros globalmente. La muestra contiene solo dos negativos sintéticos.

## Catorce etiquetas «pendiente hueco 1»

- MCP rechazó **14/14 antes de abrir la base** con `SUSTANTIVOS_CLAVE_FORMATO_INVALIDO`. Ninguna de esas llamadas ejecutó búsqueda; por tanto, el marcador no representa una búsqueda sin resultados ni una abstención correcta. **Se conservan las 14 etiquetas pendientes.**
- En la búsqueda directa baseline de la fixture actual, **7/14** recuperaron su esperado en top 5: seis en rango 1 y una en rango 2; las otras siete no devolvieron resultados.
- La referencia E3B3, generada sobre el commit `88f71bbbee9e340511d777b1b56d5d7ee8139802`, había registrado 4/14 esperados. Tres resultados japoneses adicionales aparecen en el baseline actual, cada uno en rango 1. La sonda aislada de los predicados confirmó que esos tres candidatos fallan el predicado histórico `PALABRA_PREFIJO` y pasan el predicado Unicode de ancho completo `PALABRA_INICIO_ANCHO`, ya presente en el motor actual. Es una diferencia entre baselines; no se introdujo en esta investigación ni requiere aplicar un parche CJK.
- Las cuatro discrepancias restantes al comparar la serialización MCP con E3B3 se limitan a la forma canónica NFC del término rechazado (jamo descompuestos en la referencia frente a sílaba compuesta ahora). Código de error, rechazo previo a búsqueda y resultados vacíos no cambiaron.

La diferencia de baseline merece conservarse como contexto: los archivos E3B3 y la medición actual corresponden a commits distintos. En la corrida actual, los 16 casos directos y los 16 MCP se repitieron en orden inverso sin diferencias; esto valida repetibilidad **dentro del baseline actual**, no convierte las referencias históricas en ejecuciones del HEAD actual.

## Evidencia y siguientes límites

El arnés reproducible es `scripts/diagnosticar_fp_ingles_y_etiquetas_pendientes_e3.py`. Su salida detallada —con consultas y etiquetas caso a caso— y el manifiesto de hashes se conservaron en la carpeta privada de Drive; no se incluyen en Git. La salida sintética no modificó los valores gold, no entrenó el sistema, no eliminó asociaciones ni cambió filtros.

E3 puede continuar con el inventario restante bajo el mismo principio: baseline actual, copias aisladas, resultados detallados en privado y solo agregados sanitizados en el repo. **No se avanza a E4** sin una decisión posterior.
