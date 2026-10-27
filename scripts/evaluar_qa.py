import sys
import os
import json
import re
import shutil
import sqlite3
import time
import unicodedata
import difflib
from collections import defaultdict
from pathlib import Path

# Add workspace root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG
from core.memory import neurona
import qa_neurona as QN


def _normalizar_token(texto):
    """Normaliza texto para matching de tokens: sin acentos, minúsculas."""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(c)
    ).lower()


def _clave_etiqueta(texto):
    """Clave comparativa de etiqueta oro: sin acentos, minúsculas, solo alfanuméricos.

    Permite resolver etiquetas obsoletas del JSONL cuando un nodo fue renombrado con
    cambios de puntuación (coma -> "_y_", dos puntos, guiones). Los 3 fallos de la
    categoría `literal` del 2026-09-02 eran exactamente esto: el motor devolvía el nodo
    correcto en TOP1 con score 0.935 y el caso se contaba como fallo porque la etiqueta
    apuntaba al nombre viejo, ya inexistente en la DB.
    """
    return re.sub(r'[^a-z0-9]+', '', _normalizar_token(texto))


def _clave_texto(texto):
    """Clave de comparación de TEXTO LIBRE: minúsculas, sin tildes, separadores unidos.

    Distinta de `_clave_etiqueta` (que borra TODO lo no alfanumérico y por tanto no
    sirve para buscar una frase dentro de un campo). Aquí los separadores `_`, `-` y
    los espacios se convierten en un solo espacio, porque el nombre de un nodo usa
    `_` y el alias usa `-` o `,`: `pre-validacion` y `pre_validacion` son lo mismo.
    """
    limpio = re.sub(r'[_,;\s\-]+', ' ', _normalizar_token(texto or ''))
    return limpio.strip()


# ── E1: reglas de la QA honesta (fijadas por el auditor, 2026-10-26) ──────────
# UMBRAL_AMBIGUA_R5 = "más de 5 reclamantes": con 5 o menos TODOS caben en el
# top-5, así que el caso no lo puede fallar el motor por ser ambiguo. Se decidió
# DESPUÉS de ver los resultados de la primera entrega de E1 y se dice así en el
# informe: no es una regla previa, es una decisión consciente de Dennys.
UMBRAL_AMBIGUA_R5 = 5
UMBRAL_AMBIGUA_R1 = 2


def _palabras(texto):
    """Palabras normalizadas completas. `pre-validacion` -> ['pre','validacion']."""
    return [p for p in _clave_texto(texto).split() if p]


def _nodo_declara(concepto, sinonimos, palabras_q):
    """¿Este nodo reclama la consulta? Regla ESTRICTA, sin buscar dentro de palabras.

    Dos formas, y solo dos:
      - ALIAS COMPLETO: un alias del campo `sinonimos` es exactamente la consulta
        (`filtro-arquitecto-prolijo` == `filtro-arquitecto-prolijo`).
      - PALABRA ENTERA EN EL NOMBRE: la consulta aparece como palabras completas y
        seguidas en el nombre del nodo (`perfil` dentro de `dennys_perfil_gustos`).

    POR QUÉ no se usa "contiene": con substring, `agente` reclamaba 119 nodos
    (exacto: 32) porque entraba dentro de `agentes`, `agencia`... y `oracle
    identification` salía ambigua con un solo reclamante real. La regla anterior
    medía parecido de letras, no la palabra.
    """
    if not palabras_q:
        return False
    for alias in re.split(r'[,;|\n]+', sinonimos or ''):
        if _palabras(alias) == palabras_q:
            return True
    palabras_nombre = _palabras((concepto or '').replace('_', ' ').replace('-', ' '))
    n = len(palabras_q)
    if n > len(palabras_nombre):
        return False
    return any(palabras_nombre[i:i + n] == palabras_q for i in range(len(palabras_nombre) - n + 1))


def _mapa_declaraciones(con):
    """{concepto: sinonimos} de una base, para clasificar sin abrir el motor."""
    return {
        concepto: (sinonimos or '')
        for concepto, sinonimos in con.execute(
            "SELECT concepto, COALESCE(sinonimos, '') FROM largo_plazo"
        ).fetchall()
    }


def clasificar_casos_sinonimo(db, cases, ruta_referencia=None):
    """Separa los casos `sinonimo` en OBSOLETOS y AMBIGUOS.

    POR QUÉ existe (etapa E1, decisión de Dennys 2026-10-26): en la base viva, 6 de
    los 7 fallos venían del EXAMEN, no del buscador. Contarlos como fallos del motor
    no mide el motor: mide el dataset.

    REGLAS (las del auditor, aplicadas al pie de la letra):
      1. OBSOLETA — el recuerdo esperado SÍ declaraba la palabra en el snapshot de
         origen y YA NO la declara en la base que se mide. Si se mide el propio
         snapshot, son 0 por construcción.
      2. AMBIGUA — 2 o más recuerdos reclaman la palabra, con la regla estricta de
         `_nodo_declara` (alias completo o palabra entera en el nombre).
      3. Se aparta POR MÉTRICA: para R@5 solo cuentan como ambiguas las de más de
         `UMBRAL_AMBIGUA_R5` reclamantes; para R@1, desde `UMBRAL_AMBIGUA_R1`.
      4. Se calcula en tiempo de QA contra la base medida. `casos_qa.jsonl` no se
         toca.

    `ruta_referencia`: DB del snapshot de origen. Sin ella no se puede afirmar
    "YA NO" y `obsoleta` queda en False (no se inventa).

    Devuelve {case_id: {"obsoleta", "n_reclamantes", "ambigua_r5", "ambigua_r1",
                        "detalle"}}.
    """
    medido = _mapa_declaraciones(db.cursor)
    referencia = {}
    if ruta_referencia:
        try:
            # Solo lectura, e INMUTABLE cuando el fichero está limpio: sin esto
            # SQLite puede crear -wal/-shm al lado del snapshot y cambiarle el
            # sha256. Ya pasó una vez en esta etapa (lo detectó el auditor).
            # PERO immutable=1 hace que SQLite IGNORE un -wal existente: en una
            # base recién escrita (que vive en WAL) se leería vacía. Por eso solo
            # se usa cuando no hay sidecar.
            _modo = "mode=ro"
            if not os.path.exists(str(ruta_referencia) + "-wal"):
                _modo += "&immutable=1"
            con_ref = sqlite3.connect(f"file:{ruta_referencia}?{_modo}", uri=True)
            try:
                referencia = _mapa_declaraciones(con_ref)
            finally:
                con_ref.close()
        except sqlite3.Error:
            referencia = {}

    marcas = {}
    for caso in cases:
        if caso.get("categoria") != "sinonimo":
            continue
        esperado = caso.get("concepto_esperado")
        if not esperado:
            continue
        palabras_q = _palabras(caso.get("query", ""))
        if not palabras_q:
            continue

        # 1) OBSOLETA: declaraba en el origen y ya no declara aquí.
        declaraba_antes = bool(
            referencia and esperado in referencia
            and _nodo_declara(esperado, referencia[esperado], palabras_q)
        )
        declara_ahora = bool(
            esperado in medido and _nodo_declara(esperado, medido[esperado], palabras_q)
        )
        obsoleta = bool(declaraba_antes and not declara_ahora)

        # 2) AMBIGUA: cuántos nodos la reclaman en la base medida.
        n_reclamantes = sum(
            1 for concepto, sinonimos in medido.items()
            if _nodo_declara(concepto, sinonimos, palabras_q)
        )

        # 3) Umbral por métrica.
        ambigua_r5 = n_reclamantes > UMBRAL_AMBIGUA_R5
        ambigua_r1 = n_reclamantes >= UMBRAL_AMBIGUA_R1

        partes = []
        if obsoleta:
            partes.append("el esperado declaraba el alias en el snapshot y ya no en esta base")
        if n_reclamantes:
            partes.append(f"{n_reclamantes} recuerdos reclaman la palabra")
        marcas[caso["id"]] = {
            "obsoleta": obsoleta,
            "n_reclamantes": n_reclamantes,
            "ambigua_r5": ambigua_r5,
            "ambigua_r1": ambigua_r1,
            "detalle": "; ".join(partes) if partes else "",
        }
    return marcas


