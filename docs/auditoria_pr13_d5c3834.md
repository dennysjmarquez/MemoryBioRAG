# Reconstrucción de la auditoría PR #13 sobre `d5c3834`

> **Qué es este documento.** El informe original lo escribió la auditora externa
> en su rama (commit `7609d18`, archivo `docs/auditoria_pr13_d5c3834.md`). No
> estaba en esta rama. A petición suya se reconstruye aquí.
> **Qué es mío y qué es suyo.** Las secciones 1–3 reproducen **su informe**,
> citado: son sus palabras y sus cifras, no mías. Las secciones 4–7 son la
> respuesta y el estado actual de esta rama.
> **Última revisión:** 2026-11-07.

## 1. Su decisión (citada)

> **No fusionar `d5c3834` tal como está.** La optimización acelera el caso sin
> cambios, pero en dos controles sintéticos deja pasar cambios del archivo
> principal que `2818e72` detectaba. Uno es una alteración in-place; el otro, un
> checkpoint raw que no altera el tamaño del archivo principal. Es una regresión
> en la detección pretendida, aparte de la ventana commit/publicación que ya se
> documentó. No demuestra corrupción ni se usaron datos reales.

Precisión suya que hay que conservar: *"Si el usuario decide aceptar la ventana,
eso no equivale a aceptar silenciosamente esta regresión nueva"*. Correcto: son
dos asuntos distintos y no se arreglan con la misma decisión.

## 2. Los dos casos que reprodujo (cifras de su informe)

| Caso | `2818e72` (antes) | `d5c3834` (la optimización) |
|---|---|---|
| Alteración in-place con tamaño e inodo constantes | `SQLiteDatabaseIdentityChangedError` en la lectura siguiente | Devuelve `(1,)` **sin alerta**, en los dos runtimes de prueba |
| Checkpoint raw `PASSIVE` sin cambio de tamaño (`(0, 1, 1)`) | Lanza el error | Devuelve **sin alerta** |

**Su diagnóstico, que es la clave del arreglo:** *"tamaño constante no es
suficiente para aplicar esa política"*. El *fast path* comprobaba solo
`data_version`, época y **tamaño** del principal; retornaba antes de leer la
firma que incluía `mtime`/`ctime` y el encabezado. Un cambio externo del archivo
puede no notificar `data_version` a SQLite.

**Su medición de rendimiento:** WAL sintético de 18.589.472 bytes, 30
`SELECT count(*)` protegidos: `2818e72` **1,628 s**; `d5c3834` **0,010 s**. La
mejora era real; el problema era el precio.

**Sus condiciones de medida, que limitan el alcance** (se recogen para no
exagerar lo probado): árboles aislados, Linux, SQLite 3.40.1 del sistema y
`pysqlite3==0.6.1` (SQLite 3.53.4) inyectado temporalmente. **No es el runtime
real de producción.** Para DELETE forzó el clasificador a 3.45.1 y para WAL a
3.51.3: eso decide la política de journal, no cambia el motor binario. No repitió
la suite completa del candidato; el 813/0 procedía del operador/CI.

Evidencia suya: `auditoria_pr13_d5c3834.tar.gz`, SHA-256
`e154b53a092bb4e037c409f53114d73590245274cc98fe32793448bb7b1e5ed8`.

## 3. La ventana commit/publicación

Ya venía documentada en `d5c3834` y **no es una regresión**: entre el commit de
SQLite y la publicación de la firma, un cliente sin protocolo puede confirmar y
la firma atestigua un estado que ya incluye su escritura. Es una carrera real que
ningún candado cooperativo cierra contra quien no acata el protocolo. **Sigue
abierta** y requiere decisión de diseño, no otro parche.

## 4. Qué se hizo (commit `4747ca8`)

Se acepta el diagnóstico completo. **El *fast path* se retiró.**

