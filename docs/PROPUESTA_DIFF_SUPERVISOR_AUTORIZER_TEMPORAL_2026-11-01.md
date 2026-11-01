# Propuesta de diff: instrumentación y supervisor del arnés temporal

Fecha: 2026-11-01. Solo para revisión del auditor. El arnés temporal no se ejecutó contra una búsqueda real y este diff no se aplicó al motor ni a las bases. Las pruebas se hicieron exclusivamente con SQLite `:memory:` y objetos sintéticos.

## Integración propuesta al worker

Los helpers ejecutables del supervisor están en `scripts/authorizer_supervisor.py`; la prueba de contrato sintético del authorizer y allowlist está en `tests/test_sqlite_authorizer_diagnostic_synthetic.py`, y las pruebas subprocess ejecutables están en `tests/test_authorizer_supervisor_subprocess_synthetic.py`. El hunk siguiente es un diff de diseño para adaptar el worker temporal: no es aplicable literalmente hasta cotejar nombres, ciclo de vida y control de errores con el arnés temporal. No se ha aplicado. El registro no contiene SQL, argumentos del authorizer, valores, locales, filas ni texto de consulta.

```diff
@@ antes de instalar el authorizer
+ phase = {"name": "pre_search"}  # solo etiquetas fijas del arnés
+ first_violation_sent = False
+ event_fd = int(os.environ["BIORAG_GUARD_EVENT_FD"])
+ worker_event_path = os.environ["BIORAG_GUARD_EVENT_PATH"]
+
+ def record_first_guard_event(action_name, database):
+     nonlocal first_violation_sent
+     if first_violation_sent:
+         return
+     first_violation_sent = True
+     event = {
+         "phase": phase["name"],
+         "action": action_name,
+         "database": db_class(database),
+         "frames": safe_call_frames(),  # basename/function/line; sin locals
+     }
+     try:
+         persist_exclusive_0600_fsync(worker_event_path, event)
+         event["worker_event_saved"] = True
+     except OSError:
+         event["worker_event_saved"] = False
+     try:
+         write_bounded_json_line(event_fd, event)
+     except OSError:
+         # El evento local se intentó guardar antes. Si falla IPC, terminar;
+         # el padre lo detecta por salida no-cero y nunca avanza al siguiente.
+         os._exit(GUARD_CHANNEL_FAILURE)
+
  def auth(action, a1, a2, db, source):
      name = action_names.get(action)
      is_pragma = action == sqlite3.SQLITE_PRAGMA
-     metadata_read = is_pragma and a1 == "table_info" and ...
+     metadata_read = (
+         is_pragma and (
+             (a1 == "database_list" and a2 is None and db is None and source is None)
+             or (a1 == "table_info" and db == "main"
+                 and a2 in REL_TABLES and source is None)
+         )
+     )
      if name:
-         attempts.append({"action": name, "arg1": a1, "arg2": a2, ...})
+         attempts.append({"action": name, "phase": phase["name"],
+                          "database": db_class(db), "frames": safe_call_frames()})
+         record_first_guard_event(name, db)
          return sqlite3.SQLITE_DENY
      if is_pragma and not metadata_read:
-         blocked_pragmas.append({"arg1": a1, "arg2": a2, ...})
+         blocked_pragmas.append({"action": "SQLITE_PRAGMA_NOT_ALLOWLISTED",
+                                 "phase": phase["name"],
+                                 "database": db_class(db), "frames": safe_call_frames()})
+         record_first_guard_event("SQLITE_PRAGMA_NOT_ALLOWLISTED", db)
          return sqlite3.SQLITE_DENY
      return sqlite3.SQLITE_OK
@@ antes de buscar_por_frase
+ phase["name"] = "search_call"
  results, total = engine.buscar_por_frase(...)
@@ antes de la verificación posterior
+ phase["name"] = "post_search_check"
  after_sig = data_sig(engine.conn)
```

La allowlist queda limitada a `database_list` sin argumento y `main.table_info` para tablas enumeradas. No abre permisos generales a PRAGMA ni modifica la lista de acciones de escritura bloqueadas.

## Integración propuesta al padre/supervisor

El padre debe reemplazar el `subprocess.run()` bloqueante por `Popen` más un pipe de eventos. El worker recibe el descriptor de escritura y una ruta de evidencia privada única. Se mantiene un worker por búsqueda y el lote solo continúa con salida limpia, resultado `ok` y ausencia de evento de guardia.