def _tabla_honesta(registros, metrica="r5"):
    """Agrega por categoría lo que queda al apartar según LA MÉTRICA pedida.

    `metrica` es "r5" o "r1": una pregunta puede contar para el R@5 y no para el
    R@1 (por ejemplo, 4 recuerdos declaran la palabra: todos caben en el top-5,
    pero solo uno puede ser el primero).
    """
    campo_apartado = "apartado_r5" if metrica == "r5" else "apartado_r1"
    por_cat = defaultdict(lambda: {"n": 0, "h5": 0, "h1": 0, "rr": 0.0})
    for reg in registros:
        if reg.get(campo_apartado):
            continue
        m = por_cat[reg["categoria"]]
        m["n"] += 1
        m["h5"] += reg["hit5"]
        m["h1"] += reg["hit1"]
        m["rr"] += reg["rr"]
    return por_cat


def _restaurar_estado_nodos(db, estado_inicial):
    """Restaura `estado` y `peso_sinaptico` de los nodos que el caso anterior modificó.

    Por qué hace falta (hallazgo del 2026-09-02, diagnóstico §4.3):
    el arnés muta la DB caso a caso y esas mutaciones se ACUMULAN:

      - el setup hace `UPDATE largo_plazo SET estado='activo'/'dormido'` sobre el nodo
        esperado de cada caso;
      - `buscar_por_frase(profundidad='profundo')` DESPIERTA nodos dormidos
        (`estado='activo'`, `peso_sinaptico += 0.15`) dentro del motor
        (core/memory_store.py, bloque de paginación profunda).

    Consecuencia: el resultado del caso N depende de los N-1 casos anteriores. En la
    DB viva hay 66 nodos `dormido` y 46 de los 921 casos tienen su nodo esperado en
    ese estado, así que buena parte del corpus se va reactivando de forma irreversible
    a medida que avanza la corrida y el pool de candidatos crece.

    Efecto medido: el caso `typo` 0513 ('denys-identidad-profunda') pasó de PASS a
    FAIL entre dos corridas del MISMO código porque su nodo esperado puntúa 0.1743,
    empatado con otro candidato y justo en el corte del top-5; cualquier cambio de
    estado aguas arriba lo deja dentro o fuera. Eso es ruido del arnés, no señal del
    motor, y con ruido de ±1-2 casos no se puede validar ningún fix.

    El restaurador hace la evaluación independiente del orden: cada caso arranca desde
    el mismo estado de corpus. Coste: un SELECT de ~1k filas + updates puntuales por
    caso, despreciable frente a ~1 s de búsqueda.
    """
    actual = db.cursor.execute(
        "SELECT concepto, estado, peso_sinaptico FROM largo_plazo"
    ).fetchall()
    cambias = []
    for concepto, estado, peso in actual:
        original = estado_inicial.get(concepto)
        if original and (original[0] != estado or original[1] != peso):
            cambias.append((original[0], original[1], concepto))
    if not cambias:
        return 0
    db.cursor.executemany(
        "UPDATE largo_plazo SET estado = ?, peso_sinaptico = ? WHERE concepto = ?",
        cambias,
    )
    db.conn.commit()
    return len(cambias)


def _tokens_corpus(db):
    """Tokens (>=3 chars, normalizados) presentes en el corpus completo.

    Se usa para detectar controles negativos contaminados: si un token de la
    query aparece como palabra en el corpus (concepto + contenido + sinónimos),
    la query dejó de ser "ruido" y pasó a ser una coincidencia léxica legítima.
    Esos controles no miden el gate de ruido y se reportan aparte.
    """
    tokens = set()
    db.cursor.execute(
        "SELECT concepto, COALESCE(contenido, ''), COALESCE(sinonimos, '') FROM largo_plazo"
    )
    for concepto, contenido, sinonimos in db.cursor.fetchall():
        texto = f"{concepto} {contenido} {sinonimos}".replace('_', ' ').replace('-', ' ')
        for w in re.findall(r'\w{3,}', _normalizar_token(texto)):
            tokens.add(w)
    return tokens


def _copiar_base_para_qa(src_db, temp_db):
    """Copia la base que se va a medir SIN tocar el original. (Higiene E2b)

    POR QUÉ existe (hallazgo del auditor, E2b-C): al medir el snapshot, la copia
    se hacía abriendo el original con `mode=ro`, y SQLite, para leer una base en
    WAL, CREA el `-shm` (y a veces el `-wal`) al lado del fichero. Resultado: la
    QA del snapshot dejaba basura junto al snapshot y podía moverle el sha256.

    Cómo se evita:
      * Si no hay `-wal`, se abre con `immutable=1`: SQLite no toca el directorio.
      * Si hay `-wal` (base recién escrita), `immutable=1` IGNORARÍA esas
        transacciones y se copiaría una base vieja; ahí se abre con `mode=ro` y
        se anotan los sidecars que aparezcan para borrarlos después.
      * La copia de trabajo va a un temporal del sistema, no al repo.

    Devuelve {"modo", "sha_antes", "sha_despues", "sidecars_borrados"}.
    """
    import hashlib
    import tempfile

    src_db = str(src_db)
    temp_db = str(temp_db)
    sidecars = [src_db + "-wal", src_db + "-shm"]
    previos = {p: os.path.exists(p) for p in sidecars}

    def _sha(ruta):
        h = hashlib.sha256()
        with open(ruta, "rb") as f:
            for bloque in iter(lambda: f.read(1 << 20), b""):
                h.update(bloque)
        return h.hexdigest()

    sha_antes = _sha(src_db)
    modo = "mode=ro" if previos[src_db + "-wal"] else "mode=ro&immutable=1"
    uri = Path(src_db).expanduser().resolve().as_uri() + "?" + modo

    os.makedirs(os.path.dirname(temp_db) or ".", exist_ok=True)
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(temp_db + ext):
            try:
                os.remove(temp_db + ext)
            except OSError:
                pass

    conn_src = sqlite3.connect(uri, uri=True)
    conn_dst = sqlite3.connect(temp_db)
    try:
        conn_src.backup(conn_dst)
    finally:
        conn_dst.close()
        conn_src.close()

    # Solo se borra lo que ha aparecido por nuestra culpa; lo que ya estaba, se respeta.
    borrados = []
    for p in sidecars:
        if not previos[p] and os.path.exists(p):
            try:
                os.remove(p)
                borrados.append(os.path.basename(p))
            except OSError:
                pass

    return {
        "modo": modo,
        "sha_antes": sha_antes,
        "sha_despues": _sha(src_db),
        "sidecars_borrados": borrados,
    }


