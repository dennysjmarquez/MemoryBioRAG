# Arnés FK: diff sanitizado del authorizer y prueba aislada

Fecha: 2026-11-01. Alcance: documentación del arnés temporal; no cambia el motor, bases ni datos. No se reanudaron búsquedas. El parche que sigue contiene solo código del arnés; no incluye consultas, resultados, recuerdos ni identificadores de casos reales.

## Contrato de autorización

- Se permite únicamente `SQLITE_PRAGMA` con `arg1=table_info`, `database=main`, `arg2` perteneciente a la lista fija `REL_TABLES` y `trigger=None`. Es una lectura del esquema de una tabla; no escribe filas ni cambia estado.
- Todo otro `PRAGMA` se deniega y se registra en `blocked_pragmas`; no se presume que un PRAGMA desconocido sea de solo lectura.
- Las acciones de escritura enumeradas en el arnés se registran en `attempts` antes de devolver `SQLITE_DENY`. El callback no depende de que el motor propague la excepción: si el motor la captura, la entrada permanece y el control posterior invalida el resultado. `PRAGMA query_only=ON` sigue habilitado como defensa adicional.

### Acciones de escritura bloqueadas

El callback deniega estos códigos sin importar si `database` es `main` o `temp`, y registra la base indicada por SQLite:

- `SQLITE_INSERT`, `SQLITE_UPDATE`, `SQLITE_DELETE`.
- DDL principal: `SQLITE_CREATE_INDEX`, `SQLITE_CREATE_TABLE`, `SQLITE_CREATE_TRIGGER`, `SQLITE_CREATE_VIEW`, y sus pares `SQLITE_DROP_*`.
- DDL temporal: `SQLITE_CREATE_TEMP_INDEX`, `SQLITE_CREATE_TEMP_TABLE`, `SQLITE_CREATE_TEMP_TRIGGER`, `SQLITE_CREATE_TEMP_VIEW`, y sus pares `SQLITE_DROP_TEMP_*`.
- `SQLITE_ALTER_TABLE`, `SQLITE_REINDEX`, `SQLITE_ANALYZE`, `SQLITE_ATTACH`, `SQLITE_DETACH`, `SQLITE_TRANSACTION`, `SQLITE_SAVEPOINT`, `SQLITE_CREATE_VTABLE`, `SQLITE_DROP_VTABLE`.

Además, cualquier PRAGMA fuera de la única lectura de metadatos permitida se deniega, incluidos PRAGMA que cambian estado como `foreign_keys=ON` o `journal_mode=WAL`.

## Prueba del authorizer

Prueba aislada con `sqlite3.connect(':memory:')` y tablas sintéticas, no con el volcado ni con datos del proyecto. El test hizo que el llamador capturara las excepciones de los `INSERT`; aun así, el callback registró los dos intentos antes de denegarlos. También verificó que ambas tablas conservaran una fila y que las PRAGMA no autorizadas fueran denegadas. La prueba ejercitó DML en `main` y `temp`; la lista completa de códigos bloqueados que sigue se deriva de `write_names` del arnés, no de una prueba individual de cada código.

Salida:

```json
{"allowed": "PRAGMA main.table_info on REL_TABLES only", "blocked_unapproved_pragmas": ["foreign_keys", "journal_mode", "table_info"], "blocked_write_actions": ["SQLITE_INSERT on main", "SQLITE_INSERT on temp"], "database": "synthetic :memory: only", "main_rows_unchanged": true, "result": "PASS", "searches_run": 0, "temp_rows_unchanged": true, "write_attempts_logged_after_application_caught_denial": 2}
```

Compilación del arnés temporal: `py_compile=PASS`. No se ejecutó el motor ni se abrió una base del proyecto.

## Diff completo sanitizado