```diff
@@ call(cid, condition)
- cp = subprocess.run(command, input=payload, capture_output=True, ...)
+ event_r, event_w = os.pipe()
+ child_env = {**env, "BIORAG_GUARD_EVENT_FD": str(event_w),
+              "BIORAG_GUARD_EVENT_PATH": worker_event_path}
+ proc = subprocess.Popen(command, stdin=subprocess.PIPE,
+                         stdout=private_stdout, stderr=private_stderr,
+                         env=child_env, pass_fds=(event_w,))
+ os.close(event_w)
+ proc.stdin.write(payload)
+ proc.stdin.close()
+ outcome = supervise_subprocess(
+     proc, event_r, worker_event_path, primary_event_path,
+     fallback_event_path, private_result_path,
+     timeout=WORKER_TIMEOUT, grace=1.0)
+ os.close(event_r)
+ if outcome["status"] != "worker_exit" or outcome["returncode"] != 0:
+     # El helper persiste el evento primario/respaldo o recupera el archivo
+     # local tras EOF. Verificar stopped=true y clasificar; nunca seguir lote.
+     return aborted_record(reason=outcome["status"],
+                           evidence=outcome["event_saved_to"], retry=False)
+ result = read_private_result_record()
+ if result.status != "ok":
+     return aborted_record(reason="worker_result_not_ok", retry=False)
+ return result
@@ bucle de condiciones
- if failed: continue_or_retry()
+ if status != "ok":
+     break  # no iniciar otro worker ni reintentar automáticamente
```

El pipe entrega como máximo el primer evento sanitizado. Si `select` no marca datos pero `poll` observa la salida, el helper drena el pipe en modo no bloqueante antes de clasificar la salida; un evento ya encolado, incluso con código 0, impide aceptar limpieza. Un cierre normal solo es `worker_exit` cuando el canal llega a EOF sin bytes/evento, el código es 0, no existe evidencia local de guardia y el archivo privado de resultado es regular, no público, JSON y contiene `status: ok`. EOF con mensaje parcial, cierre prematuro, salida no-cero, evento o resultado ausente/inválido aborta el lote. Si el guardado primario falla, el padre intenta el respaldo; si ambos fallan, marca evidencia incompleta, sin iniciar otro. Si falla IPC, el padre comprueba el evento local y aborta. Los fallos de escritura, comunicación, timeout o guardia nunca se convierten en una corrida `ok`.

**Límite temporal:** esta secuencia no garantiza interrupción instantánea. Hay un intervalo por serialización, IPC, almacenamiento/fsync, scheduling y entrega de la señal; el método puede seguir ejecutando código hasta que el supervisor actúe. La garantía propuesta es que no se inicia otro worker y que se espera la salida del anterior antes de abandonar el lote.

## Resultados de las pruebas SQLite sintéticas

Ejecutadas con Python 3.11.2 / SQLite 3.40.1: **5 pruebas, OK**.

```text
TEMP view create/resolve: CREATE_TEMP_VIEW=1; catalog DML on temp during create: INSERT=1, UPDATE=5; catalog DML during resolve=0
Strict PRAGMA allowlist: allowed database_list + listed main.table_info; denied other PRAGMA forms=5
Supervisor normal: event saved before termination; workers_started=1; next_worker_started=false
Supervisor IPC failure: worker event preserved; worker stopped; workers_started=1; next_worker_started=false
Supervisor primary-save failure: fallback event saved; worker stopped; workers_started=1; next_worker_started=false
Supervisor exit race: 110 pending event bytes drained after select miss; clean exit rejected
Supervisor normal EOF: accepted only with private status=ok result; invalid result rejected
Supervisor partial IPC frame: rejected; IPC loss recovers worker evidence; primary-save failure uses fallback
5 diagnostic tests + 7 subprocess tests — OK
```

La creación de una vista TEMP sí generó acciones de catálogo TEMP en este SQLite sintético; resolverla no. Es una observación, **no una atribución** de los eventos `main` del intento anterior. La prueba de allowlist admite solo las formas exactas descritas y deniega cinco PRAGMA adicionales. Las pruebas de fallos confirman que el evento llega a respaldo o se marca el fallo, el worker se detiene y el segundo worker no se inicia. No se afirma latencia instantánea.

No se repitieron búsquedas reales ni se abrió o modificó ninguna base del proyecto. E1 sigue abierto; W pendiente.
