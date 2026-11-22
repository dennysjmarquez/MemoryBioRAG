# Auditoría E3: FP ingleses y etiquetas pendientes — `e4ce0b3`

## Decisión

La medición sintética y su repetibilidad se **reproducen en los indicadores comprobados**. No supone una reparación de los FP ni una resolución de las etiquetas; E3 sigue abierto. No se autorizan parches, entrenamiento ni paso a E4 con esta auditoría.

## Método e integridad

El commit `e4ce0b3e19f391380bb39ba301819497e7934620`, confirmado como cabeza del operador al hacer fetch, agrega solo el informe y un script diagnóstico frente a `0fff2b0`; no cambia motor. Se cotejaron motor, configuración, evaluadores y archivos gold y etiquetas con la rama auditora `fa980b3`: idénticos en las rutas inspeccionadas. Hashes del script `b993533f2df9768e743cef8220c2ec04990470033802664cc01feaa3277eb606`, motor `7193ee7f9e4fdcc52787d8dc107d7456cbaedecac687e084d4e15f450a4ba8e6`, gold `d3665a8e895ba061354ddd7d9c4fe44614956ad79d663433c6ef70e59aa78a6a` y etiquetas `ecadfca36f142e5f9cb00d86cce8c90bff29849c6d482c5034587d8f0a04b1dc` coinciden con el manifiesto Drive. El hash del JSON que figura en dicho manifiesto coincide con los metadatos Drive; **no se descargó ni comparó su contenido completo caso a caso**. La carpeta mostró únicamente permiso de propietario.

Se ejecutó el script exacto en checkout temporal del commit, con dependencias aisladas y datos NLTK locales, `PYTHONHASHSEED=0`, neurona apagada y reloj fijo, con salida detallada y log en privado. Fixture nueva de 120 recuerdos, `integrity_check=ok`; copias por llamada y hash de fuente sin cambios durante la prueba. La fuente se reconstruyó y su SHA fue distinto del operador, por lo que no se afirma identidad binaria de las bases. Salida código 0. La llamada MCP fue a `_recordar_impl` con `_get_cerebro` instrumentado, no una sesión stdio ni un agente autónomo.

## Resultados cotejados

- Dos controles negativos ingleses dieron resultados en directo y MCP: **2/2** cada uno. No es tasa general de falsos positivos.
- Las **14/14** etiquetas pendientes fueron rechazadas por validación MCP sin abrir el cerebro instrumentado; no son búsquedas vacías ni abstenciones. En directo se recuperó el esperado en **7/14** (seis primeros y un segundo); otras siete búsquedas devolvieron cero resultados. No se cambiaron etiquetas.
- Las 16 mediciones directas y las 16 MCP se repitieron en orden inverso, con cero diferencias en los campos comparados. Copias de DB por sí solas no aíslan cachés globales del proceso: el orden inverso es un control acotado, no una garantía general.
- Contra el archivo de la referencia E3B3 se observaron tres diferencias directas, que son las tres recuperaciones adicionales japonesas, y cuatro discrepancias MCP exclusivamente en representación NFC del término invalidado, con iguales campos de error y búsqueda. La referencia procede de otro commit; no es una corrida del motor actual.
- La sonda de predicados aislados sobre los tres esperados confirmó que el predicado histórico rechaza y el actual acepta. Esto es **compatible** con la diferencia observada; la prueba no intercambia solo ese predicado en ambos motores ni demuestra que sea la causa exclusiva de las tres diferencias históricas.

## FP y límite de causalidad

La reproducción del rastreador mostró el mismo patrón: primer control con resultado y score iguales con WordNet activo o apagado, segundo con resultado solo al activarlo; los hits rastreados son fragmentos de palabras, sin coincidencia completa detectada en la comprobación. Para evitar la contaminación de la caché por alternancia en un proceso, se repitió la ablación en **procesos separados** contra copias de una misma fuente sintética: mismo patrón y los resultados apagados coinciden con la ejecución del operador.

La traza muestra un lema de la expansión y un hit FTS compatibles con el segundo caso, pero no interviene en ese único lema ni excluye todas las rutas que pudieran contribuir. El test `BIORAG_WORDNET_ENABLED=0` altera más de una ruta, por lo que no se declara causalidad exclusiva de ese lema o de FTS. No se recomienda desactivar WordNet, eliminar conectores, pistas o filtrar por estos dos negativos.

## Continuación

Volver al inventario original del resto de E3 y distinguir la **fusión de etiquetas pospuesta** de estas etiquetas de prueba pendientes; no reetiquetar ni fusionar por inferencia. Si se plantea mejora, pedir evidencia pareada con diff aislado, recall y pistas completos, controles positivos y negativos, además de medir agente+cerebro cuando corresponda. Ningún cambio de motor sin autorización específica. E4 y fase 2 esperan su turno.

Evidencia auditora privada, incluidos resultados detallados y la instrumentación de la ablación en procesos separados: `auditoria_e3_fp_e4ce0b3.tar.gz`, SHA-256 `ca305989124cb311d83ca4622c60493533fe8244bbc8b6f3ea0acfde6abffe8f`, Drive `1UG_5uKIZE3ppldjaYa-OrpYuZ8FgcEEU`. No incluye SQLite ni base original. Las salidas completas del operador continúan en su carpeta privada.
