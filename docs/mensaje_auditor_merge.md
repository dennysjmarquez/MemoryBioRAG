# Mensaje para el auditor — solicitud de autorización de merge

Copia y pega este texto. Está escrito para que él pueda responder con un sí o
un no, sin tener que investigar nada.

---

**Asunto: cierre de los tres huecos de `59ef8a4` — solicitud de autorización para merge a `master`**

Hola. Retomé sus observaciones sobre `59ef8a4` y las cerré. Le resumo qué
cambió, qué medí y qué le pido.

**Su objeción fue la que fijó el diseño.** Usted escribió: *"no mover ni borrar
el WAL no garantiza que no pueda dañar la base: SQLite podría aplicarlo al
abrirla"*. Tenía razón y `59ef8a4` estaba incompleto: evitaba **producir** el
WAL huérfano, pero si ya existía, se aplicaba igual.

El commit `97b43c0` cambia el criterio: **la protección es no abrir**. La
decisión se toma antes de `sqlite3.connect`, leyendo solo las cabeceras de los
archivos. Si no hay prueba de que el `-wal` pertenece al `.db` que tiene al
lado, el motor no abre. Nunca mueve, renombra ni borra nada.

**Los tres escenarios que usted pidió, medidos:**

| Escenario | Resultado |
|---|---|
| Caída del proceso | Deja abrir y **recupera**: el `-wal` es de esa misma base y contiene commits propios sin consolidar. Rechazarlo sería perder datos. Probado con `subprocess` + `kill()`, no con `close()`. |
| Agente abierto al cambiar de rama | **Rechazado.** Principal intacto, `-wal` sin mover, constancia con sha256 en `.biorag-pair-state.conflicto.json`. |
| Consolidación que no se puede completar | El cierre **no rompe**; se registra y se cierra. |

**Cómo decide, sin abrir SQLite.** (1) ¿Hay `-wal` con datos? Si no, abre.
(2) ¿El journal mode de la cabecera es WAL? Se lee el byte 18. (3) ¿El sha256
del principal coincide con el anotado en el último commit propio? Entonces el
diario nuevo solo puede venir de escritura externa legítima. (4) Cualquier otro
caso: no se puede probar pertenencia, se rechaza.

**El coste, y por qué lo acepto.** Probé cuatro señales para separar un
checkpoint externo legítimo de una sustitución y ninguna funciona:
`quick_check` (un diario ajeno lo pasa), sal de cabecera (identifica al diario,
no a la base), `size`+`mtime_ns`+`ctime_ns` (no identifican contenido), y
sha256 estricto (rechaza también mantenimiento legítimo). Ante un principal que
cambió con un diario vivo, no adivino: pido confirmación. **Tres pruebas
existentes ahora necesitan `BIORAG_SQLITE_FORCE_OPEN=1`** porque su política es
precisamente rechazar un checkpoint externo. Es el precio de fallar cerrado, y
es deliberado.

**Vías de escape, documentadas.** `BIORAG_SQLITE_GUARD=0` apaga la capa entera.
`BIORAG_SQLITE_FORCE_OPEN=1` autoriza una apertura concreta con aviso y
constancia. Ambas están en `.env.example`, en el README (con el default `1`
explícito) y en `docs/sqlite_par_no_verificado.md`. Hay una prueba
(`test_la_proteccion_viene_activada_por_defecto`) que falla si alguien cambia
el default a apagado.

**Documentación que faltaba.** `docs/sqlite_par_no_verificado.md` estaba
referenciado por el mensaje de error y no existía. Ya está.

**Estado de las pruebas.** `test_sqlite_generation.py` 30/30;
`test_sqlite_runtime.py` + generación + hilos 55/55; suite completa **729
passed, 7 failed, 89 errors**, todos preexistentes y por dependencias ausentes
en mi entorno (`test_memory_core`, `test_qa_multilingue_e3a`,
`test_escala_motor`, `test_evidence_convergence`,
`test_sustantivos_clave_recordar`). CI en GitHub: **5/5 verde** en macOS,
Ubuntu, Windows, Python 3.11 y 3.12.

**Dos cosas que declaro y no escondo:**

1. Hubo un fallo intermitente de `test_alteracion_directa_del_wal_se_detecta`
   en una ejecución completa. No reprodujo en aislamiento, ni en dos mitades de
   la suite, ni en tres ejecuciones completas posteriores. Lo declaro **no
   explicado**, no resuelto.
2. **La causa de fondo sigue ahí**: la base está versionada en git. Mientras lo
   esté, cada cambio de rama puede sustituirla. Esto detecta el problema, no lo
   evita. Sacar la base del repositorio es decisión de Dennys, no mía.

**Lo que le pido.** Autorización para mergear `97b43c0` a `master`, o los
reparos concretos que vea. Tres preguntas para usted:

1. ¿Acepta el coste de fallar cerrado cuando un checkpoint externo legítimo
   cambia el principal?
2. ¿`FORCE_OPEN` le parece vía de escape suficiente, o preferiría una
   confirmación interactiva?
3. ¿Recomienda sacar la base del control de versiones como paso siguiente?

El informe completo está en `docs/informe_auditora_97b43c0.md` dentro de la
rama. No he tocado `master`, ni la base real, ni he mergeado nada.

Gracias.

---

## Nota para Dennys (no enviar)

Si él pide algo concreto, se hace y se le responde. **No mergear sin su
respuesta y sin tu palabra explícita**, que es lo que quedó acordado.
