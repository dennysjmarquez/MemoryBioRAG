# Procedimiento de revisión ciega E1 — paquete v1

**Estado: preparado, no enviado a agentes y no revisado.** No modifica/cierra el gold ni autoriza E1.

## Artefactos

- Paquete para revisor: `docs/paquete_ciego_revision_semantica_e1_v1.jsonl`
- Manifiesto técnico: `docs/manifiesto_paquete_ciego_revision_semantica_e1_v1.json`
- Generador reproducible: `scripts/preparar_paquete_ciego_e1.py`
- Crosswalk privado con etiquetas e **textos originales**: `.private_evidence/e1_blind_review_v1/crosswalk_private_r6.jsonl` (directorio `0700`, archivo `0600`; no entregar a revisores ni añadir al control de versiones).

Hash SHA-256 del paquete: `c6445643cf8750cd85f841c4f3c8b6211c9ecb2a7e5777a43c56764c98112a90`.

## Composición y mezcla

- 33 consultas/casos; se mantienen las 90 asignaciones bajo revisión: 33 de objetivo y 57 de pista.
- 66 presentaciones adicionales: exactamente 2 por caso, muestreadas sin reemplazo entre los otros nodos del mismo episodio, sin filtrar por su rol gold. Total: 156 presentaciones. El mismo nodo de fuente puede aparecer en casos distintos.
- Semilla de mezcla: `20261101`. El generador ordena las entradas de origen, toma las 2 adicionales, mezcla los candidatos dentro de cada caso, mezcla los casos y asigna códigos opacos mediante el mismo PRNG.
- Campos visibles: `case_code`, `question`, `items[].item_code`, `items[].text`. No se suministran IDs de fuente, roles, justificaciones, fragmentos de evidencia ya anotados, respuesta gold, tipo de consulta, expectativa de abstención, estrato ni respuestas de otros revisores.

## Transformaciones exactas del texto presentado

La consulta se copia verbatim. Para cada texto de recuerdo se aplican, en este orden, solo las reglas listadas abajo; el crosswalk privado retiene la cadena original, la presentada y las reglas aplicadas:

1. Regex `^.{1,90}?\b[0-9]{1,3}\s*:\s*`: quitar el título inicial numerado completo y preservar el cuerpo a partir del primer carácter posterior al match. Se aplicó en 147 presentaciones.
2. Regex `\s*This is the primary decision\.\s*$`: quitar esa oración final exacta si está presente. Se aplicó en 4 presentaciones.
3. Regex `\bacción primaria es\b` (sin distinción de mayúsculas): reemplazar el match por `acción es`, preservando el texto de la acción. Se aplicó en 5 presentaciones.

No se traduce, parafrasea, normaliza el caso ni se reescribe el contenido restante. Los códigos de caso/artículo sustituyen los identificadores originales. La selección de adicionales y las transformaciones no alteran el JSONL gold.

## Verificación de fuga

El generador falló cerrado si no hallaba 33 casos, 33/57 asignaciones, 66 adicionales o 90 asignaciones únicas; si no podía elegir dos candidatos adicionales en un caso; o si detectaba IDs `qa_pos_*`, claves/metadatos gold, títulos numerados o frases de rol revisadas en el paquete. Se comprobaron los esquemas visibles (solo las cuatro claves previstas), la unicidad de códigos y los totales 33/156. El hash del crosswalk se registra únicamente en el manifiesto; su contenido permanece privado.

Los títulos numerados se quitan porque varios contienen palabras que declaran el rol de origen. El manifest y el crosswalk tampoco se entregan a los revisores: además de documentar la transformación, podrían ayudar a reconstruir la correspondencia con el gold.

## Disponibilidad de sesiones y decisión de independencia

En este turno solo es identificable **la sesión actual de Arena Agent Mode**. No se expone un ID de sesión independiente ni una segunda sesión de agente separada; la sesión actual además ya tuvo acceso al gold/etiquetas y no es elegible como revisor ciego. Por tanto, no se asignó ni inició ninguna pasada y no se afirma que haya dos agentes disponibles.

Antes de una futura ejecución se debe identificar y registrar dos sesiones distintas, comprobar contextos frescos y aislamiento de memoria/historial, dar a ambas el mismo hash de paquete y rúbrica, negar acceso al gold/crosswalk/manifiesto y mantener oculta la salida de la otra hasta congelar y hashear ambas respuestas. Si no se puede verificar cada punto, cualquier pasada se rotula **exploratoria, no independiente**; no se calcula acuerdo de anotadores ni se usa para adjudicar o cerrar gold.

Cada agente devolvería por artículo una categoría provisional (`respuesta principal`, `pista útil`, `neutral`, `irrelevante/perjudicial` o `evidencia insuficiente`), fragmento textual, vínculo con la consulta, duda y confianza. Un adjudicador humano bilingüe, elegido por Dennys y preferentemente ajeno a las dos revisiones, podría resolver discrepancias después de conservar las respuestas originales. La revisión de agentes no sustituye automáticamente a revisores humanos ni constituye aprobación del gold.

**Pasadas iniciadas: 0. Gold modificado: no. Campaña E1 ejecutada: no. Motor/bases modificados: no. W sigue pendiente.**
