# Competencia contextual — laboratorio, NO integrado

## Contrato definido antes del experimento

Objetivo: comprobar si evidencia explícita de revisión permite ordenar candidatos sin borrar historia, fabricar autoridad ni aprender de la mera exposición. Usuarios finales: agentes que registran una corrección del usuario junto a su evidencia; no se espera que el usuario edite SQL. Interfaz MCP/CLI futura, fuera de esta prueba.

La recuperación natural y los sinónimos ya se probaron en el diagnóstico: no expresan sustitución. Se justifica un laboratorio pequeño desacoplado, no migrar el córtex ni otra neurona todavía.

### Hipótesis aislada
Para atributos **monovalorados dentro de un alcance exacto**, una relación confirmada `nuevo sustituye anterior`, con fuente y tiempo efectivo, permite seleccionar el extremo vigente sin tocar los scores de parecido. Si quedan valores incompatibles sin resolución, se señala conflicto y se conserva la lista. El prototipo no descubre contradicciones semánticas en texto ni verifica por sí solo las fuentes declaradas.

### Invariancia obligatoria
Sea N el total de afirmaciones del ledger y k las del contexto `(entidad, atributo, alcance)`. Se mantienen idénticos consulta estructurada, instante explícito, candidatos y scores. Información irrelevante: afirmaciones/aristas de otros contextos; y, para la decisión, candidatos sin evidencia del contexto. Se exige igualdad exacta (tolerancia 0) del ganador, estado y evidencia explicativa al añadir 10.000 afirmaciones ajenas. Si se añaden candidatos ajenos, sus posiciones se conservan salvo el desplazamiento estable por promoción; se compara además la proyección sobre candidatos originales. No se promete invariancia del BM25 aguas arriba.

Índice SQLite por contexto y fecha; lectura O(log N + k), resolución O(k+e), reordenamiento O(m), m candidatos. Límite explícito de k; si se supera, error visible, nunca truncamiento silencioso. No se promete O(1).

### Guardianes / criterios previos
- Sin metadatos pertinentes: lista exactamente intacta, estado desconocido.
- Consultas históricas, genéricas o por ID: no reordenar automáticamente.
- Misma membresía y scores originales antes/después; no se elimina ruido útil.
- Ante conflicto: winner=null, lista disponible e intacta; nunca declarar ganador por popularidad.
- Si el vigente no está en candidatos: retrieval_gap; no presentar el viejo como vigente.
- Tiempo explícito, sin reloj de pared ni decay implícito.
- Validar alcances, ciclos, extremos, fuentes, intervalos y entradas no finitas.
- La lectura no escribe ni confirma nada.
- Separación total de la DB de memoria; ledger lateral experimental.
- Ni reglas de dominio ni nombres concretos en la lógica.

## Estado / límites de aceptación
Este laboratorio NO es v36.2 publicada ni un fix del motor, ni un router de lenguaje natural ni un modelo entrenado. La intención y el contexto son entradas estructuradas suministradas por el agente. Las correcciones son datos de prueba explícitos, no relaciones descubiertas autónomamente. Un resultado positivo aquí no acredita mejora autónoma en una DB sin metadatos.

No se aprueba integración sin QA 921 emparejada sobre copias, pruebas de regresión del motor, comparación con baseline en copia de DB actual y revisión del usuario. Esta fase no modifica VERSION, core ni el modelo de 29 señales. No se infiere vida o consciencia de este comportamiento.

## Ejecutar

```bash
python -m unittest discover -s scripts/experimentos/competencia_contextual -p 'test_*.py' -v
python scripts/experimentos/competencia_contextual/experimento.py
# Opcional, solo lectura de un snapshot suministrado; backup SQLite temporal:
python scripts/experimentos/competencia_contextual/experimento.py --snapshot /ruta/backup.db
```

No usar una base viva como argumento. El ensayo de snapshot usa rankings previamente capturados en el diagnóstico, NO vuelve a ejecutar BM25 ni la neurona. Comprueba los nodos por SQL en una copia temporal y añade metadatos exclusivamente al ledger de laboratorio. El informe distingue este replay de un E2E nuevo.
