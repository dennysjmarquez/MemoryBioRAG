# Propuesta breve: flujo completo del arnés con fixture sintética

**Estado: propuesta; no ejecutada.** La autorización previa para el smoke limitado no se toma como aprobación de congelación ni como autorización para iniciar una línea base.

## Diseño

- Crear un `BIORAG_QA_TEMP_ROOT` nuevo, externo al repositorio. Generar allí un único gold sintético diminuto (un episodio, tres nodos y dos aristas) y conservar su SHA-256. No abrir ni modificar el gold original ni ninguna base original.
- Ejecutar `prepare_fixture` dos veces desde cero contra el mismo gold sintético: dos archivos SQLite nuevos en rutas distintas, dos sesiones MCP reales y dos `construction_id` distintos. **No** copiar la primera fixture para fabricar la segunda. Conservar para cada construcción el manifiesto, el informe, los eventos MCP y cualquier marcador de fallo.
- Ejecutar `audit_repeatability` sobre esas dos construcciones y continuar solo si confirma `REPEATABLE_PAIR`, ledgers independientes, hash gold coincidente y estructura repetible. Inspeccionar y registrar la auditoría del grafo antes de pedir aprobación.
- Si se autoriza después la fase de medición, usar el `measure_baseline` real sin reemplazar validadores ni crear un manifiesto ficticio. Debe existir una aprobación humana explícita de Dennys, ligada a los hashes del gold sintético, la fixture y los informes revisados; la aprobación previa del smoke no basta. Si falta o no coincide, la guarda debe detener la medición y **no** se ejecuta ningún brazo.
- Con esa aprobación auténtica, medir solo la fixture sintética y sus copias aisladas, usando los brazos exactos configurados por el arnés: N0/N1, G1/G2 y R. Verificar en cada intento los canales por separado (resultados, contexto expandido, asociaciones y asociaciones enriquecidas), diffs por fila/campo y aislamiento de cada copia. W queda excluido.
- En una base sintética separada, provocar un único fallo MCP controlado. Confirmar que se preservan el evento crudo, el marcador de corrida inválida y sus hashes; detener cualquier medición si aparece un fallo o una mutación inesperada.

## Condiciones de parada

No ejecutar ahora preparación MCP, medición, ni QA. En la futura ejecución, detenerse antes de N/G/R si no hay aprobación real de Dennys o si falla cualquiera de los gates de repetibilidad, grafo o aislamiento. Si falla una llamada, preservar evidencia y marcar la corrida inválida; no reintentar sobre la misma base. No se cambia el motor, el ranking ni las bases originales.