```diff
--- a/fk_smallcheck_runner.py
+++ b/fk_smallcheck_runner.py
@@ -104,10 +104,15 @@
   before_sig=data_sig(engine.conn);before_changes=engine.conn.total_changes;attempts=[]
   write_names=('SQLITE_INSERT','SQLITE_UPDATE','SQLITE_DELETE','SQLITE_CREATE_INDEX','SQLITE_CREATE_TABLE','SQLITE_CREATE_TEMP_INDEX','SQLITE_CREATE_TEMP_TABLE','SQLITE_CREATE_TEMP_TRIGGER','SQLITE_CREATE_TEMP_VIEW','SQLITE_CREATE_TRIGGER','SQLITE_CREATE_VIEW','SQLITE_DROP_INDEX','SQLITE_DROP_TABLE','SQLITE_DROP_TEMP_INDEX','SQLITE_DROP_TEMP_TABLE','SQLITE_DROP_TEMP_TRIGGER','SQLITE_DROP_TEMP_VIEW','SQLITE_DROP_TRIGGER','SQLITE_DROP_VIEW','SQLITE_ALTER_TABLE','SQLITE_REINDEX','SQLITE_ANALYZE','SQLITE_ATTACH','SQLITE_DETACH','SQLITE_TRANSACTION','SQLITE_SAVEPOINT','SQLITE_CREATE_VTABLE','SQLITE_DROP_VTABLE')
   action_names={getattr(sqlite3,n):n for n in write_names if hasattr(sqlite3,n)}
+  blocked_pragmas=[]
   def auth(action,a1,a2,db,trigger):
-   name=action_names.get(action);pragma_write=(action==getattr(sqlite3,'SQLITE_PRAGMA',-1) and (a2 is not None or str(a1).lower() in {'journal_mode','foreign_keys','query_only','writable_schema','synchronous','locking_mode','wal_checkpoint','user_version','application_id'}))
-   if name or pragma_write:
-    attempts.append({'action':name or 'SQLITE_PRAGMA_WRITE','arg1':a1,'arg2':a2,'database':db,'trigger':trigger});return sqlite3.SQLITE_DENY
+   name=action_names.get(action)
+   is_pragma=(action==getattr(sqlite3,'SQLITE_PRAGMA',-1))
+   metadata_read=(is_pragma and str(a1).lower()=='table_info' and db=='main' and a2 in REL_TABLES and trigger is None)
+   if name:
+    attempts.append({'action':name,'arg1':a1,'arg2':a2,'database':db,'trigger':trigger});return sqlite3.SQLITE_DENY
+   if is_pragma and not metadata_read:
+    blocked_pragmas.append({'action':'SQLITE_PRAGMA_NOT_ALLOWLISTED','arg1':a1,'arg2':a2,'database':db,'trigger':trigger});return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK
   engine.conn.execute('PRAGMA query_only=ON');engine.conn.set_authorizer(auth)
   effenv={k:os.environ.get(k) for k in ('BIORAG_NEURONA','BIORAG_NEURONA_ASOCIATIVA','BIORAG_NO_LOG','BIORAG_DMN_SINTESIS_ACTIVA','BIORAG_EPISODIO_TEMPORAL','BIORAG_ANALOGIA_DETECTAR','BIORAG_MULTIHOP_EXPANSION','BIORAG_HUB_ENABLED','PYTHONHASHSEED')}
@@ -117,14 +122,29 @@
   try:
    results,total=engine.buscar_por_frase(query,profundidad='activos',pagina=1,limite=5,categoria=None,preview_chars=1,historial_fallos=None,context_window=0,dimensiones_dict=None,dimensiones_ids=None,parafrasis_list=None,desde_ts=None,hasta_ts=None,modo_estricto=False,usar_inferencia=True,buscar_por_rol=None,ignore_peso_sinaptico=True,ordenar_por='relevancia',permitir_expansion_empate=False,expandir_episodio=False,analogia=False,sustantivos_clave_boost=None,convergencia_limite=None)
   except BaseException as exc:
-   r.update(status='search_error',exception_type=type(exc).__name__,exception_text=str(exc)[:1000],traceback=traceback.format_exc()[-5000:],write_attempts=attempts);return r
-  after_sig=data_sig(engine.conn)
-  if attempts:r.update(status='guard_write_attempt',write_attempts=attempts);return r
-  if engine.conn.total_changes!=before_changes:r.update(status='guard_changes_counter',before_changes=before_changes,after_changes=engine.conn.total_changes);return r
-  if after_sig!=before_sig:r.update(status='guard_data_changed',after_schema_sha256=after_sig[0],after_relation_fingerprints=after_sig[1]);return r
+   r.update(status='search_error',exception_type=type(exc).__name__,exception_text=str(exc)[:1000],traceback=traceback.format_exc()[-5000:],write_attempts=attempts,blocked_pragmas=blocked_pragmas);return r
   top=[{'concept':x[0],'score':float(x[4]),'state':x[3],'origin':engine.last_origen_scores.get(x[0])} for x in results[:5]]
   rank=next((i+1 for i,x in enumerate(results[:5]) if expected and x[0]==expected),0) if expected else None
-  r.update(status='ok',candidate_count=len(results),total=total,top5=top,declared_target_rank=rank,declared_target_validated=False,top5_order_sha256=hashlib.sha256(json.dumps([x['concept'] for x in top],ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),top5_full_sha256=hashlib.sha256(json.dumps(top,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),after_schema_sha256=after_sig[0],after_relation_fingerprints=after_sig[1],write_attempts=[])
+  order_sha=hashlib.sha256(json.dumps([x['concept'] for x in top],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
+  full_sha=hashlib.sha256(json.dumps(top,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
+  checkpoint={'case_id':cid,'condition':cond,'search_returned':True,'candidate_count':len(results),'total':total,'top5':top,'declared_target_rank':rank,'declared_target_validated':False,'top5_order_sha256':order_sha,'top5_full_sha256':full_sha,'before_schema_sha256':before_sig[0],'before_relation_fingerprints':before_sig[1],'changes_before':before_changes,'changes_after_search':engine.conn.total_changes,'write_attempts':attempts,'blocked_pragmas':blocked_pragmas}
+  checkpoint_path=EVID+f'/postsearch_checkpoint_{cid}_{cond}.json'
+  try:
+   fd=os.open(checkpoint_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
+   with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(checkpoint,f,ensure_ascii=False,separators=(',',':'));f.flush();os.fsync(f.fileno())
+   dfd=os.open(EVID,os.O_RDONLY)
+   try:os.fsync(dfd)
+   finally:os.close(dfd)
+  except BaseException as exc:
+   r.update(status='post_search_checkpoint_error',search_returned=True,checkpoint_path=checkpoint_path,exception_type=type(exc).__name__,exception_text=str(exc)[:1000],traceback=traceback.format_exc()[-5000:],top5=top,total=total,write_attempts=attempts,blocked_pragmas=blocked_pragmas);return r
+  try:after_sig=data_sig(engine.conn)
+  except BaseException as exc:
+   r.update(status='post_search_verification_error',search_returned=True,checkpoint_path=checkpoint_path,exception_type=type(exc).__name__,exception_text=str(exc)[:1000],traceback=traceback.format_exc()[-5000:],top5=top,total=total,write_attempts=attempts,blocked_pragmas=blocked_pragmas);return r
+  if attempts:r.update(status='guard_write_attempt',search_returned=True,checkpoint_path=checkpoint_path,top5=top,total=total,write_attempts=attempts,blocked_pragmas=blocked_pragmas);return r
+  if blocked_pragmas:r.update(status='guard_unapproved_pragma',search_returned=True,checkpoint_path=checkpoint_path,top5=top,total=total,write_attempts=attempts,blocked_pragmas=blocked_pragmas);return r
+  if engine.conn.total_changes!=before_changes:r.update(status='guard_changes_counter',search_returned=True,checkpoint_path=checkpoint_path,top5=top,total=total,before_changes=before_changes,after_changes=engine.conn.total_changes);return r
+  if after_sig!=before_sig:r.update(status='guard_data_changed',search_returned=True,checkpoint_path=checkpoint_path,top5=top,total=total,after_schema_sha256=after_sig[0],after_relation_fingerprints=after_sig[1]);return r
+  r.update(status='ok',candidate_count=len(results),total=total,top5=top,declared_target_rank=rank,declared_target_validated=False,top5_order_sha256=order_sha,top5_full_sha256=full_sha,after_schema_sha256=after_sig[0],after_relation_fingerprints=after_sig[1],write_attempts=[],blocked_pragmas=[],checkpoint_path=checkpoint_path)
   return r
  finally:src.close()
```

El checkpoint privado se escribe antes de iniciar la verificación posterior, con creación exclusiva (no sobrescribe evidencia), modo `0600` y `fsync` del archivo y directorio. Si falla esa verificación, el registro privado incluye el estado de error y la ruta al checkpoint; el flujo se detiene y no reintenta ni presenta resultados parciales como conclusiones. Este diff no autoriza reanudar búsquedas: requiere revisión del auditor primero.

E1 sigue abierto; W sigue pendiente.