def run_evaluation(argv=None):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    args = QN.leer_argumentos(sys.argv[1:] if argv is None else argv)

    # Cargar .env.local automáticamente si existe
    env_local = os.path.join(base_dir, ".env.local")
    if os.path.exists(env_local):
        with open(env_local, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    # No contaminar log_busquedas con consultas del benchmark
    os.environ["BIORAG_NO_LOG"] = "1"

    src_db = os.environ.get('BIORAG_PATH') or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")

    # La copia de trabajo va fuera del repo: la QA no debe dejar ficheros suyos
    # en el árbol de trabajo ni junto a las bases que mide (higiene E2b-C).
    import tempfile as _tempfile
    temp_db = os.environ.get("BIORAG_QA_TEMP_DB") or os.path.join(
        _tempfile.gettempdir(), f"biorag_qa_temp_{os.getpid()}.db"
    )
    cases_filename = args.casos
    cases_file = os.path.join(base_dir, "scripts", cases_filename)
    failed_file = os.environ.get(
        "BIORAG_QA_FAILED_CASES",
        os.path.join(base_dir, "scripts", "casos_fallidos.jsonl"),
    )
    
    if not os.path.exists(cases_file):
        print(f"Error: Test cases file not found at {cases_file}.")
        sys.exit(1)
        
    print(f"Creating isolated database copy at: {temp_db}")
    for ext in ["", "-wal", "-shm"]:
        f = temp_db + ext
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass
    # La fuente es de solo lectura: la copia incluye las transacciones confirmadas
    # del WAL sin ejecutar wal_checkpoint ni escribir en la DB origen.
    info_copia = _copiar_base_para_qa(src_db, temp_db)
    if info_copia["sha_antes"] != info_copia["sha_despues"]:
        print("  [AVISO] la base de origen CAMBIÓ de sha256 al copiarla "
              f"({info_copia['sha_antes'][:12]} -> {info_copia['sha_despues'][:12]})")
    print(f"  origen intacto: sha256 {info_copia['sha_despues'][:12]} ({info_copia['modo']})"
          + (f"; sidecars borrados: {', '.join(info_copia['sidecars_borrados'])}"
             if info_copia["sidecars_borrados"] else ""))
    # Lo que la neurona dejó guardado en la base medida (leído de la copia, sin el motor)
    guardada_origen = QN.leer_guardada(temp_db)


    
    # Load cases
    cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
                
    print(f"Loaded {len(cases)} test cases.")
    
    # Initialize BioRAG against the temp DB copy
    db = SQLiteMemoryBioRAG(db_path=temp_db)

    # ── Neurona de ranking (scripts/qa_neurona.py) ──────────────────────────
    # Cada base tiene su propia neurona. Se dice ANTES de medir qué neurona hay en la
    # base medida y en tu DB viva, y con --con-neurona se entrena una en la copia.
    origen_qa = os.environ.get("BIORAG_QA_ORIGEN") or src_db  # run_qa_suite.sh mide una copia: aquí va la original
    ruta_viva = os.environ.get("BIORAG_QA_DB_VIVA") or os.path.join(base_dir, "MemoryBioRAG_Data", "memory_biorag.db")
    viva, viva_vale = None, False
    if not QN.misma_db(ruta_viva, origen_qa):
        viva = QN.leer_guardada(ruta_viva)  # solo lectura, sin abrir el motor sobre tu DB viva
        if viva and viva.get("campeon"):
            viva_vale = QN.vale_para_este_motor(viva, neurona.VERSION, neurona.huella_motor(db))
    entrenada_aqui = None
    decision_entrenar = None
    if args.con_neurona:
        if not neurona.activa():
            print("[ERROR] --con-neurona con BIORAG_NEURONA=0: la neurona está apagada en este entorno.")
            sys.exit(2)
        if neurona.resumen(db).get("campeon"):
            print("--con-neurona: esta base ya tiene su neurona entrenada; se usa tal cual (no se entrena).")
        else:
            _entrenar, decision_entrenar = QN.quiere_entrenar(
                args.ciclos, args.minutos, neurona._cfg()["presupuesto"], len(cases), auto_si=args.si)
        if decision_entrenar in ("si_flag", "acepto"):
            from despertar_neurona import practicar_seguido
            print(f"\n--con-neurona: entrenando una neurona en la COPIA temporal (hasta {args.ciclos} prácticas"
                  f"{f', tope {args.minutos} min' if args.minutos else ''}). La base original no se toca.")
            print("Es la misma práctica de despertar_neurona: preguntas que la neurona se hace con los")
            print("recuerdos de la base; nunca ve las preguntas de esta QA.")
            _r, _hechos, _seg = practicar_seguido(db, args.ciclos, args.minutos)
            entrenada_aqui = dict(ciclos=_hechos, segundos=round(_seg, 1))
    estado_neurona = neurona.resumen(db)
    neurona_actua = bool(estado_neurona.get("activa") and estado_neurona.get("campeon"))
    aviso_neurona = QN.lineas_aviso(dict(
        activa=neurona.activa(), medida=estado_neurona, entrenada_aqui=entrenada_aqui,
        origen=origen_qa, origen_es_snapshot=QN.es_snapshot(origen_qa, base_dir),
        guardada_origen=guardada_origen, viva=viva, viva_vale=viva_vale, ruta_viva=ruta_viva,
        base_dir=base_dir, decision_entrenar=decision_entrenar))
    print("")
    print("\n".join(aviso_neurona))
    print("")

    # ── E1: QA honesta (obsoletas y ambiguas) ──────────────────────────────
    # Se calcula UNA vez, al principio, sobre la copia recién abierta: antes de que
    # ningún caso despierte nodos ni escriba pesos. Así la clasificación es
    # determinista y no depende del orden de los casos.
    # Referencia = snapshot de origen, para poder afirmar "YA NO declara".
    # Si se está midiendo el propio snapshot, son la misma base y salen 0.
    ruta_ref_honesta = os.environ.get(
        "BIORAG_QA_REFERENCIA",
        os.path.join(base_dir, "snapshots", "qa_escape_qcr_20260811.db"),
    )
    misma_base = (
        ruta_ref_honesta
        and os.path.exists(ruta_ref_honesta)
        and os.path.abspath(ruta_ref_honesta) == os.path.abspath(src_db)
    )
    if not os.path.exists(ruta_ref_honesta) or misma_base:
        ruta_ref_honesta = None
    marcas_honesta = clasificar_casos_sinonimo(db, cases, ruta_ref_honesta)
    honesta_registros = []

    # Tokens del corpus para detectar controles negativos contaminados
    # (autorreferencia: el corpus documenta las mismas queries negativas).
    corpus_tokens = _tokens_corpus(db)

    # ── Resolución de etiquetas oro contra la DB evaluada ──────────────────
    # El JSONL se genera contra una DB concreta; si después un nodo se renombra, la
    # etiqueta queda obsoleta y el caso se vuelve IMPOSIBLE (falla aunque el motor
    # acierte). Se resuelve aquí, en tiempo de evaluación y contra la copia que se está
    # midiendo, para que el dataset no se rompa con cada rename.
    # Desactivable: export BIORAG_QA_RESOLVER_ETIQUETAS=0
    RESOLVER_ETIQUETAS = os.environ.get("BIORAG_QA_RESOLVER_ETIQUETAS", "1") == "1"
    clave_a_conceptos = defaultdict(list)
    for (_conc,) in db.cursor.execute("SELECT concepto FROM largo_plazo").fetchall():
        if _conc:
            clave_a_conceptos[_clave_etiqueta(_conc)].append(_conc)

    # Nivel difuso: los renames reales del corpus no son solo de puntuación. Los 3
    # casos del 2026-09-02 fueron coma -> "_y_" (se AÑADIÓ el token "y"), así que la
    # clave normalizada no coincide:
    #   viejo  lección:_guardar_todo_lo_importante_inmediatamente,_no_esperar
    #   actual lección:_guardar_todo_lo_importante_inmediatamente_y_no_esperar
    # Por eso existe este segundo nivel, acotado por dos guardas: ratio >= umbral y
    # separación clara sobre el segundo mejor candidato. Si no se cumplen ambas, la
    # etiqueta se reporta como irreparable en vez de adivinar (un gold erróneo es peor
    # que un fallo visible).
    UMBRAL_DIFUSO = float(os.environ.get("BIORAG_QA_ETIQUETA_DIFUSA", "0.94"))
    MARGEN_DIFUSO = float(os.environ.get("BIORAG_QA_ETIQUETA_MARGEN", "0.02"))

    def _resolver_etiqueta(esperado):
        """Devuelve (concepto_resuelto, motivo) para una etiqueta oro."""
        if not esperado:
            return esperado, ""
        row = db.cursor.execute(
            "SELECT concepto FROM largo_plazo WHERE concepto = ?", (esperado,)
        ).fetchone()
        if row:
            return esperado, ""

        clave = _clave_etiqueta(esperado)

        # Nivel 1: coincidencia exacta ignorando puntuación y acentos
        candidatos = clave_a_conceptos.get(clave, [])
        if len(candidatos) == 1:
            return candidatos[0], "obsoleta_resuelta"
        if len(candidatos) > 1:
            return esperado, "obsoleta_ambigua"

        # Nivel 2: coincidencia difusa sobre la clave normalizada
        cercanos = difflib.get_close_matches(clave, list(clave_a_conceptos.keys()), n=3, cutoff=0.80)
        if not cercanos:
            return esperado, "inexistente"
        mejor_clave = cercanos[0]
        ratio = difflib.SequenceMatcher(None, clave, mejor_clave).ratio()
        segundo = (
            difflib.SequenceMatcher(None, clave, cercanos[1]).ratio()
            if len(cercanos) > 1 else 0.0
        )
        opciones = clave_a_conceptos[mejor_clave]
        if ratio < UMBRAL_DIFUSO:
            return esperado, f"inexistente (mejor candidato difuso {ratio:.3f} < {UMBRAL_DIFUSO})"
        if (ratio - segundo) < MARGEN_DIFUSO:
            return esperado, f"obsoleta_ambigua_difusa ({ratio:.3f} vs {segundo:.3f})"
        if len(opciones) > 1:
            return esperado, "obsoleta_ambigua"
        return opciones[0], "obsoleta_resuelta_difusa"

    etiquetas_obsoletas = []   # (id, etiqueta_jsonl, concepto_real)
    etiquetas_irreparables = []  # (id, etiqueta_jsonl, motivo)

    # ── Queries con etiqueta oro contradictoria ────────────────────────────
    # Misma query con >= 2 esperados distintos: un motor determinista no puede acertar
    # ambas, así que esos casos no miden el motor, miden el ruido del dataset. Se sacan
    # del Recall global y se reportan aparte como categoría `ambiguo` (igual que
    # `negativo`). En el dataset 2026-09-02: 'dimensiones', 'compromiso', 'biorag'.
    golds_por_query = defaultdict(set)
    for _c in cases:
        if _c.get("concepto_esperado"):
            golds_por_query[_c["query"].strip().lower()].add(_c["concepto_esperado"])
    queries_ambiguas = {q for q, g in golds_por_query.items() if len(g) > 1}

    # Stats tracking
    stats = defaultdict(lambda: {"total": 0, "hits_at_5": 0, "hits_at_1": 0, "reciprocal_rank_sum": 0, "false_positives": 0, "contaminados": 0, "cubiertos": 0})
    failures_by_category = defaultdict(list)
    spreading_activation_count = 0  # Contador de queries que activan spreading activation
    
    start_time = time.time()

    # Snapshot del estado del corpus para poder restaurarlo entre casos (ver
    # _restaurar_estado_nodos). Sin esto la evaluación no es reproducible: cada caso
    # hereda las reactivaciones y subidas de peso_sinaptico de los casos anteriores.
    estado_inicial_nodos = {
        r[0]: (r[1], r[2])
        for r in db.cursor.execute(
            "SELECT concepto, estado, peso_sinaptico FROM largo_plazo"
        ).fetchall()
    }
    nodos_restaurados_total = 0
    nodos_dormidos_iniciales = sum(
        1 for _e, _p in estado_inicial_nodos.values() if _e == "dormido"
    )

    # ── E2b: tolerancia al ruido (SOLO diagnóstico, apagado por defecto) ──────
    # Con BIORAG_QA_RUIDO=zzqx, cada consulta se lanza con esa palabra pegada al
    # final. El token se añade SOLO a la búsqueda: `query` sigue intacta para el
    # control de ambiguas y para los informes. Sirve para medir cuánto aguanta el
    # motor una palabra que no existe en ningún recuerdo.
    RUIDO = os.environ.get("BIORAG_QA_RUIDO", "").strip()

    def _consulta_buscada(q):
        return f"{q} {RUIDO}" if RUIDO else q

    # ── E2b: censo del temático (SOLO diagnóstico, apagado por defecto) ───────
    # Cuenta cuántos candidatos cobran la señal temática y cuántos la cobran
    # saturada a 1.0. No toca el cálculo: envuelve y devuelve el mismo valor.
    CENSO_TEMATICO = os.environ.get("BIORAG_QA_TEMATICO_CENSO", "") == "1"
    censo = {"candidatos": 0, "con_tematico": 0, "saturados": 0, "bloqueados": 0}
    if CENSO_TEMATICO:
        _hibrido_original = type(db)._calcular_score_hibrido

        def _hibrido_censado(self, **kw):
            censo["candidatos"] += 1
            _t = float(kw.get("tematico_score", 0.0) or 0.0)
            _s = float(kw.get("sinonimos_ratio", 0.0) or 0.0)
            if _t > 0:
                censo["con_tematico"] += 1
                if _t == 1.0:
                    censo["saturados"] += 1
            elif _s >= 0.5:
                censo["bloqueados"] += 1
            return _hibrido_original(self, **kw)

        type(db)._calcular_score_hibrido = _hibrido_censado

    # Las dos columnas: orden de la fórmula (antes de la neurona) y orden servido
    espia = QN.Espia(neurona)
    espia.__enter__()
    comparacion = QN.Comparacion()

    for case in cases:
        case_id = case["id"]
        category = case["categoria"]
        query = case["query"]
        expected = case["concepto_esperado"]
        deep = case.get("deep", False)

        # Etiqueta obsoleta -> resolver contra la DB evaluada
        if RESOLVER_ETIQUETAS and expected:
            esperado_resuelto, motivo_etiqueta = _resolver_etiqueta(expected)
            if motivo_etiqueta.startswith("obsoleta_resuelta"):
                etiquetas_obsoletas.append((case_id, expected, esperado_resuelto))
                expected = esperado_resuelto
            elif motivo_etiqueta:
                etiquetas_irreparables.append((case_id, expected, motivo_etiqueta))

        # Query contradictoria -> fuera del recall global
        if expected and query.strip().lower() in queries_ambiguas:
            golds = sorted(golds_por_query[query.strip().lower()])
            stats["ambiguo"]["total"] += 1
            _res, _tot = db.buscar_por_frase(
                _consulta_buscada(query), profundidad="activos", limite=5,
                ignore_peso_sinaptico=True
            )
            _devueltos = [r[0] for r in _res]
            _cubierto = [g for g in golds if g in _devueltos]
            if _cubierto:
                stats["ambiguo"]["cubiertos"] += 1
            else:
                failures_by_category["ambiguo"].append({
                    "id": case_id,
                    "query": query,
                    "expected": golds,
                    "returned": _devueltos[:3],
                    "scores": [r[4] for r in _res][:3],
                    "error": "Query ambigua: ninguno de los esperados contradictorios apareció en top 5",
                })
            nodos_restaurados_total += _restaurar_estado_nodos(db, estado_inicial_nodos)
            continue

        stats[category]["total"] += 1
        
        # 1. Setup phase: only set active/dormant state for target concept (weights are 1.00 for ALL nodes globally)
        if category == "dormido" and expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'dormido' WHERE concepto = ?", (expected,))
            db.conn.commit()
        elif expected:
            db.cursor.execute("UPDATE largo_plazo SET estado = 'activo' WHERE concepto = ?", (expected,))
            db.conn.commit()
            
        # 2. Execute query
        profundidad = "profundo" if (deep or category == "dormido" or category == "negativo") else "activos"
        espia.nueva_busqueda()
        results, total = db.buscar_por_frase(_consulta_buscada(query), profundidad=profundidad, limite=5, ignore_peso_sinaptico=True)
        
        # Track spreading activation usage
        if hasattr(db, 'last_parent_map') and db.last_parent_map:
            spreading_activation_count += 1
        
        # Extract returned concepts
        returned = [r[0] for r in results]
        scores = [r[4] for r in results]
        
        # 3. Evaluation phase
        if expected is None:
            # Negative control case: check if we retrieved any matches with high score
            # Umbral de falso positivo: prioriza override explícito BIORAG_FP_THRESHOLD,
            # luego el umbral conforme persistido en calibracion_estado si existe, y finalmente fallback 0.25.
            if 'BIORAG_FP_THRESHOLD' in os.environ:
                fp_threshold = float(os.environ['BIORAG_FP_THRESHOLD'])
            elif getattr(db, '_umbral_conforme', None) and getattr(db._umbral_conforme, 'umbral', None):
                fp_threshold = float(db._umbral_conforme.umbral)
            else:
                fp_threshold = 0.25

            # Detección de control contaminado: si algún token de la query ya
            # existe como palabra en el corpus, el control dejó de ser "negativo"
            # (el motor lo recupera correctamente y no es un fallo del gate).
            q_tokens = [t for t in re.findall(r'\w{3,}', _normalizar_token(query))]
            contaminados = [t for t in q_tokens if t in corpus_tokens]
            if contaminados:
                stats[category]["contaminados"] += 1
                failures_by_category[category].append({
                    "id": case_id,
                    "query": query,
                    "expected": None,
                    "returned": returned[:3],
                    "scores": scores[:3],
                    "contaminado": True,
                    "error": f"Control negativo contaminado (tokens en corpus: {', '.join(sorted(set(contaminados)))}) — no es un FP del gate"
                })
            else:
                fps = [r for r in results if r[4] >= fp_threshold]
                if len(fps) > 0:
                    stats[category]["false_positives"] += 1
                    failures_by_category[category].append({
                        "id": case_id,
                        "query": query,
                        "expected": None,
                        "returned": returned[:3],
                        "scores": scores[:3],
                        "error": f"False positive returned with score {scores[0]}"
                    })
        else:
            # Normal or awakening case
            found_at = -1
            no_desperto = False
            for idx, concept in enumerate(returned):
                if concept == expected:
                    found_at = idx + 1
                    break
                    
            if found_at != -1:
                stats[category]["hits_at_5"] += 1
                stats[category]["reciprocal_rank_sum"] += 1.0 / found_at
                if found_at == 1:
                    stats[category]["hits_at_1"] += 1
                    
                # Extra validation for dormant nodes: check if the state was updated to 'activo'
                if category == "dormido":
                    db.cursor.execute("SELECT estado FROM largo_plazo WHERE concepto = ?", (expected,))
                    row = db.cursor.fetchone()
                    if not row or row[0] != "activo":
                        failures_by_category[category].append({
                            "id": case_id,
                            "query": query,
                            "expected": expected,
                            "returned": returned[:3],
                            "scores": scores[:3],
                            "error": f"Node found but remained dormant (state is {row[0] if row else 'None'})"
                        })
                        # Revert stats change since awakening failed
                        no_desperto = True
                        stats[category]["hits_at_5"] -= 1
                        if found_at == 1:
                            stats[category]["hits_at_1"] -= 1
                        stats[category]["reciprocal_rank_sum"] -= 1.0 / found_at
            else:
                failures_by_category[category].append({
                    "id": case_id,
                    "query": query,
                    "expected": expected,
                    "returned": returned[:3],
                    "scores": scores[:3],
                    "error": "Expected concept not found in top 5 results"
                })

            # Neurona: mismo caso, dos órdenes (si no despertó, no cuenta para ninguno)
            orden_formula, _servido, coherente = espia.ordenes(returned)
            cuenta = not no_desperto
            comparacion.anotar(
                category,
                QN.puesto(orden_formula, expected) if cuenta else 0,
                found_at if (cuenta and found_at > 0) else 0,
                orden_formula != returned,
                coherente,
            )

            # E1: veredicto de este caso para la QA honesta. Se guarda el resultado
            # FINAL (después de descontar el fallo de despertar), para que la
            # clasificación no pueda "mejorar" un caso que en realidad falló.
            _marca = marcas_honesta.get(case_id)
            honesta_registros.append({
                "id": case_id,
                "categoria": category,
                "hit5": bool(cuenta and found_at != -1),
                "hit1": bool(cuenta and found_at == 1),
                "rr": (1.0 / found_at) if (cuenta and found_at != -1) else 0.0,
                "apartado_r5": bool(_marca and (_marca["obsoleta"] or _marca["ambigua_r5"])),
                "apartado_r1": bool(_marca and (_marca["obsoleta"] or _marca["ambigua_r1"])),
            })

        # Aislar el caso siguiente del estado que este caso dejó en la DB
        nodos_restaurados_total += _restaurar_estado_nodos(db, estado_inicial_nodos)

    elapsed_time = time.time() - start_time
    espia.__exit__(None, None, None)
    db.conn.close()

    res_neurona = comparacion.resumen()
    tiempos_neurona = QN.tiempos(espia.ms)
    tol_neurona = QN.tolerancia_casos()
    motivos_neurona = QN.control_de_dano(res_neurona, tol_neurona)
    
    # Export failed cases to JSONL
    print(f"\nExporting failed cases to: {failed_file}")
    with open(failed_file, "w", encoding="utf-8") as f:
        for cat, fails in failures_by_category.items():
            for fail in fails:
                fail_record = {"categoria": cat, **fail}
                f.write(json.dumps(fail_record, ensure_ascii=False) + "\n")
                
    # Cleanup temp database
    if CENSO_TEMATICO:
        _ct, _sat = censo["con_tematico"], censo["saturados"]
        _pct = (_sat / _ct * 100) if _ct else 0.0
        print(f"[CENSO TEMATICO] candidatos puntuados: {censo['candidatos']} | "
              f"cobran la senal: {_ct} | saturados a 1.0: {_sat} ({_pct:.2f}%) | "
              f"a 0 con sinonimos_ratio>=0.5: {censo['bloqueados']}")
    if RUIDO:
        print(f"[RUIDO] cada consulta se lanzo con la palabra inexistente '{RUIDO}'")

    print(f"Cleaning up temporary database copy at {temp_db}...")
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(temp_db + ext):
            try:
                os.remove(temp_db + ext)
            except OSError:
                pass
        
    # Generate report
    print("\n" + "="*80)
    print("                      BIORAG QA EVALUATION REPORT")
    print("="*80)
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")
    print("-"*80)
    print("\n".join(aviso_neurona))
    print("-"*80)
    print(f"{'Category':<22} | {'Total':<6} | {'Recall@5':<9} | {'Recall@1':<9} | {'MRR':<8} | {'Errors/FPs':<10}")
    print("-"*80)
    
    total_queries = 0
    total_hits_at_5 = 0
    total_hits_at_1 = 0
    total_mrr_sum = 0
    total_negatives = 0
    total_false_positives = 0
    total_contaminados = 0
    
    for cat in sorted(stats.keys()):
        stat = stats[cat]
        cnt = stat["total"]
        if cat == "ambiguo":
            cobertura = (stat.get("cubiertos", 0) / cnt * 100) if cnt else 0.0
            print(f"{cat:<22} | {cnt:<6} | {'N/A':<9} | {'N/A':<9} | {'N/A':<8} | {len(failures_by_category[cat]):<10} ({cobertura:.1f}% de cobertura sobre queries con etiqueta contradictoria; fuera del Recall global)")
            continue
        if cat == "negativo":
            total_negatives += cnt
            total_false_positives += stat["false_positives"]
            total_contaminados += stat.get("contaminados", 0)
            validos = cnt - stat.get("contaminados", 0)
            fp_rate = (stat["false_positives"] / validos) * 100 if validos > 0 else 0.0
            print(f"{cat:<22} | {cnt:<6} | {'N/A':<9} | {'N/A':<9} | {'N/A':<8} | {stat['false_positives']:<10} ({fp_rate:.1f}% FP sobre {validos} válidos; {stat.get('contaminados', 0)} contaminados)")
        else:
            total_queries += cnt
            total_hits_at_5 += stat["hits_at_5"]
            total_hits_at_1 += stat["hits_at_1"]
            total_mrr_sum += stat["reciprocal_rank_sum"]
            
            recall_5 = (stat["hits_at_5"] / cnt) * 100 if cnt > 0 else 0
            recall_1 = (stat["hits_at_1"] / cnt) * 100 if cnt > 0 else 0
            mrr = stat["reciprocal_rank_sum"] / cnt if cnt > 0 else 0
            num_failures = cnt - stat["hits_at_5"] if cat != "dormido" else len(failures_by_category[cat])
            sufijo = ("  " + QN.sufijo_fila(res_neurona["categorias"][cat])
                      if neurona_actua and cat in res_neurona["categorias"] else "")
            print(f"{cat:<22} | {cnt:<6} | {recall_5:>7.2f}% | {recall_1:>7.2f}% | {mrr:>6.3f} | {num_failures:<10}{sufijo}")
            
    print("-"*80)
    global_recall_5 = (total_hits_at_5 / total_queries) * 100 if total_queries > 0 else 0
    global_recall_1 = (total_hits_at_1 / total_queries) * 100 if total_queries > 0 else 0
    global_mrr = total_mrr_sum / total_queries if total_queries > 0 else 0
    global_validos = total_negatives - total_contaminados
    global_fp_rate = (total_false_positives / global_validos) * 100 if global_validos > 0 else 0.0
    
    sufijo = "  " + QN.sufijo_fila(res_neurona["global_"]) if neurona_actua else ""
    print(f"{'GLOBAL SUMMARY (Retrieval)':<22} | {total_queries:<6} | {global_recall_5:>7.2f}% | {global_recall_1:>7.2f}% | {global_mrr:>6.3f} | {total_queries - total_hits_at_5:<10}{sufijo}")
    print(f"{'GLOBAL SUMMARY (Noise/FP)':<22} | {total_negatives:<6} | {'N/A':<9} | {'N/A':<9} | {'N/A':<8} | {total_false_positives:<10} ({global_fp_rate:.2f}% FP sobre {global_validos} válidos; {total_contaminados} contaminados)")
    print(f"{'SPREADING ACTIVATION':<22} | {spreading_activation_count}/{len(cases)} queries ({spreading_activation_count/len(cases)*100:.1f}%)")
    print(f"{'AISLAMIENTO POR CASO':<22} | {nodos_restaurados_total} mutaciones de estado revertidas "
          f"({nodos_dormidos_iniciales} nodos arrancaron dormidos)")
    print("="*80)
    if neurona_actua:
        print("")
        print("\n".join(QN.lineas_resultado(res_neurona, tiempos_neurona, motivos_neurona, tol_neurona)))
        print("="*80)

    # ── E1: QA HONESTA, lado a lado con la clásica ─────────────────────────
    # POR QUÉ se imprime aparte y no se reemplaza nada: la GATE sigue usando la QA
    # clásica (todos los casos) hasta que Dennys diga otra cosa. Aquí solo se dice,
    # con números, cuánto del resultado depende del examen y no del buscador.
    tabla_r5 = _tabla_honesta(honesta_registros, "r5")
    tabla_r1 = _tabla_honesta(honesta_registros, "r1")
    obsoletas = [c for c in cases if marcas_honesta.get(c.get("id"), {}).get("obsoleta")]
    ambiguous = [
        c for c in cases
        if marcas_honesta.get(c.get("id"), {}).get("ambigua_r1")
    ]
    apartados_r5 = [
        c for c in cases
        if marcas_honesta.get(c.get("id"), {}).get("obsoleta")
        or marcas_honesta.get(c.get("id"), {}).get("ambigua_r5")
    ]
    apartados_r1 = [
        c for c in cases
        if marcas_honesta.get(c.get("id"), {}).get("obsoleta")
        or marcas_honesta.get(c.get("id"), {}).get("ambigua_r1")
    ]
    ambas = [c for c in cases if marcas_honesta.get(c.get("id"), {}).get("obsoleta")
             and marcas_honesta.get(c.get("id"), {}).get("ambigua_r1")]
    total_sinonimo = sum(1 for c in cases if c.get("categoria") == "sinonimo")
    resultado_por_id = {r["id"]: r for r in honesta_registros}

    print("")
    print("=" * 88)
    print("   QA HONESTA (E1) — misma búsqueda, distinto conjunto de casos")
    print("=" * 88)
    print("  Reglas del auditor (no se ajustan después de ver resultados):")
    print("    OBSOLETA: el esperado declaraba la palabra en el SNAPSHOT de origen")
    print("              (alias completo o palabra entera del nombre) y YA NO la")
    print("              declara en la base que se mide.")
    print("    AMBIGUA : 2 o más recuerdos la reclaman. Se compara ESTRICTO:")
    print("              alias completo o palabra entera dentro del nombre. Sin")
    print("              'contiene' (con substring, 'agente' reclamaba 119 nodos).")
    print(f"    UMBRAL  : para R@5 se aparta solo con MÁS DE {UMBRAL_AMBIGUA_R5} reclamantes")
    print(f"              (con 5 o menos, todos caben en el top-5); para R@1 desde")
    print(f"              {UMBRAL_AMBIGUA_R1}. Se aparta POR MÉTRICA.")
    print("    NOTA    : ese umbral se decidió DESPUÉS de ver la primera medición de")
    print("              E1. Es una decisión consciente de Dennys, no una regla previa.")
    print("  El examen (casos_qa.jsonl) NO se toca. La GATE sigue usando la CLÁSICA.")
    if ruta_ref_honesta:
        print(f"  Referencia para OBSOLETA: {os.path.basename(ruta_ref_honesta)}")
    else:
        print("  Referencia para OBSOLETA: la base medida es el propio snapshot -> 0 por definición.")
    print(f"  Casos 'sinonimo': {total_sinonimo}. Obsoletas: {len(obsoletas)}. "
          f"Ambiguas: {len(ambiguous)}. Ambas marcas: {len(ambas)}.")
    reubicados = sum(
        1 for c in apartados_r1
        if c.get("query", "").strip().lower() in queries_ambiguas
    )
    print(f"  Apartados -> R@5: {len(apartados_r5)} | R@1: {len(apartados_r1)}  "
          f"(sobre los {total_sinonimo} casos del JSONL; la fila 'sinonimo' tiene "
          f"{stats['sinonimo']['total']} porque {reubicados} de los apartados ya iban a 'ambiguo')")
    print("-" * 88)
    print(f"{'Categoría':<20} | {'CLÁSICA':>18} | {'HONESTA R@5':>20} | {'HONESTA R@1':>20}")
    print(f"{'':<20} | {'n':>6} {'R@5':>5} {'R@1':>5} | {'n':>6} {'R@5':>6} {'ap.':>5} | {'n':>6} {'R@1':>6} {'ap.':>5}")
    print("-" * 88)
    h = {"r5_n": 0, "r5_h5": 0, "r1_n": 0, "r1_h1": 0, "r1_rr": 0.0}
    cl_n = cl_h5 = cl_h1 = 0
    apart_r5_por_cat = defaultdict(int)
    apart_r1_por_cat = defaultdict(int)
    for c in apartados_r5:
        apart_r5_por_cat[c.get("categoria")] += 1
    for c in apartados_r1:
        apart_r1_por_cat[c.get("categoria")] += 1
    for cat in sorted(stats.keys()):
        if cat in ("negativo", "ambiguo"):
            continue
        st = stats[cat]
        if not st["total"]:
            continue
        c5 = (st["hits_at_5"] / st["total"] * 100) if st["total"] else 0.0
        c1 = (st["hits_at_1"] / st["total"] * 100) if st["total"] else 0.0
        cl_n += st["total"]; cl_h5 += st["hits_at_5"]; cl_h1 += st["hits_at_1"]
        t5 = tabla_r5.get(cat, {"n": 0, "h5": 0, "h1": 0, "rr": 0.0})
        t1 = tabla_r1.get(cat, {"n": 0, "h5": 0, "h1": 0, "rr": 0.0})
        r5 = (t5["h5"] / t5["n"] * 100) if t5["n"] else 0.0
        r1 = (t1["h1"] / t1["n"] * 100) if t1["n"] else 0.0
        h["r5_n"] += t5["n"]; h["r5_h5"] += t5["h5"]
        h["r1_n"] += t1["n"]; h["r1_h1"] += t1["h1"]; h["r1_rr"] += t1["rr"]
        print(f"{cat:<20} | {st['total']:>6} {c5:>4.1f}% {c1:>4.1f}% | "
              f"{t5['n']:>6} {r5:>5.1f}% {apart_r5_por_cat.get(cat, 0):>5} | "
              f"{t1['n']:>6} {r1:>5.1f}% {apart_r1_por_cat.get(cat, 0):>5}")
    print("-" * 88)
    g5 = (h["r5_h5"] / h["r5_n"] * 100) if h["r5_n"] else 0.0
    g1 = (h["r1_h1"] / h["r1_n"] * 100) if h["r1_n"] else 0.0
    g_mrr = (h["r1_rr"] / h["r1_n"]) if h["r1_n"] else 0.0
    c5g = (cl_h5 / cl_n * 100) if cl_n else 0.0
    c1g = (cl_h1 / cl_n * 100) if cl_n else 0.0
    print(f"{'GLOBAL (recuperación)':<20} | {cl_n:>6} {c5g:>4.1f}% {c1g:>4.1f}% | "
          f"{h['r5_n']:>6} {g5:>5.1f}% {sum(apart_r5_por_cat.values()):>5} | "
          f"{h['r1_n']:>6} {g1:>5.1f}% {sum(apart_r1_por_cat.values()):>5}")
    # "fallos" = no entró al top-5. La columna R@1 no tiene "fallos": lo que no
    # llega al primer puesto NO es un fallo de recuperación, es un puesto peor.
    # Se dice aparte para no inflar un número con una etiqueta equivocada.
    print(f"{'fallos (fuera del top-5)':<20} | {cl_n - cl_h5:>6} {'':>5} {'':>5} | "
          f"{h['r5_n'] - h['r5_h5']:>6} {'':>6} {'':>5} | {'':>6}")
    print(f"{'no llegó al 1er puesto':<20} | {cl_n - cl_h1:>6} {'':>5} {'':>5} | "
          f"{'':>6} {'':>6} {'':>5} | {h['r1_n'] - h['r1_h1']:>6}")
    print(f"{'MRR':<20} | {'':>6} {'':>5} {'':>5} | {'':>6} {'':>6} {'':>5} | "
          f"{'':>6} {g_mrr:>6.4f}")
    print("=" * 88)

    # ── Los bloques, caso por caso, con su motivo ──────────────────────────
    # Se listan TAMBIÉN las que hoy pasan: si solo se listaran las que fallan,
    # parecería un truco para maquillar el número.
    if obsoletas:
        pasan = sum(1 for c in obsoletas if resultado_por_id.get(c["id"], {}).get("hit5"))
        print(f"\nOBSOLETAS ({len(obsoletas)}) — pasan hoy {pasan}, fallan hoy {len(obsoletas) - pasan}:")
        for c in obsoletas:
            reg = resultado_por_id.get(c["id"], {})
            estado = "TOP1 " if reg.get("hit1") else ("PASA " if reg.get("hit5") else "FALLA")
            print(f"  [{c['id']}] {estado} {c.get('query')!r} -> {c.get('concepto_esperado')}")
            print(f"        motivo: {marcas_honesta[c['id']]['detalle']}")
    if ambiguous:
        pasan = sum(1 for c in ambiguous if resultado_por_id.get(c["id"], {}).get("hit5"))
        print(f"\nAMBIGUAS ({len(ambiguous)}) — pasan hoy {pasan}, fallan hoy {len(ambiguous) - pasan}:")
        for c in sorted(ambiguous, key=lambda x: -marcas_honesta[x["id"]]["n_reclamantes"]):
            m = marcas_honesta[c["id"]]
            reg = resultado_por_id.get(c["id"], {})
            estado = "TOP1 " if reg.get("hit1") else ("PASA " if reg.get("hit5") else "FALLA")
            marca = " [solo R@1: 5 o menos reclamantes]" if not m["ambigua_r5"] else ""
            print(f"  [{c['id']}] {estado} {c.get('query')!r} -> {c.get('concepto_esperado')}")
            print(f"        {m['n_reclamantes']} recuerdos reclaman la palabra{marca}")
    print("-" * 88)

    # ── Salud del dataset: etiquetas que el evaluador tuvo que reparar ──────
    if etiquetas_obsoletas or etiquetas_irreparables or queries_ambiguas:
        print("\nDATASET (salud de las etiquetas oro):")
        print("-"*80)
        if etiquetas_obsoletas:
            print(f"  {len(etiquetas_obsoletas)} etiqueta(s) obsoleta(s) resuelta(s) contra la DB:")
            for _id, _vieja, _nueva in etiquetas_obsoletas:
                print(f"    [{_id}] {_vieja}\n         -> {_nueva}")
        if etiquetas_irreparables:
            print(f"  {len(etiquetas_irreparables)} etiqueta(s) NO resoluble(s) (el nodo no existe en la DB evaluada):")
            for _id, _etq, _mot in etiquetas_irreparables:
                print(f"    [{_id}] {_etq}  ({_mot})")
        if queries_ambiguas:
            print(f"  {len(queries_ambiguas)} query(s) con etiqueta contradictoria -> reclasificadas como 'ambiguo':")
            for _q in sorted(queries_ambiguas):
                print(f"    {_q!r} -> {sorted(golds_por_query[_q])}")
        print("-"*80)
    
    # Output detailed failures per category (up to 3 cases per category)
    if len(failures_by_category) > 0:
        print("\nSAMPLE FAILURES BY CATEGORY FOR ACTIONABLE DIAGNOSIS:")
        print("="*80)
        for cat in sorted(failures_by_category.keys()):
            fails = failures_by_category[cat]
            print(f"\n[Category: {cat}] ({len(fails)} total failures)")
            print("-" * 40)
            for idx, fail in enumerate(fails[:3]):
                print(f"  #{idx+1} [ID {fail['id']}] Query: \"{fail['query']}\"")
                print(f"      Expected:  {fail['expected']}")
                print(f"      Returned:  {fail['returned']} (scores: {[round(s, 3) for s in fail['scores']]})")
                print(f"      Reason:    {fail['error']}")
        print("="*80)
        print(f"Note: All failed cases have been saved to {failed_file} for full debug analysis.")
    else:
        print("\nAmazing! Zero failures detected across all test categories.")
        print("="*80)

    # ── Métricas machine-readable + gate de regresión ──────────────────────
    # Hasta v30.0 la suite solo emitía texto: comparar dos corridas obligaba a hacer
    # grep del informe, y evaluar_qa.py terminaba SIEMPRE en 0. Con `set -e` en
    # run_qa_suite.sh eso significa que la suite no podía fallar: el 2026-09-02 el
    # Recall@5 global cayó 97.39% -> 95.23% (+19 fallos) y el wrapper imprimió
    # "SUITE DE EVALUACIÓN BIORAG FINALIZADA CON ÉXITO".
    #
    # qa_metrics.json deja las cifras listas para diff/CI, y el gate convierte una
    # regresión en exit code distinto de cero.
    metrics_file = os.environ.get(
        "BIORAG_QA_METRICS", os.path.join(base_dir, "scripts", "qa_metrics.json")
    )
    version_file = os.path.join(base_dir, "VERSION")
    version_str = "v30.2"
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as vf:
                version_str = vf.read().strip()
        except Exception:
            pass

    global_fallos = total_queries - total_hits_at_5
    metrics = {
        "version": version_str,
        "generado_en": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(elapsed_time, 2),
        "casos_file": cases_filename,
        "casos_total": len(cases),
        "db_src": src_db,
        "global": {
            "queries": total_queries,
            "recall_at_5": round(global_recall_5, 2),
            "recall_at_1": round(global_recall_1, 2),
            "mrr": round(global_mrr, 4),
            "fallos": global_fallos,
            "negativos_total": total_negatives,
            "negativos_fp": total_false_positives,
            "negativos_fp_rate": round(global_fp_rate, 2),
            "negativos_contaminados": total_contaminados,
            "spreading_activation": spreading_activation_count,
            "etiquetas_obsoletas_resueltas": len(etiquetas_obsoletas),
            "etiquetas_irreparables": len(etiquetas_irreparables),
            "queries_ambiguas": len(queries_ambiguas),
            "nodos_dormidos_iniciales": nodos_dormidos_iniciales,
            "nodos_restaurados_entre_casos": nodos_restaurados_total,
        },
        "categorias": {
            cat: {
                "total": st["total"],
                "recall_at_5": round((st["hits_at_5"] / st["total"] * 100) if st["total"] else 0.0, 2),
                "recall_at_1": round((st["hits_at_1"] / st["total"] * 100) if st["total"] else 0.0, 2),
                "mrr": round((st["reciprocal_rank_sum"] / st["total"]) if st["total"] else 0.0, 4),
                "fallos": (st["total"] - st["hits_at_5"]) if cat != "dormido" else len(failures_by_category[cat]),
            }
            for cat, st in sorted(stats.items())
            if cat not in ("negativo", "ambiguo") and st["total"]
        },
    }
    # E1: la QA honesta va al JSON aparte, sin cambiar la GATE (que sigue mirando
    # la clásica). Así el número honesto se puede seguir en el tiempo sin que un
    # cambio de examen lo mueva.
    metrics["qa_honesta"] = {
        "reglas": {
            "obsoleta": "declaraba el alias en el snapshot de origen y ya no en la base medida",
            "ambigua": "2+ recuerdos reclaman la palabra (alias completo o palabra entera del nombre)",
            "umbral_r5": f"mas de {UMBRAL_AMBIGUA_R5} reclamantes",
            "umbral_r1": f"{UMBRAL_AMBIGUA_R1} o mas reclamantes",
            "decidido": "DESPUES de ver la primera medicion de E1 (decision de Dennys)",
            "referencia": os.path.basename(ruta_ref_honesta) if ruta_ref_honesta else None,
        },
        "sinonimo_total": total_sinonimo,
        "obsoletas": len(obsoletas),
        "ambiguas": len(ambiguous),
        "con_las_dos_marcas": len(ambas),
        "apartados_r5": len(apartados_r5),
        "apartados_r1": len(apartados_r1),
        "global_r5": {
            "queries": h["r5_n"],
            "recall_at_5": round(g5, 2),
            "fallos": h["r5_n"] - h["r5_h5"],
        },
        "global_r1": {
            "queries": h["r1_n"],
            "recall_at_1": round(g1, 2),
            "mrr": round(g_mrr, 4),
            # No es un "fallo": es un puesto peor. La tabla ya lo llama así.
            "no_top1": h["r1_n"] - h["r1_h1"],
        },
        "categorias": {
            cat: {
                "r5": {
                    "total": tabla_r5.get(cat, {"n": 0, "h5": 0})["n"],
                    "recall_at_5": round(
                        (tabla_r5[cat]["h5"] / tabla_r5[cat]["n"] * 100) if tabla_r5.get(cat, {}).get("n") else 0.0, 2),
                    "apartados": apart_r5_por_cat.get(cat, 0),
                },
                "r1": {
                    "total": tabla_r1.get(cat, {"n": 0, "h1": 0})["n"],
                    "recall_at_1": round(
                        (tabla_r1[cat]["h1"] / tabla_r1[cat]["n"] * 100) if tabla_r1.get(cat, {}).get("n") else 0.0, 2),
                    "apartados": apart_r1_por_cat.get(cat, 0),
                },
            }
            for cat in sorted(set(list(tabla_r5.keys()) + list(tabla_r1.keys())))
        },
        "casos_apartados": [
            {
                "id": c["id"],
                "query": c.get("query"),
                "esperado": c.get("concepto_esperado"),
                "obsoleta": marcas_honesta[c["id"]]["obsoleta"],
                "n_reclamantes": marcas_honesta[c["id"]]["n_reclamantes"],
                "apartado_r5": c in apartados_r5,
                "apartado_r1": c in apartados_r1,
                "pasa_hoy": bool(resultado_por_id.get(c["id"], {}).get("hit5")),
            }
            for c in cases if c.get("id") in marcas_honesta
            and (c in apartados_r5 or c in apartados_r1)
        ],
    }
    metrics["neurona"] = {
        "activa": neurona.activa(),
        "actuo": neurona_actua,
        "entrenada_en_la_copia": entrenada_aqui,
        "con_neurona_decision": decision_entrenar,
        "origen": origen_qa,
        "origen_es_snapshot": QN.es_snapshot(origen_qa, base_dir),
        "base_medida": {k: estado_neurona.get(k) for k in
                        ("campeon", "margen", "ciclos", "ascensos", "retiros", "tranquila", "estudio", "guardia")},
        "db_viva": (None if viva is None else {
            "ruta": ruta_viva, "campeon": viva.get("campeon"), "vale_para_este_motor": viva_vale,
            "ciclos": (viva.get("stats") or {}).get("ciclos"),
            "ascensos": (viva.get("stats") or {}).get("ascensos"),
            "retiros": (viva.get("stats") or {}).get("retiros")}),
        "columnas": {"categorias": res_neurona["categorias"], "global": res_neurona["global_"]},
        "cambios": res_neurona["cambios"],
        "incoherentes": res_neurona["incoherentes"],
        "tiempos": tiempos_neurona,
        "control_de_dano": {"tolerancia_casos": tol_neurona, "motivos": motivos_neurona},
    }
    # E2b: se deja constancia en el JSON de si esta corrida llevaba palabra de
    # ruido y del censo del temático, para que las cifras sean interpretables.
    metrics["e2b"] = {
        "ruido": RUIDO or None,
        "censo_tematico": censo if CENSO_TEMATICO else None,
    }
    metrics["global"]["orden_no_monotonico"] = sum(
        1
        for _f in (f for _fs in failures_by_category.values() for f in _fs)
        if _f.get("scores")
        and any(_f["scores"][i] < _f["scores"][i + 1] for i in range(len(_f["scores"]) - 1))
    )
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"\nMétricas exportadas a: {metrics_file}")

    gate_ok, gate_reasons = _evaluar_gate(metrics, base_dir)
    return metrics, gate_ok, gate_reasons