La sonda barata pasó a ser **`size + mtime + ctime`**, y se usa solo como
**condición necesaria** para saltar el hash. **Nunca decide sola**: si no
coincide, se ejecuta la firma completa, que es la que decide.

Precisión que se comprobó en el código y corrige una impresión incompleta: la
sonda **no cubre solo el archivo principal, cubre también el `-wal`**
(`_cheap_file_probe`, `core/memory_store.py`). Se amplió a propósito: una
alteración directa dentro del WAL deja intactos todos los campos del principal,
así que una sonda limitada al principal informaba "nada cambió" mientras el WAL
estaba alterado (`auditoría 4747ca8`, ver §6.2).

Su frase —"tamaño constante no es suficiente"— es literalmente el motivo del
cambio de criterio.

**Rendimiento recuperado sin perder detecciones:** 30 lecturas sobre un WAL de
14,7 MB en **0,0105 s**, igual que el *fast path* defectuoso. Su medición fue
1,628 s → 0,010 s; la mejora se conserva.

## 5. Las pruebas, y sus resultados

| Prueba | Qué fija |
|---|---|
| `test_alteracion_in_place_de_tamano_constante_se_detecta` | Caso 1: reescritura con mismo tamaño e inodo, forzando `mtime`; **debe lanzar** `SQLiteDatabaseIdentityChangedError` |
| `test_checkpoint_raw_sin_cambio_de_tamano_se_detecta` | Caso 2: checkpoint `PASSIVE` de cliente sin protocolo con tamaño constante; **debe fallar cerrado** |
| `test_lectura_sin_cambios_no_rehashea_el_wal` | El coste: 30 lecturas sobre WAL > 5 MB en menos de 0,5 s |

Las tres llevan su informe nombrado en el docstring, para que la trazabilidad no
dependa de la memoria de nadie.

**Coste declarado de `test_checkpoint_raw_sin_cambio_de_tamano_se_detecta`:**
lleva `BIORAG_SQLITE_FORCE_OPEN=1` porque su política es **rechazar un checkpoint
externo**, y la capa nueva rechaza antes de llegar a lo que la prueba mide. Es
deliberado: el precio de fallar cerrado.

## 6. Lo que este documento no resuelve

1. **La ventana commit/publicación sigue abierta** (§3). No se ha tocado.
2. **`test_alteracion_directa_del_wal_se_detecta` falló de forma intermitente**
   en una ejecución completa de la suite. No reprodujo en aislamiento, ni en dos
   mitades, ni en tres ejecuciones completas posteriores. **Se declara no
   explicado, no resuelto.** Una prueba intermitente no es una prueba en la que
   se pueda confiar hasta que se explique.
3. **El runtime de producción no está cubierto** por las pruebas de CI, igual que
   señaló ella en §2. La CI usa el SQLite de cada plataforma, no el binario real
   de despliegue.
4. **La decisión de fondo no es técnica y sigue sin tomarse: ¿la base se
   versiona en git?** Todo el blindaje de esta capa existe porque el modelo de
   amenaza es "alguien puede sustituir el principal o el diario por debajo", y
   **eso es exactamente lo que hace `git checkout` al cambiar de rama**. Si la
   base deja de versionarse, buena parte de esta complejidad sobra; mientras se
   versione, la protección es necesaria y está en su forma final. No la puede
   tomar quien escribe el código.

## 7. Revisión independiente sobre `88ef43f` (dos hallazgos, ambos reales)

La revisión independiente encontró dos fallos que las 60 pruebas de SQLite no
cubrían. **Los dos se reprodujeron y se corrigieron.**

### Hallazgo 1 — Un `-wal` ajeno se aceptaba si el principal coincidía

**Causa:** el caso 3 de `_pair_can_be_opened` aceptaba con solo comparar el
sha256 del **principal** con el anotado. Eso descarta que hayan sustituido el
archivo principal, **pero no que el `-wal` sea de otra base**.

