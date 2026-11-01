# Instrucciones neutrales para revisión semántica E1 — v1

Revisa cada elemento de `docs/paquete_ciego_revision_semantica_e1_v1.jsonl` usando solamente la pregunta y el texto visible de cada elemento. No busques el origen de los códigos ni intentes reconstruir etiquetas anteriores. No consultes motores, bases, recuerdos externos ni resultados de E1.

Para cada par `case_code` + `item_code`, devuelve:

1. **Categoría provisional:** respuesta directa a la pregunta / pista indirecta útil / neutral / irrelevante o perjudicial / evidencia insuficiente.
2. **Evidencia textual:** cita el fragmento mínimo del recuerdo que sustenta la decisión. Si no hay uno, escribe “sin evidencia textual suficiente”.
3. **Relación con la consulta:** explica en una frase qué parte de la pregunta responde, qué posible paso de razonamiento apoya o por qué no se establece relación.
4. **Duda:** registra ambigüedad, falta de contexto, posible rol alternativo o cualquier supuesto necesario.
5. **Confianza:** baja / media / alta, con una breve razón.

No uses coincidencia de palabras por sí sola como prueba. No supongas que un elemento es útil o ruido solo por el lugar donde aparece; distingue respuesta directa, apoyo indirecto y contexto neutral. Si una etiqueta depende de evidencia no visible, marca insuficiente en vez de completarla con conocimiento externo.

Entrega un registro por cada elemento visible, conserva los códigos opacos, no omitas desacuerdos internos ni fusionas categorías. No revises, edites ni cierres ningún gold. Guarda esta pasada por separado y no la compartas con otro revisor hasta que ambas respuestas hayan sido congeladas y sus hashes registrados.

Estas instrucciones no convierten una pasada de agente en anotación humana independiente. Si el aislamiento de sesión no puede verificarse, identifícala como **exploratoria, no independiente**.
