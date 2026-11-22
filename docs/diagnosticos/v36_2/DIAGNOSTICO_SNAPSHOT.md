# Diagnóstico de competencia de recuerdos — snapshot recibido

## Conclusión ejecutiva
Se reprodujeron y aislaron dos fallos de selección diferentes:

1. Con `ultima_version_biorag` activo, la consulta natural se interpreta también como identidad exacta. El bono de nombre lo coloca primero aunque su contenido declare que es obsoleto. Quitar SOLO ese bono, en una intervención experimental sobre una copia, hace ganar a `version_actual_biorag`.
2. Con ese nodo dormido, v32.4 gana al canónico v36.1 por las señales de similitud del ranking. El campeón neuronal real está cargado y participa; no corrige la pareja: su corrección también favorece a v32.4 y el margen de seguridad refuerza el orden previo.

La neurona existente aprende recuperación de nodos mediante autoexámenes, no una tarea explícita de decidir entre afirmaciones vigentes y sustituidas. Sus 29 entradas no incluyen una relación explícita de sustitución o autoridad. No hay evidencia de que estuviera apagada en las reproducciones; tampoco de que baste con ampliar el pool o eliminar la regla de identidad.

No se aplicó ninguna corrección productiva. Estos resultados diagnostican el snapshot y el código ensayados, no reconstruyen con certeza cada intervención histórica.

## 1. Integridad y aislamiento

- Archivo recibido: `memory_biorag.db.7z`, 23.283.456 bytes. MD5: `ff586aed997937bfb4165d7481841d11`.
- DB extraída: 135.077.888 bytes; MD5 `e9f48aa8ef966624d42fb0ede2939639`, idéntico al del archivo sin comprimir consultado anteriormente en Drive.
- SHA-256 DB: `07a77c801eaa56750627e1c831de91a65e6448da25e4803b86d3ae4e2446c55e`.
- `PRAGMA quick_check`: `ok`. 1.325 nodos activos y 56 dormidos.
- Recibido conservado sin modificaciones; cada variante parte de una copia nueva. Se verificó SHA-256 intacto tras las ejecuciones.
- Código copiado a un directorio aislado; sin `.env.local` heredado ni uso de DB viva. HOME aislado. Sin entrenamiento ni consolidación voluntaria. El motor puede realizar migraciones, accesos y mantenimiento normales SOLO en copias.
- Python 3.11; dependencias fijadas de requirements.txt; PYTHONHASHSEED=1. Corridas definitivas con WordNet/OMW locales y auto-descarga desactivada; update checker y síntesis DMN al inicio desactivados. Hubo corridas exploratorias previas sin corpus WordNet, no usadas para las cifras definitivas.
- No se conoce la configuración completa ni los bytes exactos del servidor original. La huella funcional neuronal coincide exactamente: `5721b3821c3521e6`, versión interna 2, campeón válido, margen 2.0. Esto acredita compatibilidad de la fórmula comprobada, no identidad absoluta de todo el entorno.
- DB y archivo comprimido no se versionan. Las trazas resumidas no contienen cuerpos de recuerdos ni el resto de la memoria privada.

## 2. Consulta ejecutada

Se llamó al handler real `core.mcp_server.search._recordar_impl`, con la instancia de memoria conectada únicamente a la copia:

```python
_recordar_impl(
    query="ultima version biorag",
    sustantivos_clave="ultima,version,biorag",
    parafrasis="cual es la ultima version de biorag,ultimo release publicado",
    limite=5,
    asociados=True,
)
```

Se instrumentaron la fórmula de scoring y la función neuronal para capturar entradas, orden previo, correcciones, claves de decisión y orden posterior. Los cambios experimentales son monkeypatches del proceso, no ediciones del motor distribuido.

## 3. Estado recibido: la supuesta cuarentena no está vigente como estado de DB

`ultima_version_biorag` llega **activo**, peso **0.35**, sin `fecha_expiracion`. Su contenido dice que es obsoleto y remite al canónico, pero esa advertencia textual no equivale a una exclusión estructurada. El canónico llega activo, peso 0.21; v32.4 activo, peso ~0.33.

No se puede afirmar que el archivo recibido lo tenga dormido o en cuarentena efectiva solo porque el texto use esa palabra.

## 4. Por qué gana el nodo obsoleto activo

| Resultado | Score servido |
|---|---:|
| ultima_version_biorag | 0.9586 |
| version_actual_biorag | 0.8522 |
| version_actual_biorag_v32_4_20261007 | 0.8168 |

La traza prueba `match_exacto=True` para el primero. En la fórmula, antes de otros ajustes, su score pasa de **0.3658 sin el bono** a **0.9161 con él**. El BM25 normalizado de ese nodo es solo ~0.1936; no gana por tener el mejor BM25.

Control causal: desactivar SOLO el bono exacto en la llamada a la fórmula, manteniendo consulta, DB y resto de parámetros, deja al canónico primero con 0.8522. El obsoleto sale del top-5.

La regla de identidad neuronal también se activa, pero **no es la causa decisiva en este snapshot**: al desactivarla por sí sola, sigue ganando el obsoleto. El campeón y el margen ya lo prefieren. No presentar el veto de identidad como explicación suficiente.

## 5. Por qué sigue ganando una versión histórica al dormir el obsoleto

Intervención experimental: únicamente en la copia, poner `ultima_version_biorag` en dormido con peso 0.05.