**El escenario exacto que lo dispara:** un proceso hace commit y **se cae**. El
principal queda intacto y el registro sigue siendo válido. En ese hueco se
coloca un `-wal` de otra base y se aplicaba en silencio sin alerta.

**Arreglo:** la **sal de la cabecera del `-wal`** identifica al diario y ya
estaba anotada; ahora **participa en la decisión**. Si el principal coincide
pero la sal no es la anotada, ese diario no es el que había cuando se verificó
el par: se rechaza.

**Lo que esto conserva:** tras una caída legítima el diario es el mismo que
había en el último commit propio (misma sal), así que se sigue aceptando y
SQLite recupera los datos. La recuperación tras caída sigue probada y verde.

**Prueba:** `test_wal_ajeno_con_principal_intacto_se_rechaza`. Reproduce una
caída real (`subprocess` + `kill`) y coloca el diario ajeno. **Falla sin el
arreglo, pasa con él** (comprobado con `git stash`).

### Hallazgo 2 — `open_reader` abría el par que `open_writer` rechazaba

**Causa:** la comprobación de pertenencia solo estaba en `open_writer`.
`open_reader` no comprobaba nada.

**Por qué importa:** un lector también abre el par y SQLite aplica el `-wal`
al abrirlo, igual que en escritura. La lectura veía datos de otra versión por
la puerta de al lado, aunque la de escritura estuviera cerrada.

**Arreglo:** `open_reader` aplica la **misma** política, antes de abrir:
`SQLiteSidecarConflictError` con constancia forense, y `FORCE_OPEN` como vía de
escape autorizada.

**Prueba:** `test_open_reader_rechaza_el_mismo_par_que_open_writer`. **Falla sin
el arreglo, pasa con él.**

### Hallazgo 3 — Un `-wal` copiado y modificado conservaba la sal

**Causa:** el arreglo del hallazgo 1 comparaba la **sal de la cabecera**, y la
sal **está en la cabecera**: una copia la conserva. Copiar el `-wal`, modificar
sus datos y dejarlo junto al principal intacto producía **la misma sal**, así
que la comprobación lo aceptaba y `open_reader` mostraba el dato de la copia.

**Por qué el arreglo anterior era insuficiente:** la sal identifica *la
identidad declarada* del diario, no su contenido. Sirve para descartar un
diario generado de cero, pero no uno copiado y reescrito.

**Arreglo:** se anota y se compara también el **sha256 del contenido del
diario** (todo menos la cabecera de 32 bytes). La cabecera se puede copiar; los
frames con datos de otra base no coinciden. Se exige **sal y contenido**.

**Lo que conserva:** tras una caída legítima el diario no cambia, así que su
contenido coincide y SQLite recupera. La prueba de caída sigue verde.

**Coste:** hashear el diario en cada comprobación se evita con el mismo atajo
que ya existía (`size` + `mtime_ns` + `sal` + `contenido` sin cambios → no se
rehashea). La prueba de coste `test_lectura_sin_cambios_no_rehashea_el_wal`
sigue verde.

**Prueba:** `test_wal_copiado_y_modificado_con_la_misma_sal_se_rechaza`.
Comprueba **explícitamente que el ataque conserva la sal** (si no, la prueba no
estaría probando lo que dice) y verifica que tanto `open_writer` como
`open_reader` rechazan. **Falla sin el arreglo, pasa con él.**

### Consecuencia de política que este hallazgo dejó a la vista

El par **no se anota mientras queda un diario vivo**: solo se anota tras el
cierre ordenado (diario vacío) o tras un commit propio. Por eso un segundo
proceso que abre con el diario de otro vivo se rechaza por "par no verificado",
aunque no haya nada malo. Es coherente con fallar cerrado, pero **es una
restricción operativa real** que hay que conocer: dos procesos sobre la misma
base en WAL necesitan autorización explícita del primero en anotar.

### Hallazgo 4 — La ventana entre comprobar y abrir (TOCTOU)