def _evaluar_gate(metrics, base_dir):
    """Compara las métricas de la corrida contra los umbrales del gate de regresión.

    Defaults = la BASELINE v31.1 (Recall@5 97.37%, 23 fallos, FP 15% aceptado — 6 FP
    conocidos del snapshot, gate-producto E11). Supera a v30.2 (97.26%/24/0FP) en
    R@5/R@1/MRR/fallos; FP 15% es el piso aceptado, no una regresión. Para una corrida exploratoria
    (ablaciones, experimentos) se desactiva con BIORAG_QA_GATE=0.

    Variables:
      BIORAG_QA_GATE=1|0            activa/apaga el gate (default 1)
      BIORAG_QA_MIN_RECALL5=97.0    Recall@5 global mínimo, en %
      BIORAG_QA_MAX_FALLOS=24       máximo de fallos de recuperación
      BIORAG_QA_MAX_FP_RATE=15.0    máximo % de falsos positivos sobre negativos válidos
      BIORAG_QA_MAX_REGRESION_PP=2.0  caída máxima por categoría vs. baseline, en pp
      BIORAG_QA_BASELINE=qa_metrics_baseline.json  baseline en scripts/ (si no existe,
                                      solo se avisa; no se compara por categoría)
      BIORAG_QA_NEURONA_TOL_CASOS=1 casos en 1er lugar que la neurona puede perder por
                                      categoría (solo cuenta si la neurona actuó; además
                                      su Recall@5 debe ser idéntico y su total de aciertos
                                      en 1er lugar no puede bajar; ver qa_neurona.py)
    """
    if os.environ.get("BIORAG_QA_GATE", "1") != "1":
        return True, ["gate desactivado (BIORAG_QA_GATE=0)"]

    g = metrics["global"]
    min_recall5 = float(os.environ.get("BIORAG_QA_MIN_RECALL5", "97.0"))
    max_fallos = int(os.environ.get("BIORAG_QA_MAX_FALLOS", "24"))
    max_fp = float(os.environ.get("BIORAG_QA_MAX_FP_RATE", "15.0"))
    max_regresion = float(os.environ.get("BIORAG_QA_MAX_REGRESION_PP", "2.0"))

    reasons = []
    if g["recall_at_5"] < min_recall5:
        reasons.append(
            f"Recall@5 global {g['recall_at_5']:.2f}% < mínimo {min_recall5:.2f}%"
        )
    if g["fallos"] > max_fallos:
        reasons.append(f"{g['fallos']} fallos > máximo {max_fallos}")
    if g["negativos_fp_rate"] > max_fp:
        reasons.append(
            f"FP {g['negativos_fp_rate']:.2f}% > máximo {max_fp:.2f}% "
            f"({g['negativos_fp']}/{g['negativos_total'] - g['negativos_contaminados']} negativos válidos)"
        )
    # Neurona de ranking: no puede dañar (ver qa_neurona.control_de_dano)
    reasons.extend(metrics.get("neurona", {}).get("control_de_dano", {}).get("motivos", []))

    baseline_name = os.environ.get("BIORAG_QA_BASELINE", "qa_metrics_baseline.json")
    baseline_path = os.path.join(base_dir, "scripts", baseline_name)
    if os.path.exists(baseline_path):
        try:
            with open(baseline_path, encoding="utf-8") as f:
                base = json.load(f)
            for cat, actual in metrics["categorias"].items():
                ref = base.get("categorias", {}).get(cat)
                if not ref:
                    continue
                delta = actual["recall_at_5"] - ref["recall_at_5"]
                if delta < -max_regresion:
                    reasons.append(
                        f"{cat}: Recall@5 {actual['recall_at_5']:.2f}% vs baseline "
                        f"{ref['recall_at_5']:.2f}% ({delta:+.2f} pp)"
                    )
        except Exception as exc:  # baseline corrupta no debe tumbar la corrida
            print(f"[WARN] No se pudo leer la baseline {baseline_path}: {exc}")
    else:
        print(
            f"[INFO] Sin baseline en {baseline_path} — se omitió la comparación por "
            f"categoría. Generala con: cp scripts/qa_metrics.json scripts/{baseline_name}"
        )

    return (len(reasons) == 0), reasons


