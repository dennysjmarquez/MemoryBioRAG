#!/usr/bin/env python3
"""BioRAG CLI — local memory tools. Command names and flags are preserved for compatibility.

Topic keywords describe what a memory is about, not every name or detail it mentions.

  python3 biorag.py buscar <query> [options]
    Search permanent memory using textual, semantic and associative signals.
    Options:
    --sustantivos-clave "a,b"  Topic keywords; alias: --sustantivos.
    --deep                     Include dormant memories and wake retrieved dormant nodes.
    --todos                    Request up to 100 results, unless --frase or --tokens
                               selects another search route.
    --tokens "root1,root2"     Search stemmed tokens instead of a phrase.
    --modo strict|relaxed      Token matching; default: relaxed.
    --frase                    Explicit phrase search (the default route).
    --pagina N                 Results page, starting at 1.
    --cat TYPE                 Filter by category.
    --completo                 Show full content rather than a preview.
    --asociados                Show associated concepts and topic keywords.

  python3 biorag.py guardar <concept> <content> --sustantivos-clave "a,b" [options]
    Save a memory in working memory. Consolidate it with sueno before searching.
    Options:
    --sustantivos-clave "a,b"  Required: 1–5 keywords; each is 2–15 Unicode letters,
                               combining marks or numbers, or underscores; no spaces.
    --sustantivos              Alias of --sustantivos-clave.
    --syn "a,b"                Search synonyms.
    --cat TYPE                 Explicit category; otherwise inferred from content.

  python3 biorag.py sustantivos <concept>
    Inspect topic keywords in permanent or working memory. Alias: sustantivo.
    Options:
    No additional options.

  python3 biorag.py agregar_sustantivos <concept> "keyword1,keyword2"
    Assign topic keywords in permanent or working memory.
    Options:
    --sustantivos-clave "a,b"  Alternative to the positional keyword list.
    --sustantivos           Alias of --sustantivos-clave.
    Aliases: agregar-sustantivos, asignar_sustantivos, asignar-sustantivos.

  python3 biorag.py asociar <concept_a> <concept_b>
    Create a bidirectional association between related concepts.
    Options:
    No additional options.

  python3 biorag.py comunicar <destination> <message>
    Store an inter-agent message. AGENT_NAME identifies the sender.
    Use todos for an explicit shared broadcast.
    Recipient routing is currently restricted: an unknown ID becomes todos.
    Arbitrary private destinations are not supported by the current engine.
    Options:
    No additional options.

  python3 biorag.py leer_mensajes [options]
    Display messages and mark displayed unread messages as read.
    Options:
    --no-leidos             Show unread messages only.
    --ultimos N             Show up to N recent messages; default: 10.
    --para ID               Destination filter; unsupported IDs are ignored.
    AGENT_NAME identifies the reader.

  python3 biorag.py sueno [energy_limit]
    Consolidate working memory and apply memory maintenance.
    Options:
    energy_limit           Optional numerical energy limit.

  python3 biorag.py corteza
    List permanent memory nodes, including active and dormant nodes.
    Options:
    No additional options.

  python3 biorag.py listar [--pagina N]
    List permanent concepts in pages of 10 with content previews.
    Options:
    --pagina N              Page number, starting at 1.

  python3 biorag.py familiaridad <text>
    Find active permanent concepts mentioned in text.
    Options:
    No additional options.

  python3 biorag.py estado
    Show active/dormant counts, working memory size, energy and keyword coverage.
    Options:
    No additional options.

  python3 biorag.py dashboard
    Launch the optional local dashboard. May install dependencies and start servers.
    Options:
    No additional options. Use --help to inspect this command without launching it.

Project: https://github.com/dennysjmarquez/MemoryBioRAG
"""
import sys

# Ayuda, errores de uso y mantenimiento sin importar NLP ni abrir memoria.
if __name__ == '__main__':
    from core.cli import can_handle_early, main as bootstrap_main
    if can_handle_early(sys.argv[1:]):
        raise SystemExit(bootstrap_main())

import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import re
import unicodedata
from core.memory_store import SQLiteMemoryBioRAG, normalizar_sustantivos_clave
from core.sinapsis import auto_vincular, vincular_por_sinonimos, _tokenizar, _peso_similitud
from core.categorizador import inferir_categoria

from core.paths import resolve_db_path

DB_PATH = resolve_db_path()


def _sanitizar_entrada_cli(texto: str, max_len: int = 100000, nombre_campo: str = "entrada") -> str:
    """
    Sanitiza entradas del CLI según lineamientos OWASP (A03: Injection & Input Validation).
    - Elimina bytes nulos (\\x00) y caracteres de control ASCII.
    - Normaliza espacios en blanco repetidos.
    - Valida límites duros de longitud para evitar DoS por memoria.
    """
    if texto is None:
        return ""
    sanitizado = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', str(texto))
    sanitizado = re.sub(r'[ \t]+', ' ', sanitizado).strip()
    if len(sanitizado) > max_len:
        raise ValueError(f"El campo '{nombre_campo}' excede el límite máximo de {max_len} caracteres (recibidos: {len(sanitizado)}).")
    return sanitizado