**Causa raíz, y es de diseño, no un descuido:** todas las comprobaciones
anteriores miran el **nombre** del archivo. Comprobar y abrir son dos
operaciones distintas sobre ese nombre, y entre ellas alguien puede poner otro
archivo detrás. **Ninguna cantidad de comprobaciones previas cierra esa
ventana.**

Reproducido con un hook: la comprobación acepta, el `-wal` cambia, y el lector
abre y muestra el dato ajeno.

**Arreglo:** verificar **después** de abrir. Se toma una fotografía del par
(identidad `(st_dev, st_ino)` + tamaño + fecha + sha256 del principal +
contenido del diario) en el mismo momento que la comprobación, y se vuelve a
tomar tras abrir. Si no coinciden, la conexión **no se entrega**.

- **Inodo:** `os.replace()` produce un inodo nuevo. Es lo que hace un
  `git checkout` al cambiar la base versionada. **Git no participa en los
  bloqueos del motor, así que la comprobación no se apoya en ningún bloqueo:**
  se apoya en la identidad del archivo, que el sistema mantiene.
- **Contenido:** una reescritura in situ conserva el inodo. Por eso no basta la
  identidad: se exige también el sha256. Ambas puertas usan la comprobación
  fuerte.
- **En lectura** cerrar es inocuo: no se ha leído nada.
- **En escritura** la conexión se cierra con `wal_autocheckpoint=0` y
  `query_only=ON` para no consolidar en el principal nada de lo aplicado.

**Coste medido, no estimado.** En el camino normal (cierre ordenado, sin
`-wal`) la fotografía **no se toma**, porque sin diario no hay nada que SQLite
pueda aplicar: 100 aperturas sobre una base de 8,9 MB dan **0,857 ms** antes y
**0,868 ms** después (**+11 µs, +1,3%**, y es el `os.stat()` del chequeo de
diario, no hashing). Con `-wal` vivo sí se paga el sha256 del diario, y solo
entonces.

**Pruebas:** `test_ventana_entre_comprobacion_y_apertura_escritura_in_situ`,
`..._renombrado`, `..._lectura` y `test_sin_diario_no_hay_ventana_ni_coste`.
Las cuatro **fallan sin el arreglo, pasan con él**.

### Hallazgo 5 — La ventana seguía abierta cuando no había diario inicial

**Causa, y es un error mío de razonamiento, no un descuido:** para no pagar el
sha256 en el camino normal puse una condición de coste — "si no hay `-wal`, no
se toma fotografía". Esa condición **desactivaba la verificación posterior
justo en la puerta que debía proteger**: no había diario, `_pair_can_be_opened`
aceptaba por ausencia de diario, aparecía un `-wal` ajeno antes de la apertura,
y el lector mostraba su dato.

**La regla correcta no es de coste, es de correspondencia:** la verificación
posterior debe comprobar **exactamente lo que asumió la anterior**.

| Estado al comprobar | Qué asumió la comprobación | Qué debe verificar después |
|---|---|---|
| Sin `-wal` | "no hay diario y el principal es este archivo" | Identidad + tamaño + fecha. Detecta que aparezca un diario o se sustituya el principal. |
| Con `-wal` | "el contenido es este" (sha256) | Identidad + contenido. |

Por eso la fotografía **se toma siempre**, con la profundidad que corresponda
al estado verificado. Si no había diario basta lo superficial; si había, se
rehashéa.

**Pruebas:** `test_ventana_sin_diario_inicial_con_diario_que_aparece`,
`test_ventana_sin_diario_inicial_escritura` y
`test_sin_diario_se_verifica_sin_hashear`. **Las tres fallan sin el arreglo.**

**Coste:** 100 aperturas sobre 8,9 MB sin diario dan ~0,78–0,84 ms antes y
~0,77–0,90 ms después. La diferencia cae dentro del ruido de medida del
entorno; no se paga hashing en el camino normal.

### Una lección sobre mis propios arreglos