| Señal | v32.4 histórico | Canónico v36.1 |
|---|---:|---:|
| BM25 normalizado | 0.71053 | 0.36711 |
| Coincidencia en sinónimos | 1.0 | 1.0 |
| PPMI | 0.73911 | 0.59697 |
| Peso sináptico | 0.33 | 0.21 |
| Score de fórmula | 0.7014 | 0.6476 |
| Score previo a neurona | 0.7746 | 0.7208 |
| Corrección del campeón | 10.06383 | 9.84353 |
| Clave neuronal (base + corrección + prior) | 21.29830 | 18.79196 |

El campeón procesa ambos y conserva v32.4 arriba. Incluso quitando mentalmente el prior, base+corrección sigue favoreciendo v32.4. Las correcciones son valores internos, NO probabilidades ni puntuaciones finales de relevancia.

Ambos registros incluyen `ultima_version_biorag` entre sus sinónimos; ambos reciben coincidencia completa. Tener ese alias no expresa cuál sigue vigente.

Ablación local de la fórmula, congelando los demás inputs (NO evaluación E2E de una solución):

| Inputs de v32.4 igualados a los del canónico | Score v32.4 | Score canónico |
|---|---:|---:|
| Ninguno | 0.7014 | 0.6476 |
| Solo BM25 | 0.6556 | 0.6476 |
| Solo peso | 0.6953 | 0.6476 |
| Solo PPMI | 0.6733 | 0.6476 |
| BM25 + peso + PPMI | 0.6176 | 0.6476 |

La ventaja no se explica solo por el peso ni por una sola coincidencia de nombre del canónico. El ranking está recompensando afinidad con la consulta; no hay una comparación explícita de sustitución/vigencia en esas entradas.

Cambiar el estado del obsoleto también cambia semillas y señales derivadas del pool: por ejemplo las dimensiones inferidas de ambos pasan a cero y cambia BM25 normalizado. El código tiene pseudo-relevance feedback con semillas FTS y otras señales dependientes del conjunto. No interpretar dormir un nodo como una simple eliminación posterior al ranking con todos los scores restantes constantes.

## 6. Qué está aprendiendo la neurona

El snapshot tiene 446 ciclos, 10 ascensos y un campeón persistido válido. La memoria de examen contiene 352 casos de estudio y 66 de guardia. Ninguno de esos 418 casos tiene como nodo objetivo uno de los tres nodos investigados; esto no demuestra que nunca fueran practicados antes.

`neurona_examen.preguntas` genera variantes, preguntas temáticas/de contenido, etc., desde cada recuerdo, con ese propio recuerdo como objetivo. `neurona._preguntar` descarta el caso si el objetivo no entra a la vista. Esto es entrenamiento de recuperación de identidad/contenido; no equivale a supervisión contrastiva de vigencia entre afirmaciones históricas.

Las 29 señales son de coincidencia, similitud, origen, convergencia y peso/contexto. No incluyen un campo explícito de sustitución, estado de aprobación o canal DEV/Stable. La corrección real observada NO favorece al canónico en el ensayo con el obsoleto dormido.

## 7. Reactivación: el relato original no queda respaldado

- Dos consultas normales consecutivas sobre la copia con nodo dormido: sigue dormido y peso 0.05. No se reproduce 0.05→0.27.
- Misma consulta con `deep=True`: se despierta y pasa 0.05→0.20, conforme al incremento +0.15 de la rama profunda. La segunda consulta mantiene 0.20.
- La DB recibida contiene consultas profundas explícitas por ese identificador (por ejemplo logs 9551 y 9552). Por tanto, hubo lecturas capaces de despertarlo durante la investigación previa. No se puede atribuir cada transición histórica sin la secuencia completa de escrituras, pero sí refutar que el snapshot y la reproducción demuestren una reactivación inevitable por consulta normal.

## 8. Puesto 7: no confirmado, y hay evidencia histórica distinta

El pool MCP es hasta 3×limite; puesto interno 7 es posible. La neurona solo reordena la vista pública (5 con limite=5), así que un candidato séptimo sería inaccesible a esa corrección. Esto sigue comprobado por la prueba estructural.

Sin embargo, los logs guardados relevantes 9557 y 9560 enumeran al canónico **segundo** en el top registrado por el motor; 9557 tiene v32.4 primero y 9560 al obsoleto primero. Las reproducciones actuales también lo sitúan segundo, no séptimo. Esos logs no son una traza completa de todas las etapas MCP ni guardan los 15 candidatos. La afirmación específica de puesto 7 permanece sin acreditar y no se usa como causa de este diagnóstico.

## 9. Alcance y próximos pasos

Queda explicado de forma reproducible por qué ganan esos competidores en el snapshot actual y por qué el campeón no lo corrige. No es una neurona ausente: son señales/objetivo de recuperación, bonos y restricciones que no acreditan vigencia.

No queda reconstruido el ranking exacto antes del saneamiento, ni el incremento histórico 0.05→0.27, ni el supuesto puesto 7. Para eso harían falta snapshot anterior y trazas completas. El defecto de columnas de antigüedad sigue siendo independiente y no se corrigió.

La elección de solución queda para revisión con el usuario. No se propone eliminar el bono globalmente basándose en un solo caso, añadir recencia indiscriminada ni reentrenar la neurona sin diseño y controles.

## Archivos reproducibles

- `rastrear_snapshot.py`: ejecuta handler real sobre copia nueva y registra trazas sin cuerpos de recuerdos. Requiere código y corpus/configuración compatibles; WORKDIR no debe existir.
- `resultados_resumidos.json`: seis variantes definitivas, filtradas a los tres conceptos investigados.
- `verificar_limites.py`: pruebas estructurales independientes con campeón simulado; no confundir con las corridas del campeón real.
- `DIAGNOSTICO_PRELIMINAR.md`: estado previo a recibir la DB; este documento lo actualiza.