def _extraer_flag_valor(args: list, flags: list, default: str = "") -> tuple:
    """
    Extrae un flag y su valor de una lista de argumentos de terminal,
    sin importar su posición (inicio, medio, final).
    Retorna (valor_extraido, lista_argumentos_restantes).
    Lanza ValueError si el flag está presente pero no tiene valor o el valor es otro flag.
    """
    args_restantes = []
    valor = default
    i = 0
    while i < len(args):
        token = args[i]
        if token in flags:
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                raise ValueError(f"El flag '{token}' requiere un valor.")
            valor = args[i + 1]
            i += 2
        else:
            args_restantes.append(token)
            i += 1
    return valor, args_restantes


def _buscar_nodos_viejos_relacionados(cerebro, tokens_nuevos, contenido_nuevo, top_k=3, umbral=0.05):
    """
    Busca en largo_plazo nodos semanticamente similares al contenido nuevo.
    Retorna lista de (concepto, preview, dias_antiguedad, similitud).
    """
    if not tokens_nuevos:
        return []
    try:
        cerebro.cursor.execute("""
            SELECT concepto, contenido, creado_en
            FROM largo_plazo
            WHERE estado = 'activo'
            ORDER BY creado_en ASC
        """)
        candidatos = cerebro.cursor.fetchall()
    except Exception:
        return []

    if not candidatos:
        return []

    resultados = []
    for concepto, contenido, creado_en in candidatos:
        tokens_exist = _tokenizar((concepto or "") + " " + (contenido or ""))
        sim = _peso_similitud(tokens_nuevos, tokens_exist)
        if sim >= umbral:
            dias_ant = int((time.time() - (creado_en or time.time())) / 86400)
            preview = (contenido or "")[:120].replace("\n", " ")
            resultados.append((concepto, preview, dias_ant, round(sim, 2)))

    resultados.sort(key=lambda x: x[3], reverse=True)
    return resultados[:top_k]