Dos de los cinco hallazgos (3 y 5) los introduje **optimizando**. En el 3
comparé la sal porque era barata, y la sal se copia. En el 5 me salté la
verificación para no hashear, y con eso desactivé la protección donde hacía
falta.

La raíz común es la misma: **elegí qué comprobar por su coste en vez de por lo
que la comprobación anterior había asumido**. Eso no se corrige con más
comprobaciones; se corrige con la regla de correspondencia de arriba.

### Escenarios explorados además del reportado

Se probaron antes de que los reportara la revisión. Resultado:

| Escenario | Resultado |
|---|---|
| `-shm` ajeno **sin** `-wal` | Abre y lee el dato correcto: SQLite ignora el `-shm` huérfano. **No es un fallo** (verificado, no supuesto). |
| `-wal` **y** `-shm` ajenos | Rechazo. |
| `-wal` truncado a mitad de cabecera | Rechazo. |
| Principal sin permisos | `OperationalError`, no se toca nada. |
| Principal vía enlace simbólico | Abre correctamente. |
| Dos lectores con `-wal` vivo | Rechazo (ver la restricción operativa de §Hallazgo 3). |
| Sustitución **después** de abrir | La conexión abierta sigue leyendo el inodo viejo: **inmune**. Una apertura nueva abre el principal nuevo, que es correcto. |
| ¿El cierre tras rechazar consolida lo ajeno? | **No.** Comprobado: el principal no cambia durante la apertura rechazada. Cambia al cerrar el dueño legítimo, que es su checkpoint normal, y el resultado es íntegro y sin el dato ajeno. |

Este último párrafo es importante: era mi mayor preocupación del arreglo y la
verifiqué en vez de suponerla.

### Lo que esta revisión demuestra sobre el método

Las 60 pruebas de SQLite pasaban y los dos fallos seguían ahí. La razón es que
las pruebas cubrían los caminos que yo había imaginado. Una revisión
independiente busca los que no imaginé. **Eso no lo sustituye ninguna prueba
propia**, y es el argumento más fuerte que hay para que la revisión exista.

## 8. Estado de la rama

**Ciclo de revisión completo.** Cinco commits revisados, cinco hallazgos, todos
reproducidos y corregidos:

| Revisado | Hallazgo | Corregido en |
|---|---|---|
| `88ef43f` | 1: `-wal` ajeno aceptado con el principal coincidente | `d98a946` |
| `88ef43f` | 2: `open_reader` abría el par que `open_writer` rechazaba | `d98a946` |
| `d98a946` | 3: el `-wal` copiado conservaba la sal | `2b3b11c` |
| `2b3b11c` | 4: ventana TOCTOU entre comprobar y abrir | `3912d68` |
| `3912d68` | 5: la ventana seguía abierta sin diario inicial | `17fbae2` |

Cada corrección va con una prueba que **falla sin ella**: eso se comprobó
revirtiendo el arreglo (`git stash`) en cada caso, no solo viendo la prueba en
verde.

**Dos de los cinco hallazgos (3 y 5) los introdujo el propio autor de la rama
optimizando.** Está documentado en §"Una lección sobre mis propios arreglos"
porque es la parte del proceso que más conviene recordar.

**Regla de diseño que queda vigente, y es la que hay que respetar en cualquier
cambio futuro:**

> La verificación posterior debe comprobar exactamente lo que asumió la
> anterior. Sin diario: identidad + tamaño + fecha. Con diario: identidad +
> contenido.

**Estado operativo:**

- Sin merge a `master` (decisión pendiente de autorización explícita).
- Sin tocar la base real ni sus archivos auxiliares durante toda la revisión.
- PR #13 abierto y fusionable; CI 5/5 verde en la última ejecución.
- La capa vive en `core/sqlite/` (seis módulos) con `core/sqlite_runtime.py` como
  fachada. Cero lógica nueva en esa división: los 54 bloques se movieron
  literalmente y se compararon con el AST (`0 diferencias`).
