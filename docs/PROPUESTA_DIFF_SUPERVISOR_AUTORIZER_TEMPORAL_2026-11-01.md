# Diff de integración preparado: instrumentación y supervisor del arnés temporal

Fecha: 2026-11-01. Solo para revisión del auditor. El runner temporal citado en el registro previo (`/tmp/biorag_fk_smallcheck_runner.py`) no está presente en el workspace, por lo que no se pudo modificar ese archivo externo ni afirmar que el diff esté aplicado allí. En su lugar, el flujo parent/worker está integrado y probado en `tests/test_authorizer_supervisor_subprocess_synthetic.py`, con SQLite `:memory:` y objetos sintéticos. Este cambio no se aplica al motor ni a bases reales.

## Integración propuesta al worker

Los helpers están en `scripts/authorizer_supervisor.py`; el flujo de subprocess con authorizer SQLite está probado en `tests/test_authorizer_supervisor_subprocess_synthetic.py`. El hunk del worker sigue siendo un diff de adaptación porque no se encontró el archivo temporal original para cotejar nombres y ciclo de vida. El evento no contiene SQL, argumentos del authorizer, valores, locales, filas ni texto de consulta. El flujo integrado de prueba sí crea rutas nuevas y vincula el resultado con el par `run_id`/`worker_id`.

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

El padre debe reemplazar el `subprocess.run()` bloqueante por `Popen` más un pipe de eventos. `allocate_execution_paths(evidence_root)` crea un directorio privado nuevo por ejecución con UUID, un identificador único de worker, y rutas únicas para eventos primarios/fallback y resultado. `evidence_root` debe ser modo `0700`; cada worker recibe solo sus propias rutas e identificadores. El worker escribe el sobre privado con `write_private_result_exclusive(path, run_id, worker_id)` y `O_EXCL`, modo `0600` y `fsync`.

```diff
@@ call(cid, condition)
- cp = subprocess.run(command, input=payload, capture_output=True, ...)
+ paths = allocate_execution_paths(evidence_root)  # no reutilizar rutas
+ event_r, event_w = os.pipe()
+ child_env = {**env,
+     "BIORAG_GUARD_EVENT_FD": str(event_w),
+     "BIORAG_GUARD_EVENT_PATH": paths["worker_event_path"],
+     "BIORAG_PRIVATE_RESULT_PATH": paths["private_result_path"],
+     "BIORAG_RUN_ID": paths["run_id"],
+     "BIORAG_WORKER_ID": paths["worker_id"]}
+ proc = subprocess.Popen(command, stdin=subprocess.PIPE,
+                         stdout=private_stdout, stderr=private_stderr,
+                         env=child_env, pass_fds=(event_w,))
+ os.close(event_w)
+ proc.stdin.write(payload)
+ proc.stdin.close()
+ outcome = supervise_subprocess(
+     proc, event_r, paths["worker_event_path"],
+     paths["primary_event_path"], paths["fallback_event_path"],
+     paths["private_result_path"], paths["run_id"], paths["worker_id"],
+     timeout=WORKER_TIMEOUT, grace=1.0)
+ os.close(event_r)
+ if outcome["status"] != "worker_exit" or outcome["returncode"] != 0:
+     return aborted_record(reason=outcome["status"],
+                           evidence=outcome["event_saved_to"], retry=False)
+ return read_private_result_record(paths["private_result_path"])
@@ worker, solo tras resultado válido
+ write_private_result_exclusive(
+     os.environ["BIORAG_PRIVATE_RESULT_PATH"],
+     os.environ["BIORAG_RUN_ID"], os.environ["BIORAG_WORKER_ID"])
@@ bucle de condiciones
- if failed: continue_or_retry()
+ if status != "ok":
+     break  # no iniciar otro worker ni reintentar automáticamente
```

El pipe entrega como máximo el primer evento sanitizado. Si `select` no marca datos pero `poll` observa la salida, el helper drena el pipe en modo no bloqueante antes de clasificar la salida; un evento ya encolado, incluso con código 0, impide aceptar limpieza. Un cierre normal solo es `worker_exit` cuando el canal llega a EOF sin bytes/evento, el código es 0, no existe evidencia local de guardia y el archivo privado de resultado es regular, no público, JSON y contiene `status: ok` junto con los `run_id` y `worker_id` esperados. Una ruta nueva por ejecución impide reutilización accidental; la comparación de ambos identificadores rechaza incluso un archivo antiguo o de otro worker colocado en la ruta. EOF con mensaje parcial, cierre prematuro, salida no-cero, evento o resultado ausente/inválido aborta el lote. Si el guardado primario falla, el padre intenta el respaldo; si ambos fallan, marca evidencia incompleta, sin iniciar otro. Si falla IPC, el padre comprueba el evento local y aborta. Los fallos de escritura, comunicación, timeout o guardia nunca se convierten en una corrida `ok`.

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
Supervisor normal EOF: accepted only with private status=ok and matching run_id/worker_id
Supervisor stale/foreign result: old-run and other-worker records rejected; execution paths unique
Supervisor partial IPC frame: rejected; IPC loss recovers worker evidence; primary-save failure uses fallback
5 diagnostic tests + 8 subprocess tests — OK
```

La creación de una vista TEMP sí generó acciones de catálogo TEMP en este SQLite sintético; resolverla no. Es una observación, **no una atribución** de los eventos `main` del intento anterior. La prueba de allowlist admite solo las formas exactas descritas y deniega cinco PRAGMA adicionales. Las pruebas de fallos confirman que el evento llega a respaldo o se marca el fallo, el worker se detiene y el segundo worker no se inicia. No se afirma latencia instantánea.

No se repitieron búsquedas reales ni se abrió o modificó ninguna base del proyecto. E1 sigue abierto; W pendiente.