if __name__ == "__main__":
    metrics, gate_ok, reasons = run_evaluation()
    if not gate_ok:
        print("\n" + "!" * 80)
        print("GATE DE REGRESIÓN: FALLADO")
        print("!" * 80)
        for r in reasons:
            print(f"  ✗ {r}")
        print("\nLa suite termina en rojo a propósito: estos números están por debajo")
        print("de la baseline oficial. Si estás en una corrida exploratoria (ablación,")
        print("experimento) y esperabas este resultado, relaja o apaga el gate con:")
        print("  BIORAG_QA_GATE=0 ./scripts/run_qa_suite.sh")
        print("  BIORAG_QA_MIN_RECALL5=95.0 BIORAG_QA_MAX_FALLOS=42 ./scripts/run_qa_suite.sh")
        if any(r.startswith("neurona:") for r in reasons):
            print("\nSi lo que falla es la NEURONA: el motor sin ella (la fórmula sola) está en la")
            print("columna 'fórmula' del bloque LA NEURONA EN ESTA QA. Para medir sin neurona:")
            print("  BIORAG_NEURONA=0 python scripts/evaluar_qa.py")
            print("Tolerancia por categoría (casos en 1er lugar): BIORAG_QA_NEURONA_TOL_CASOS=1")
        print("!" * 80)
        sys.exit(1)
    if reasons:
        print(f"\n[GATE] OK — {'; '.join(reasons)}")
    else:
        print("\n[GATE] OK — métricas dentro de los umbrales de la baseline oficial")