def cmd_buscar(cerebro, args):
    if not args:
        print("Especifica un concepto. Ej: biorag.py buscar san_cayetano")
        print("  --deep        Buscar tambien en memoria dormida (despierta el nodo)")
        print("  --todos       Mostrar TODOS los recuerdos relacionados, ordenados por relevancia")
        print("  --frase       Busqueda por frase en lenguaje natural (FTS5, no requiere stemming)")
        print("  --tokens      Lista de raices stemmeadas separadas por comas (busqueda multi-token)")
        print("  --pagina N    Pagina de resultados (defecto: 1)")
        print("  --modo M      strict | relaxed (defecto: relaxed)")
        print("  --cat T       Filtrar por categoria (ej: proyecto, leccion, hardware)")
        print("  --completo    Muestra el contenido completo sin truncar")
        print("  --asociados   Muestra nodos asociados a los resultados")
        return 1

    deep = False
    todos = False
    multi_token = False
    tokens = []
    modo = "relaxed"
    pagina = 1
    completo = False
    asociados = False
    frase = False

    # Extraer --sustantivos-clave / --sustantivos
    sustantivos_boost = None
    try:
        raw_sustantivos, args = _extraer_flag_valor(
            args, ["--sustantivos-clave", "--sustantivos"], default=""
        )
        if raw_sustantivos:
            from core.memory_store import normalizar_sustantivos_clave
            sustantivos_boost = normalizar_sustantivos_clave(raw_sustantivos)
    except ValueError as e:
        print(f"Error en flag de sustantivos: {e}")
        return 1

    if "--deep" in args:
        deep = True
        args = [a for a in args if a != "--deep"]
    if "--todos" in args:
        todos = True
        args = [a for a in args if a != "--todos"]
    if "--completo" in args:
        completo = True
        args = [a for a in args if a != "--completo"]
    if "--asociados" in args:
        asociados = True
        args = [a for a in args if a != "--asociados"]
    if "--frase" in args:
        frase = True
        args = [a for a in args if a != "--frase"]
    for i, a in enumerate(args):
        if a == "--tokens":
            if i + 1 >= len(args):
                print("Error: --tokens requiere al menos un valor.")
                print("  Ej: --tokens \"raiz1,raiz2\"")
                return 1
            if args[i + 1].startswith("--"):
                print("Error: --tokens requiere un valor, no otro flag.")
                print("  Ej: --tokens \"raiz1,raiz2\"")
                return 1
            multi_token = True
            tokens = [t.strip() for t in args[i + 1].split(",") if t.strip()]
            if not tokens:
                print("Error: --tokens requiere al menos una raiz.")
                print("  Ej: --tokens \"raiz1,raiz2\"")
                return 1
            args = [x for j, x in enumerate(args) if j != i and j != i + 1]
            break
    for i, a in enumerate(args):
        if a == "--pagina" and i + 1 < len(args):
            try:
                pagina = int(args[i + 1])
            except ValueError:
                pass
            args = [x for j, x in enumerate(args) if j != i and j != i + 1]
            break
    for i, a in enumerate(args):
        if a == "--modo" and i + 1 < len(args):
            modo = args[i + 1] if args[i + 1] in ("strict", "relaxed") else "relaxed"
            args = [x for j, x in enumerate(args) if j != i and j != i + 1]
            break
    filtro_cat = None
    for i, a in enumerate(args):
        if a == "--cat" and i + 1 < len(args) and not args[i + 1].startswith("--"):
            filtro_cat = args[i + 1]
            args = [x for j, x in enumerate(args) if j != i and j != i + 1]
            break

    if not frase and not multi_token and not todos:
        frase = True

    if not args:
        print("Especifica un concepto.")
        return 1
    concepto = " ".join(args)

    def _mostrar_resultados(resultados, total, subtitulo=""):
        """Helper para display de resultados con --asociados y sustantivos clave.
        El truncado se maneja a nivel del motor (preview_chars en buscar_por_frase)."""
        if not resultados:
            return

        susts_map = {}
        if resultados:
            nombres = [r[0] for r in resultados]
            placeholders = ",".join("?" * len(nombres))
            cerebro.cursor.execute(
                f"SELECT concepto, COALESCE(sustantivos_clave, '') FROM largo_plazo WHERE concepto IN ({placeholders})",
                nombres
            )
            for c_nombre, sk in cerebro.cursor.fetchall():
                if sk and sk.strip():
                    susts_map[c_nombre] = sk

        total_paginas = max(1, (total + 2) // 3) if total > 0 else 1
        print(f"[MemoryBioRAG] {total} coincidencias encontradas (pagina {pagina}/{total_paginas})")
        if subtitulo:
            print(f"  ({subtitulo})")
        print("=" * 60)
        for i, (nombre, contenido, peso, estado, score, asociaciones) in enumerate(resultados, 1):
            print(f"\n--- #{i}: {nombre} (peso:{peso:.2f}, estado:{estado}, score:{score:.2f}) ---")
            print(contenido or "")
            if nombre in susts_map and (completo or asociados):
                sk_items = [s.strip() for s in susts_map[nombre].split(",") if s.strip()]
                if sk_items:
                    print(f"     Sustantivos clave: {', '.join(sk_items)}")
            if asociados and asociaciones:
                vecinos = [v.strip() for v in asociaciones.split(",") if v.strip()]
                if vecinos:
                    print(f"     asociaciones: {', '.join(vecinos)}")
        print("\n" + "=" * 60)
        if pagina < total_paginas:
            print(f"Usa --pagina {pagina + 1} para mas resultados.")

    if frase:
        preview = 0 if completo else None
        profundidad = "profundo" if deep else "activos"
        resultados, total = cerebro.buscar_por_frase(
            concepto, profundidad=profundidad, pagina=pagina,
            categoria=filtro_cat, preview_chars=preview,
            sustantivos_clave_boost=sustantivos_boost
        )
        if not resultados:
            print(f"No se encontraron coincidencias para la frase.")
            print("\n💡 Sugerencia: Puedes refinar la búsqueda especificando su núcleo temático con --sustantivos-clave \"termino1,termino2\"")
            return 1
        subt = f"frase: {concepto[:60]}"
        if filtro_cat:
            subt += f" [cat: {filtro_cat}]"
        _mostrar_resultados(resultados, total, subt)
        return 0

    if multi_token:
        profundidad = "profundo" if deep else "activos"
        resultados, total = cerebro.buscar_por_tokens(tokens, modo=modo, profundidad=profundidad, pagina=pagina)
        if not resultados:
            print(f"No se encontraron coincidencias para los tokens especificados.")
            print("\n💡 Sugerencia: Puedes refinar la búsqueda especificando su núcleo temático con --sustantivos-clave \"termino1,termino2\"")
            return 1
        _mostrar_resultados(resultados, total, "tokens: " + ",".join(tokens))
        return 0

    if todos:
        preview = 0 if completo else None
        profundidad = "profundo" if deep else "activos"
        resultados, total = cerebro.buscar_por_frase(
            concepto, profundidad=profundidad, pagina=pagina, limite=100,
            categoria=filtro_cat, preview_chars=preview,
            sustantivos_clave_boost=sustantivos_boost
        )
        if not resultados:
            print(f"No se encontro '{concepto}' en la corteza.")
            print("\n💡 Sugerencia: Puedes refinar la búsqueda especificando su núcleo temático con --sustantivos-clave \"termino1,termino2\"")
            return 1
        subt = f"todos los resultados ({profundidad})"
        if filtro_cat:
            subt += f" [cat: {filtro_cat}]"
        _mostrar_resultados(resultados, total, subt)
        return 0

    if deep:
        resultado = cerebro.buscar_recuerdo_profundo(concepto)
    else:
        resultado = cerebro.buscar_recuerdo_microsegundos(concepto)
    if resultado:
        if completo:
            print(resultado)
        else:
            print(resultado[:1500] + ("..." if len(resultado) > 1500 else ""))
        return 0
    print(f"No se encontro '{concepto}' en la corteza.")
    print("\n💡 Sugerencia: Puedes refinar la búsqueda especificando su núcleo temático con --sustantivos-clave \"termino1,termino2\"")
    return 1


def _validar_sustantivos_clave(raw_sustantivos: str) -> str:
    """
    Valida y normaliza sustantivos clave para la CLI según Spec 002 (RF-5, RF-22, RF-23).
    - Entre 1 y 5 términos separados por comas.
    - Longitud de cada término entre 2 y 15 caracteres.
    - Caracteres alfanuméricos y guiones bajos (preservando ñ).
    """
    if not raw_sustantivos or not str(raw_sustantivos).strip():
        raise ValueError("Debe proporcionar al menos un sustantivo clave.")

    from core.memory_store import normalizar_sustantivos_clave
    norm = normalizar_sustantivos_clave(raw_sustantivos)
    terminos = [t.strip() for t in norm.split(",") if t.strip()]

    if not (1 <= len(terminos) <= 5):
        raise ValueError(f"Debe especificar entre 1 y 5 sustantivos clave (recibidos: {len(terminos)}).")

    for t in terminos:
        if len(t) < 2 or len(t) > 15:
            raise ValueError(f"El sustantivo '{t}' debe tener entre 2 y 15 caracteres (tiene {len(t)}).")
        if not all(unicodedata.category(char)[0] in "LMN" or char == "_" for char in t):
            raise ValueError(
                f"El sustantivo '{t}' contiene caracteres no permitidos. "
                "Solo se permiten letras Unicode, marcas, números y guiones bajos."
            )

    return norm


def cmd_guardar(cerebro, args):
    """
    Guarda un nuevo recuerdo en BioRAG con su núcleo temático obligatorio.

    Uso:
        biorag.py guardar <clave> <contenido> --sustantivos-clave "s1,s2,s3"

    El flag --sustantivos-clave (alias: --sustantivos) es OBLIGATORIO.
    Define el NÚCLEO TEMÁTICO: los 1-5 sustantivos que identifican de qué
    TRATA el recuerdo (no lo que simplemente menciona).
    """
    # ── 1. Extraer flags opcionales: --syn, --cat ────────────────────────────
    sinonimos = ""
    categoria = None

    try:
        sinonimos, args = _extraer_flag_valor(args, ["--syn"], default="")
    except ValueError:
        print("Error: --syn requiere una lista de terminos. Ej: --syn \"angular,forms\"")
        return 1

    try:
        categoria_raw, args = _extraer_flag_valor(args, ["--cat"], default="")
        categoria = categoria_raw if categoria_raw else None
    except ValueError:
        print("Error: --cat requiere un tipo. Ej: --cat proyecto")
        return 1

    # ── 2. Extraer --sustantivos-clave / --sustantivos (OBLIGATORIO) ─────────
    try:
        raw_sustantivos, args = _extraer_flag_valor(
            args, ["--sustantivos-clave", "--sustantivos"], default=""
        )
    except ValueError as e:
        _imprimir_guia_sustantivos_clave(str(e))
        return 1

    # ── 3. Verificar presencia del flag (obligatorio) ────────────────────────
    if not raw_sustantivos:
        _imprimir_guia_sustantivos_clave()
        return 1

    # ── 4. Validar argumentos posicionales: clave y contenido ────────────────
    if len(args) < 2:
        print("Uso: biorag.py guardar <clave> <contenido> --sustantivos-clave \"s1,s2\"")
        return 1

    # ── 5. Sanitizar entradas (OWASP A03) ────────────────────────────────────
    try:
        clave_raw = _sanitizar_entrada_cli(args[0], max_len=200, nombre_campo="concepto")
        contenido_raw = _sanitizar_entrada_cli(" ".join(args[1:]), max_len=100000, nombre_campo="contenido")
        raw_sustantivos = _sanitizar_entrada_cli(raw_sustantivos, max_len=500, nombre_campo="sustantivos_clave")
    except ValueError as e:
        print(f"Error de validación: {e}")
        return 1

    if not clave_raw:
        print("Error: La clave no puede estar vacía.")
        return 1

    clave = clave_raw.lower().replace(" ", "_")

    # ── 6. Validar y normalizar sustantivos vía función del Core ─────────────
    try:
        sustantivos_norm = _validar_sustantivos_clave(raw_sustantivos)
    except ValueError as e:
        print(f"\n❌ Error en --sustantivos-clave: {e}\n")
        _imprimir_guia_sustantivos_clave()
        return 1

    # ── 7. Inferir categoría si no se proporcionó ─────────────────────────────
    if not categoria:
        categoria = inferir_categoria(contenido_raw)

    # ── 8. Almacenar en corto plazo ───────────────────────────────────────────
    cerebro.percibir_corto_plazo(clave, contenido_raw, sinonimos, categoria,
                                 sustantivos_clave=sustantivos_norm)

    # ── 9. Auto-vincular y enlazar por sinónimos ──────────────────────────────
    enlaces = auto_vincular(cerebro, clave, contenido_raw)
    if sinonimos:
        syn_enlaces = vincular_por_sinonimos(cerebro, clave, sinonimos)
        todas = list({e[0]: e for e in enlaces + syn_enlaces}.values())
        enlaces = todas

    # ── 10. Confirmación visual enriquecida ────────────────────────────────────
    lista_sust = [s.strip() for s in sustantivos_norm.split(",") if s.strip()]
    conteo = len(lista_sust)
    msg = f"'{clave}' guardado en corto plazo.\n"
    msg += f"Sustantivos clave: [{', '.join(lista_sust)}] ({conteo}/5)\n"
    if sinonimos:
        msg += f"Sinonimos: {sinonimos}.\n"
    if categoria != "general":
        msg += f"Categoria: {categoria}.\n"
    if enlaces:
        msg += f"Vinculado con {len(enlaces)} nodo(s): {', '.join(e[0] for e in enlaces)}.\n"
    msg += "Consolidalo con 'sueno' para hacerlo permanente."

    tokens_nuevos = _tokenizar(clave + " " + contenido_raw)
    viejos = _buscar_nodos_viejos_relacionados(cerebro, tokens_nuevos, contenido_raw, top_k=3, umbral=0.05)
    if viejos:
        lineas_viejos = []
        for concepto_v, preview, dias_ant, sim in viejos:
            fecha = time.strftime("%d %b %Y", time.localtime(time.time() - dias_ant * 86400))
            lineas_viejos.append("  ✨ {} ({}d) · {} (sim={}) · {}".format(fecha, dias_ant, concepto_v, sim, preview))
        msg += "\n\n✨ Conexiones con el pasado:"
        msg += "\n" + "\n".join(lineas_viejos)

    print(msg)
    return 0


_GUIA_SUSTANTIVOS_CLAVE = """
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️  --sustantivos-clave es OBLIGATORIO en 'guardar'            │
├─────────────────────────────────────────────────────────────────┤
│  ¿Qué es el Núcleo Temático?                                    │
│                                                                 │
│  Son los 1 a 5 sustantivos que identifican de qué TRATA         │
│  el recuerdo — no lo que meramente menciona.                    │
│                                                                 │
│  Regla rápida: ¿De qué trata? ≠ ¿Qué aparece en el texto?      │
│                                                                 │
│  Ejemplo:                                                       │
│    Texto: "Einstein demostró que E=mc² en 1905 en Berlín"       │
│    TRATA de: relatividad, energia, masa                         │
│    MENCIONA: Berlín, 1905 (fechas/lugares son contexto)         │
│                                                                 │
│  Uso correcto:                                                  │
│    biorag.py guardar <clave> <contenido> \\                      │
│      --sustantivos-clave "termino1,termino2,termino3"           │
│                                                                 │
│  Reglas de formato:                                             │
│    • Entre 1 y 5 términos separados por coma                    │
│    • Cada término: 2 a 15 caracteres alfanuméricos              │
│    • Solo letras, números y guiones bajos                       │
└─────────────────────────────────────────────────────────────────┘
"""


def _imprimir_guia_sustantivos_clave(razon: str = ""):
    """
    Imprime la guía pedagógica del Núcleo Temático en la terminal.
    Siempre precedida por el motivo concreto del error si se proporciona.
    """
    if razon:
        print(f"\n❌ {razon}")
    print(_GUIA_SUSTANTIVOS_CLAVE)


def cmd_sustantivos(cerebro, args):
    """
    Consulta los sustantivos clave asignados a un concepto en la corteza.
    Uso:
        biorag.py sustantivos <concepto>
    """
    if not args:
        print("Uso: biorag.py sustantivos <concepto>")
        return 1

    try:
        concepto_raw = _sanitizar_entrada_cli(args[0], max_len=200, nombre_campo="concepto")
    except ValueError as e:
        print(f"Error de validación: {e}")
        return 1

    clave = concepto_raw.lower().strip().replace(" ", "_")

    # 1. Buscar en largo_plazo
    cerebro.cursor.execute("SELECT sustantivos_clave FROM largo_plazo WHERE concepto = ?", (clave,))
    row = cerebro.cursor.fetchone()

    # 2. Fallback a corto_plazo
    if row is None:
        cerebro.cursor.execute("SELECT sustantivos_clave FROM corto_plazo WHERE concepto = ?", (clave,))
        row = cerebro.cursor.fetchone()

    if row is None:
        print(f"Error: Concepto '{clave}' no encontrado en la corteza.")
        return 1

    sustantivos_str = row[0] or ""
    if not sustantivos_str.strip():
        print(f"El concepto '{clave}' no tiene sustantivos clave asignados (nodo legado).")
        print(f"Puedes agregarlos con: biorag.py agregar_sustantivos {clave} \"termino1,termino2\"")
        return 0

    lista = [s.strip() for s in sustantivos_str.split(",") if s.strip()]
    print(f"Sustantivos clave de '{clave}': [{', '.join(lista)}] ({len(lista)}/5)")
    return 0


def cmd_agregar_sustantivos(cerebro, args):
    """
    Asigna o actualiza los sustantivos clave de un concepto existente.
    Uso:
        biorag.py agregar_sustantivos <concepto> "termino1,termino2"
        biorag.py agregar_sustantivos <concepto> --sustantivos-clave "termino1,termino2"
    """
    # 1. Extraer flag si se pasó con --sustantivos-clave o --sustantivos
    raw_sustantivos = ""
    try:
        raw_sustantivos, args_restantes = _extraer_flag_valor(
            args, ["--sustantivos-clave", "--sustantivos"], default=""
        )
    except ValueError as e:
        _imprimir_guia_sustantivos_clave(str(e))
        return 1

    if not raw_sustantivos:
        if len(args_restantes) < 2:
            print("Uso: biorag.py agregar_sustantivos <concepto> \"sustantivo1,sustantivo2\"")
            return 1
        concepto_arg = args_restantes[0]
        raw_sustantivos = " ".join(args_restantes[1:])
    else:
        if len(args_restantes) < 1:
            print("Uso: biorag.py agregar_sustantivos <concepto> --sustantivos-clave \"sustantivo1,sustantivo2\"")
            return 1
        concepto_arg = args_restantes[0]

    # 2. Sanitizar concepto y sustantivos
    try:
        concepto_raw = _sanitizar_entrada_cli(concepto_arg, max_len=200, nombre_campo="concepto")
        raw_sustantivos = _sanitizar_entrada_cli(raw_sustantivos, max_len=500, nombre_campo="sustantivos_clave")
    except ValueError as e:
        print(f"Error de validación: {e}")
        return 1

    clave = concepto_raw.lower().strip().replace(" ", "_")

    # 3. Validar sustantivos
    try:
        sustantivos_norm = _validar_sustantivos_clave(raw_sustantivos)
    except ValueError as e:
        print(f"\n❌ Error en sustantivos clave: {e}\n")
        _imprimir_guia_sustantivos_clave()
        return 1

    # 4. Actualizar en largo_plazo o corto_plazo
    cerebro.cursor.execute("SELECT sustantivos_clave FROM largo_plazo WHERE concepto = ?", (clave,))
    row_lp = cerebro.cursor.fetchone()
    if row_lp is not None:
        anterior = row_lp[0] or ""
        cerebro.cursor.execute("UPDATE largo_plazo SET sustantivos_clave = ? WHERE concepto = ?", (sustantivos_norm, clave))
        cerebro.conn.commit()
        if anterior:
            print(f"Sustantivos clave actualizados para '{clave}': {sustantivos_norm} (anteriores: {anterior})")
        else:
            print(f"Sustantivos clave asignados para '{clave}': {sustantivos_norm}")
        return 0

    cerebro.cursor.execute("SELECT sustantivos_clave FROM corto_plazo WHERE concepto = ?", (clave,))
    row_cp = cerebro.cursor.fetchone()
    if row_cp is not None:
        anterior = row_cp[0] or ""
        cerebro.cursor.execute("UPDATE corto_plazo SET sustantivos_clave = ? WHERE concepto = ?", (sustantivos_norm, clave))
        cerebro.conn.commit()
        if anterior:
            print(f"Sustantivos clave actualizados para '{clave}' (corto plazo): {sustantivos_norm} (anteriores: {anterior})")
        else:
            print(f"Sustantivos clave asignados para '{clave}' (corto plazo): {sustantivos_norm}")
        return 0

    print(f"Error: Concepto '{clave}' no encontrado en la corteza.")
    return 1


def cmd_asociar(cerebro, args):
    if len(args) < 2:
        print("Uso: biorag.py asociar <concepto_a> <concepto_b>")
        return 1
    cerebro.establecer_asociacion(args[0], args[1])
    return 0


def cmd_sueno(cerebro, args):
    cerebro.ciclo_sueno_consolidacion()
    return 0


def cmd_corteza(cerebro, args):
    cerebro.cursor.execute(
        "SELECT concepto, categoria, peso_sinaptico, estado, asociaciones, COALESCE(sustantivos_clave, '') "
        "FROM largo_plazo ORDER BY peso_sinaptico DESC, estado ASC"
    )
    filas = cerebro.cursor.fetchall()
    if not filas:
        print("La corteza esta vacia.")
        return 0

    print(f"{'CONCEPTO':<25} {'CATEGORIA':<12} {'PESO':<6} {'ESTADO':<9} {'SUSTANTIVOS CLAVE':<25} {'ASOCIACIONES'}")
    print("-" * 105)
    for c, cat, peso, est, asoc, sust in filas:
        sust_str = f"[{sust}]" if sust else "-"
        print(f"{c:<25} {str(cat):<12} {peso:<6.2f} {est:<9} {sust_str:<25} {asoc or ''}")
    print("-" * 105)
    print(f"Total: {len(filas)} nodos corticales.")
    return 0


def cmd_listar(cerebro, args):
    """Lista todos los conceptos de la corteza con metadatos y paginacion."""
    pagina = 1
    for i, a in enumerate(args):
        if a == "--pagina" and i + 1 < len(args):
            try:
                pagina = int(args[i + 1])
            except ValueError:
                pass
            break

    limite = 10
    offset = (pagina - 1) * limite

    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo")
    total = cerebro.cursor.fetchone()[0]

    if total == 0:
        print("La corteza esta vacia.")
        return 0

    cerebro.cursor.execute(
        "SELECT concepto, substr(contenido, 1, 200), peso_sinaptico, estado, COALESCE(sustantivos_clave, '') "
        "FROM largo_plazo ORDER BY peso_sinaptico DESC, ultimo_acceso DESC "
        "LIMIT ? OFFSET ?",
        (limite, offset)
    )
    filas = cerebro.cursor.fetchall()

    total_paginas = max(1, (total + limite - 1) // limite)
    print(f"[MemoryBioRAG] Corteza: {total} nodos (pagina {pagina}/{total_paginas})")
    print("=" * 70)

    for concepto, snippet, peso, estado, sust in filas:
        marca = "[ACTIVO]" if estado == "activo" else "[DORMIDO]"
        sust_str = f" · Sustantivos: [{sust}]" if sust else ""
        print(f"  {marca} {concepto} (peso:{peso:.2f}){sust_str}")
        if snippet:
            preview = snippet[:120].replace("\n", " ")
            print(f"         {preview}")
        print()

    print("=" * 70)
    if pagina < total_paginas:
        print(f"Usa --pagina {pagina + 1} para mas resultados.")
    return 0


def cmd_estado(cerebro, args):
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'activo'")
    activos = cerebro.cursor.fetchone()[0]
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE estado = 'dormido'")
    dormidos = cerebro.cursor.fetchone()[0]
    cerebro.cursor.execute("SELECT COUNT(*) FROM corto_plazo")
    corto = cerebro.cursor.fetchone()[0]
    cerebro.cursor.execute("SELECT ROUND(SUM(peso_sinaptico), 2) FROM largo_plazo WHERE estado = 'activo'")
    energia = cerebro.cursor.fetchone()[0] or 0.0

    total_lp = activos + dormidos
    cerebro.cursor.execute("SELECT COUNT(*) FROM largo_plazo WHERE sustantivos_clave IS NOT NULL AND trim(sustantivos_clave) != ''")
    con_sust = cerebro.cursor.fetchone()[0]
    pct = (con_sust / total_lp * 100.0) if total_lp > 0 else 0.0

    print(f"Nodos activos:      {activos}")
    print(f"Nodos dormidos:     {dormidos}")
    print(f"Memoria de trabajo: {corto} items")
    print(f"Energia sinaptica:  {energia}")
    print(f"Nodos con sustantivos clave: {con_sust}/{total_lp} ({pct:.1f}%)")
    return 0


def cmd_comunicar(cerebro, args):
    if len(args) < 2:
        print("Uso: biorag.py comunicar <destino> <mensaje>")
        print("  destino: athena, artemis, hermes, todos")
        print("  Identificate con env AGENT_NAME=athena|artemis|hermes")
        return 1
    origen = os.environ.get("AGENT_NAME", "desconocido")
    destino = args[0]
    mensaje = " ".join(args[1:])
    cerebro.enviar_comunicado(origen, destino, mensaje)
    return 0


def cmd_leer_mensajes(cerebro, args):
    solo_no_leidos = "--no-leidos" in args
    ultimos = 10
    destino = None
    args_limpios = [a for a in args if a != "--no-leidos"]
    for i, a in enumerate(args_limpios):
        if a == "--ultimos" and i + 1 < len(args_limpios):
            try:
                ultimos = int(args_limpios[i + 1])
            except ValueError:
                pass
        if a == "--para" and i + 1 < len(args_limpios):
            destino = args_limpios[i + 1]
    
    agente = os.environ.get('AGENT_NAME', 'desconocido')
    mensajes = cerebro.leer_comunicados(destino=destino, solo_no_leidos=solo_no_leidos, ultimos=ultimos, agente=agente)
    if not mensajes:
        print("No hay mensajes.")
        return 0
    ids_a_marcar = []
    for msg_id, origen, dest, contenido, ts, leido, leido_por in reversed(mensajes):
        # Para mensajes "todos", verificar si agente está en leido_por
        if dest == 'todos':
            leido_agente = f",{agente}," in (leido_por or '')
        else:
            leido_agente = bool(leido)
        marca = "[NO LEIDO]" if not leido_agente else "          "
        fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        print(f"{marca} #{msg_id} {fecha} | {origen} -> {dest}")
        print(f"         {contenido}")
        if dest == 'todos' and leido_por:
            print(f"         Leído por: {leido_por.strip(',').replace(',', ', ')}")
        print()
        if not leido_agente:
            ids_a_marcar.append(msg_id)
    if ids_a_marcar:
        cerebro.marcar_como_leido(ids_a_marcar, agente)
    return 0


def cmd_familiaridad(cerebro, args):
    from middleware.interceptor import escanear_familiaridad
    texto = " ".join(args)
    if not texto:
        print("Uso: biorag.py familiaridad <texto a escanear>")
        return 1
    conceptos = escanear_familiaridad(texto, cerebro)
    if conceptos:
        for c in conceptos:
            print(f"[Nota de Familiaridad: Te resulta familiar el concepto \"{c}\"]")
        return 0
    print("Sin coincidencias de familiaridad.")
    return 0


def cmd_dashboard(cerebro, args):
    """Lanza el dashboard Neuro-Visor (backend + frontend + abre navegador)."""
    import subprocess
    import signal
    import sys
    import time
    import webbrowser
    from pathlib import Path

    project_root = Path(__file__).parent
    dashboard_dir = project_root / "dashboard-neuro-visor"
    backend_dir = dashboard_dir / "backend"

    if not dashboard_dir.exists():
        print(f"Error: No existe {dashboard_dir}")
        return 1
    if not backend_dir.exists():
        print(f"Error: No existe {backend_dir}")
        return 1

    print("[Dashboard] Verificando dependencias...")

    # 1. Python deps (uv sync o pip install)
    try:
        subprocess.run(["uv", "sync"], cwd=project_root, check=False, capture_output=True)
    except FileNotFoundError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=project_root, check=False)

    # 2. Node deps
    try:
        subprocess.run(["npm", "ci"], cwd=dashboard_dir, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("[Dashboard] npm ci falló, intentando npm install...")
        subprocess.run(["npm", "install"], cwd=dashboard_dir, check=False)

    # 3. Lanzar backend
    print("[Dashboard] Iniciando backend en http://localhost:8001 ...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8001"],
        cwd=dashboard_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 4. Lanzar frontend
    print("[Dashboard] Iniciando frontend en http://localhost:3000 ...")
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", "3000", "--host"],
        cwd=dashboard_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 5. Health-check
    def wait_ready(url, name, timeout=30):
        import urllib.request
        start = time.time()
        while time.time() - start < timeout:
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    print("[Dashboard] Esperando health-checks...")
    if not wait_ready("http://localhost:8001/api/corteza/estado", "backend"):
        print("[ERROR] Backend no respondió a tiempo")
        backend_proc.terminate()
        frontend_proc.terminate()
        return 1
    print("[OK] Backend listo")

    if not wait_ready("http://localhost:3000", "frontend"):
        print("[ERROR] Frontend no respondió a tiempo")
        backend_proc.terminate()
        frontend_proc.terminate()
        return 1
    print("[OK] Frontend listo")

    # 6. Abrir navegador
    print("[Dashboard] Abriendo navegador en http://localhost:3000 ...")
    webbrowser.open("http://localhost:3000")

    # 7. Manejar Ctrl+C limpio
    def shutdown(signum, frame):
        print("\n[Dashboard] Apagando...")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
            frontend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
            frontend_proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 8. Mantener vivo y mostrar logs
    print("[Dashboard] Listo. Presiona Ctrl+C para detener.")
    try:
        while True:
            # Leer stdout/stderr no bloqueante
            for proc, name in [(backend_proc, "backend"), (frontend_proc, "frontend")]:
                line = proc.stdout.readline()
                if line:
                    print(f"[{name}] {line.decode().rstrip()}")
                err = proc.stderr.readline()
                if err:
                    print(f"[{name} ERROR] {err.decode().rstrip()}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        shutdown(None, None)

    return 0


def main():
    from core.cli import dispatch_early
    early_result = dispatch_early(sys.argv[1:])
    if early_result is not None:
        return early_result

    comando = sys.argv[1]
    args = sys.argv[2:]

    cerebro = SQLiteMemoryBioRAG(db_path=DB_PATH)

    comandos = {
        "buscar": cmd_buscar,
        "guardar": cmd_guardar,
        "asociar": cmd_asociar,
        "sueno": cmd_sueno,
        "corteza": cmd_corteza,
        "estado": cmd_estado,
        "familiaridad": cmd_familiaridad,
        "comunicar": cmd_comunicar,
        "leer_mensajes": cmd_leer_mensajes,
        "listar": cmd_listar,
        "dashboard": cmd_dashboard,
        "sustantivos": cmd_sustantivos,
        "sustantivo": cmd_sustantivos,
        "agregar_sustantivos": cmd_agregar_sustantivos,
        "agregar-sustantivos": cmd_agregar_sustantivos,
        "asignar_sustantivos": cmd_agregar_sustantivos,
        "asignar-sustantivos": cmd_agregar_sustantivos,
    }

    if comando in ("help", "--help", "-h"):
        print(__doc__)
        return 0

    if comando not in comandos:
        print(f"Comando desconocido: {comando}. Usa 'python3 biorag.py help' para ver la ayuda completa.")
        cerebro.cerrar_sistema()
        return 1

    try:
        resultado = comandos[comando](cerebro, args)
        cerebro.cerrar_sistema()
        return resultado
    except Exception as e:
        print(f"Error: {e}")
        cerebro.cerrar_sistema()
        return 1


if __name__ == "__main__":
    sys.exit(main())
