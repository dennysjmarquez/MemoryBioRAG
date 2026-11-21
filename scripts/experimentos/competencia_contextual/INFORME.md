# Resultado del primer prototipo de competencia contextual

## Veredicto
**Prueba de mecanismo positiva; integración bloqueada, no es un release.**

Se implementó un selector contextual externo con ledger SQLite lateral. Cuando recibe evidencia explícita de que una afirmación sustituye a otra dentro del mismo alcance, puede promover al candidato aplicable sin alterar scores ni eliminar los vecinos. Cuando la evidencia es incompatible o falta el candidato correcto, no declara ganador y conserva la lista.

No se necesitó otra neurona para demostrar esta pieza. Eso no decide aún si se debe ampliar la neurona existente para aprender contexto/pertinencia. Esta fase no tiene aprendizaje autónomo ni descubrimiento automático de sustituciones.

## Resultados ejecutados

### Pruebas del mecanismo

```text
python -m unittest discover -s scripts/experimentos/competencia_contextual -p 'test_*.py' -v
Ran 23 tests in 0.149s
OK
```

Incluyen:
- Preservar exactamente orden para intención histórica, identificador y genérica.
- No inventar vigencia sin metadatos.
- Conflictos explícitos, sin borrar candidatos.
- Retornar `retrieval_gap` si el vigente no fue recuperado.
- Promover desde puesto 7 cuando se entrega el pool completo al selector.
- 100 lecturas repetidas sin escrituras al ledger.
- Cadenas, regreso a un valor anterior, actualización parcial de otro atributo.
- Sustitución futura no efectiva prematuramente; sucesor expirado no resucita al anterior.
- Rechazar ciclos, extremos ausentes, cruce de alcances, intervalos inválidos y valores no finitos.
- Confirmación falsa por defecto: guardar no acredita automáticamente verdad.
- Rechazar inicialización accidental del ledger sobre un córtex.
- Invariancia exacta con 10.000 afirmaciones de contextos distintos; también con 100 candidatos ajenos de score alto, conservando la proyección del orden original.

### Dataset sintético controlado

Semilla 42, 100 contextos repartidos en cinco dominios (releases, configuraciones, decisiones, direcciones y procedimientos). Se construyeron deliberadamente distractores antiguos de mayor score y relaciones de sustitución explícitas. No es una muestra aleatoria de consultas reales ni un entrenamiento.

```text
cases: 100
before_current_at_1: 0
after_current_at_1: 100
history_passthrough: 100
identifier_passthrough: 100
conflicts_detected: 100
neighbors_preserved: 100
```

`Current@1` sobre estos fixtures pasa de 0/100 a 100/100; era un escenario adversarial diseñado para verificar el mecanismo, no una mejora estimada en producción. Passthrough demuestra no interferencia, NO que una consulta histórica arbitraria se interprete o se responda correctamente.

### Búsqueda nueva con el motor real sobre el snapshot suministrado

No solo replay: `ensayo_motor.py` cargó una copia aislada del código, ejecutó `_recordar_impl` y pasó los cinco resultados al selector externo. El campeón real se cargó en ambas variantes, con huella `5721b3821c3521e6`.

| Estado del obsoleto en la copia | Ganador MCP antes | Ganador del selector después | Candidatos conservados |
|---|---|---|---:|
| Activo como en el snapshot | ultima_version_biorag (0.9586) | version_actual_biorag (score base 0.8522) | 5/5 |
| Dormido en el ensayo | Histórico v32.4 (0.7746) | version_actual_biorag (score base 0.7208) | 5/5 |

Se añadieron **explícitamente** las afirmaciones y las dos relaciones de sustitución al ledger de ensayo basándose en el caso revisado. El motor no las descubrió ni las aprendió. Es una prueba de búsqueda real + selección lateral con evidencia suministrada, no una solución automática ya conectada al MCP.

La selección contextual no finge que la similitud cambió: mantiene el score original junto al resultado, por eso el score base puede ser menor que el del segundo. Una integración futura debe separar `score_base` y decisión contextual, revisar calibración y no volver a ordenar ciegamente por score base después de esta decisión.

También se conserva un replay independiente de los rankings anteriores, claramente marcado como replay.

## Protección del original

- DB recibida: SHA-256 `07a77c801eaa56750627e1c831de91a65e6448da25e4803b86d3ae4e2446c55e`.
- Se descargó de nuevo el mismo archivo, se comprobó el hash y se abrió en solo lectura para `sqlite3.backup()` a temporales.
- Quick check: `ok`.
- Hash original idéntico antes/después.
- DBs, archivo comprimido y entorno en `/tmp`; no se añaden a Git.
- Sin cambios en `core/`, `VERSION`, pesos productivos ni DB viva para esta tarea; no hay commit, push ni publicación.

## Qué está hecho y qué sigue pendiente

**Hecho:** modelo de afirmaciones parciales, fuente declarada y confirmación explícita; sustituciones dirigidas con alcance; decisión contextual reproducible; incertidumbre y hueco de recuperación; pruebas de conservación y crecimiento; ensayo del incidente con búsqueda real y evidencia añadida al laboratorio.

**Pendiente antes de integrar:**
1. Diseño de herramientas de confirmación/corrección para que el agente suministre evidencia sin editar SQL. Fuentes declaradas no son fuentes verificadas automáticamente.
2. Resolver entidad, atributo, alcance, intención y tiempo desde interacción real; hoy son entradas estructuradas explícitas. No usar solo coincidencias de palabras como “actual”.
3. Manejar revocación de una corrección, evidencia de distintas autoridades, incertidumbre temporal y atributos multivalorados. Este prototipo admite SOLO atributos monovalorados por contexto.
4. Evaluación emparejada de los 921 casos oficiales y demás gates sobre copias; aún NO ejecutada en esta fase. No se afirma cero regresiones del motor integrado.
5. Probar más consultas reales con anotación independiente; no limitarse a relaciones construidas para este incidente.
6. Evaluar rescate del vigente fuera del pool: hoy devuelve `retrieval_gap` en vez de inventarlo; no lo recupera por sí solo.
7. Después, comparar con la neurona: si se necesitan señales nuevas, entrenamiento/guardia por contexto y versión de modelo propia. No saltarse los guardianes actuales.

## Interpretación

Esto prueba que podemos separar accesibilidad, similitud y aplicabilidad sin destruir el historial. No prueba que el sistema sea un organismo, que la inhibición biológica funcione exactamente así, ni que sea una capacidad exclusiva frente a otras memorias. El próximo hito es convertir evidencia explícita en un flujo de correcciones útil y evaluarlo de extremo a extremo antes de integrar.
