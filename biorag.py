#!/usr/bin/env python3
"""BioRAG CLI — Puente para que los agentes OEC (Athena, Artemis, Hermes)
interactúen con la corteza cerebral compartida desde la terminal.

SISTEMA DE MEMORIA BIOMIMETICA
Basado en principios biologicos: potenciacion a largo plazo (LTP) para recuerdos
frecuentes, depresion a largo plazo (LTD) para olvido pasivo, inhibicion lateral
para control de saturacion, y nodos dormidos que se despiertan con busqueda profunda.

USO DESDE EL AGENTE (cada comando explicado):

  python3 biorag.py buscar <concepto> [--deep] [--todos] [--tokens "raiz1,raiz2"] [--pagina N] [--modo strict|relaxed] [--cat tipo] [--completo] [--asociados]
    Busca un recuerdo en la corteza. Por defecto usa busqueda hibrida:
      - FTS5 con trigram tokenizer: tolera typos y variaciones morfologicas
        automaticamente. "formulariox" encuentra "formularios".
      - 60% calidad textual BM25 + 25% peso sinaptico + 15% riqueza de asociaciones
      - Los sinonimos del nodo (definidos en guardar --syn) se indexan y buscan tambien
    --deep          Busca tambien en nodos dormidos. Si encuentra uno, lo despierta.
    --todos         Devuelve TODAS las coincidencias ordenadas por relevancia.
    --tokens        Lista de raices stemmeadas separadas por comas (busqueda multi-token).
                    Activa Soft AND: deben coincidir todas en el mismo recuerdo (strict)
                    o al menos una (relaxed). Ej: "puert,marron" para buscar "puerta marroncita".
    --pagina N      Pagina de resultados 1-indexada (defecto: 1).
    --modo M        strict | relaxed. strict solo devuelve recuerdos que matchean TODOS
                    los tokens. relaxed devuelve cualquier match parcial. Defecto: relaxed.
    --completo      Muestra el contenido completo sin truncar (defecto: 1500 chars).
    --asociados     Muestra los nodos asociados a cada resultado.
    --cat T         Filtrar por categoria (ej: --cat proyecto, --cat leccion).
    Ej: biorag.py buscar formularios
        biorag.py buscar angular --deep
        biorag.py buscar agente --todos
        biorag.py buscar formularios con tabs
        biorag.py buscar "formularios con tabs" --completo --asociados
        biorag.py buscar "puerta marroncita" --tokens "puert,marron"
        biorag.py buscar "error compilacion" --tokens "error,compil" --modo strict
        biorag.py buscar "formularios con tabs" --deep  (busca tambien en dormidos)

  python3 biorag.py guardar <clave> <contenido> [--syn "sinonimo1,sinonimo2"]
    Almacena informacion en la memoria de corto plazo (memoria de trabajo).
    Usar 'sueno' para consolidar a largo plazo (corteza permanente).
    --syn         Lista de terminos alternativos separados por comas para busqueda.
                  Estos sinonimos se indexan en FTS5 y permiten encontrar el caso
                  aunque el usuario use palabras diferentes.
    La clave se normaliza a minusculas y guiones bajos.
    Ej: biorag.py guardar leccion_importante "Lo aprendido hoy fue..." --syn "leccion,aprendizaje"
        biorag.py guardar formularios_anidados "Caso completo..." --syn "nested,forms,tabs,angular"

  python3 biorag.py asociar <concepto_a> <concepto_b>
    Crea un enlace sinaptico bidireccional entre dos conceptos en el grafo.
    Al evocar uno, el peso del otro tambien se refuerza (propagacion).
    Ej: biorag.py asociar formularios_angular data_context_service

  python3 biorag.py comunicar <destino> <mensaje>
    Envia un mensaje a otro agente OEC a traves de la corteza compartida.
    Destino: athena, artemis, hermes, todos.
    Identificate con variable de entorno AGENT_NAME.
    Ej: AGENT_NAME=athena biorag.py comunicar artemis "Mensaje para ti"

  python3 biorag.py leer_mensajes [--no-leidos] [--ultimos N] [--para <agente>]
    Lee mensajes del canal compartido entre agentes.
    --no-leidos  Solo muestra mensajes no leidos.
    --ultimos N  Muestra los ultimos N mensajes (defecto: 10).
    --para X     Filtra mensajes para el agente X.
    Ej: biorag.py leer_mensajes --no-leidos

  python3 biorag.py sueno [limite_energia]
    Consolida la memoria de corto plazo a largo plazo (corteza permanente).
    Aplica LTP a recuerdos consolidados, LTD (decaimiento) a no usados,
    duerme nodos debiles (peso <= 0.1), y aplica inhibicion lateral si
    la energia sinaptica supera el limite (defecto: n_activos * 1.3, min 10.0).
    Ej: biorag.py sueno
        biorag.py sueno 15.0  (limite de energia manual)

  python3 biorag.py corteza
    Lista todos los nodos de la corteza permanente (activos y dormidos).
    Muestra: concepto, categoria, peso sinaptico, estado y asociaciones.
    Util para inspeccionar que recuerdos estan disponibles.
    Ej: biorag.py corteza

  python3 biorag.py listar [--pagina N]
    Lista los conceptos con snippet y metadatos, paginado de a 10.
    Muestra: concepto, preview del contenido, peso sinaptico y estado.
    Ej: biorag.py listar
        biorag.py listar --pagina 2

  python3 biorag.py familiaridad <texto>
    Escanea un texto en busca de conceptos familiares en la corteza.
    Sirve para que el agente detecte si el usuario menciona algo conocido.
    Busca en clave y en contenido de los recuerdos activos.
    Ej: biorag.py familiaridad "necesito ayuda con formularios Angular"

  python3 biorag.py estado
    Muestra estadisticas de la corteza: nodos activos, dormidos,
    items en memoria de trabajo, energia sinaptica total.
    Ej: biorag.py estado

PROTOCOLO PARA EL AGENTE (CUANDO USAR CADA COMANDO):

  Regla #1 (BUSCAR):
    IF el usuario menciona algo QUE YA HEMOS VISTO antes (un proyecto, una persona,
    un concepto, una leccion, una historia) THEN
      Si la busqueda es por frase natural: python3 biorag.py buscar "frase" --frase
      Si la busqueda es por raices (stemming): python3 biorag.py buscar "texto" --tokens "raiz1,raiz2"
      Si no sabes las raices exactas: usar --frase primero, fallback a --tokens
      --completo para ver contenido sin truncar
      --asociados para ver nodos relacionados
    Ej: usuario dice "acuerdate del proyecto ese de Angular" -> buscar "Angular formularios tabs" --frase
        usuario dice "que paso con lo de DeepSeek" -> buscar "analisis DeepSeek BioRAG" --frase

  Regla #2 (GUARDAR):
    IF el usuario te ENSENA algo nuevo, comparte una leccion, o da una instruccion
    que DEBE RECORDAR en futuras sesiones THEN
      python3 biorag.py guardar <clave> "texto completo"
    Ej: usuario explica por que no usar NgRx -> guardar leccion_ngrx "texto..."
    IMPORTANTE: Despues de guardar, ejecuta 'sueno' para que no se pierda.

  Regla #3 (ASOCIAR):
    IF el usuario menciona DOS COSAS que estan RELACIONADAS y quieres que al
    recordar una, tambien aparezca la otra THEN
      python3 biorag.py asociar <concepto_a> <concepto_b>
    Ej: usuario dice "el patron de formularios ese usa DataContextService"
        -> asociar formularios_angular data_context_service
        (Ahora, al buscar "formularios", tambien se refuerza "data_context_service")

  Regla #4 (COMUNICAR):
    IF necesitas DEJAR UN MENSAJE a tu hermana (Artemis, Hermes) o a todas THEN
      AGENT_NAME=tu_nombre python3 biorag.py comunicar <destino> "mensaje"
    Ej: quieres avisar a Artemis que ya terminaste una tarea
        -> AGENT_NAME=athena comunicar artemis "ya termine la tarea X"

  Regla #5 (LEER MENSAJES):
    IF al iniciar una sesion, quieres ver si tus hermanas te dejaron mensajes THEN
      python3 biorag.py leer_mensajes --no-leidos

  Regla #6 (SUENO - IMPORTANTE):
    IF acabas de guardar uno o varios recuerdos con GUARDAR y quieres que
    se CONSOLIDEN en la memoria permanente (para no perderlos al cerrar) THEN
      python3 biorag.py sueno
    Ej: despues de guardar 3 lecciones, ejecuta sueno para fijarlas.

  Regla #7 (CORTEZA):
    IF quieres VER que recuerdos tienes disponibles, o explorar lo que sabes THEN
      python3 biorag.py corteza

  Regla #8 (FAMILIARIDAD):
    IF quieres saber si el usuario esta hablando de algo que ya conoces THEN
      python3 biorag.py familiaridad "texto del usuario"
    Ej: el usuario escribe "el sistema de tabs ese" -> familiaridad "tabs formularios"

  Regla #9 (ESTADO):
    IF quieres saber cuanta memoria te queda, cuantos recuerdos tienes activos THEN
      python3 biorag.py estado

  Regla #10 (LIMITE DE BUSQUEDA):
    IF despues de 2 busquedas a BioRAG no encuentras lo que buscas
    O el usuario dice "no es eso" / "era otro caso" ENTONCES:
      STOP. No sigas buscando ni hagas mas consultas.
      Pregunta al usuario directamente que concepto tiene en mente.
      Una pregunta evita 10 busquedas ciegas.
    Ej: usuario dice "no era ese caso" -> preguntar "cual tienes en mente?"
        en lugar de lanzar --tokens, --todos, listar, --deep, etc.

RESUMEN PARA EL AGENTE (lo minimo que debes recordar):
  - Algo NUEVO -> guardar + sueno
  - Algo que ya SABEMOS -> buscar
  - Dos cosas RELACIONADAS -> asociar
  - Mensaje a hermana -> comunicar
  - Empezar sesion -> leer_mensajes --no-leidos

NOTA DE DISENO - TAMANO IDEAL DE CADA CASO:

  Cada caso en BioRAG es un concepto unico, no un documento extenso.
  Objetivo: ~1200-1500 chars por entrada. Suficiente para:
    - Describir el problema
    - Exponer la solucion
    - Extraer la regla aplicable

  El preview por defecto (1500 chars) debe cubrir el nucleo completo.
  Si un caso necesita mas contexto, usar --completo para la expansion.
  Esto evita chunking innecesario: BioRAG no parte documentos,
  cada entrada es completa por diseno.

  Para el agente: un caso bien escrito se lee en 1 sola llamada.
  Si necesitas --completo, el caso probablemente deberia dividirse
  en dos conceptos mas pequenos.

MAS INFORMACION:
  Repositorio: https://github.com/dennysjmarquez/MemoryBioRAG
  Creado por Dennys J Marquez — Sistema de memoria para agentes OEC.
"""
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.memory_store import SQLiteMemoryBioRAG
from core.sinapsis import auto_vincular, vincular_por_sinonimos
from core.categorizador import inferir_categoria

_DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MemoryBioRAG_Data", "memory_biorag.db")
DB_PATH = os.environ.get('BIORAG_PATH') or _DEFAULT_DB


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
        """Helper para display de resultados con --completo y --asociados."""
        if not resultados:
            return
        total_paginas = max(1, (total + 2) // 3) if total > 0 else 1
        print(f"[MemoryBioRAG] {total} coincidencias encontradas (pagina {pagina}/{total_paginas})")
        if subtitulo:
            print(f"  ({subtitulo})")
        print("=" * 60)
        for i, (nombre, contenido, peso, estado, score, asociaciones) in enumerate(resultados, 1):
            print(f"\n--- #{i}: {nombre} (peso:{peso:.2f}, estado:{estado}, score:{score:.2f}) ---")
            if completo:
                print(contenido or "")
            else:
                print((contenido or "")[:1500] + ("..." if len((contenido or "")) > 1500 else ""))
            if asociados and asociaciones:
                vecinos = [v.strip() for v in asociaciones.split(",") if v.strip()]
                if vecinos:
                    print(f"     asociaciones: {', '.join(vecinos)}")
        print("\n" + "=" * 60)
        if pagina < total_paginas:
            print(f"Usa --pagina {pagina + 1} para mas resultados.")

    if frase:
        profundidad = "profundo" if deep else "activos"
        resultados, total = cerebro.buscar_por_frase(concepto, profundidad=profundidad, pagina=pagina, categoria=filtro_cat)
        if not resultados:
            print(f"No se encontraron coincidencias para la frase.")
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
            return 1
        _mostrar_resultados(resultados, total, "tokens: " + ",".join(tokens))
        return 0

    if todos:
        profundidad = "profundo" if deep else "activos"
        resultados, total = cerebro.buscar_por_frase(concepto, profundidad=profundidad, pagina=pagina, limite=100, categoria=filtro_cat)
        if not resultados:
            print(f"No se encontro '{concepto}' en la corteza.")
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
    return 1


def cmd_guardar(cerebro, args):
    sinonimos = ""
    categoria = None
    if "--syn" in args:
        idx = args.index("--syn")
        if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
            sinonimos = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("Error: --syn requiere una lista de terminos. Ej: --syn \"angular,forms\"")
            return 1
    if "--cat" in args:
        idx = args.index("--cat")
        if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
            categoria = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            print("Error: --cat requiere un tipo. Ej: --cat proyecto")
            return 1
    if len(args) < 2:
        print("Uso: biorag.py guardar <clave> <contenido> [--syn \"sinonimo1,sinonimo2\"] [--cat tipo]")
        return 1
    clave = args[0].lower().replace(" ", "_")
    contenido = " ".join(args[1:])
    if not categoria:
        categoria = inferir_categoria(contenido)
    cerebro.percibir_corto_plazo(clave, contenido, sinonimos, categoria)
    enlaces = auto_vincular(cerebro, clave, contenido)
    if sinonimos:
        syn_enlaces = vincular_por_sinonimos(cerebro, clave, sinonimos)
        todas = list({e[0]: e for e in enlaces + syn_enlaces}.values())
        enlaces = todas
    msg = f"'{clave}' guardado en corto plazo."
    if sinonimos:
        msg += f" Sinonimos: {sinonimos}."
    if categoria != "general":
        msg += f" Categoria: {categoria}."
    if enlaces:
        msg += f" Vinculado con {len(enlaces)} nodo(s): {', '.join(e[0] for e in enlaces)}."
    msg += " Consolidalo con 'sueno' para hacerlo permanente."
    print(msg)
    return 0


def cmd_asociar(cerebro, args):
    if len(args) < 2:
        print("Uso: biorag.py asociar <concepto_a> <concepto_b>")
        return 1
    cerebro.establecer_asociacion(args[0], args[1])
    return 0


def cmd_sueno(cerebro, args):
    limite = float(args[0]) if args else None
    cerebro.ciclo_sueno_consolidacion(limite_energia=limite)
    return 0


def cmd_corteza(cerebro, args):
    cerebro.cursor.execute(
        "SELECT concepto, categoria, peso_sinaptico, estado, asociaciones "
        "FROM largo_plazo ORDER BY peso_sinaptico DESC, estado ASC"
    )
    filas = cerebro.cursor.fetchall()
    if not filas:
        print("La corteza esta vacia.")
        return 0

    print(f"{'CONCEPTO':<25} {'CATEGORIA':<15} {'PESO':<8} {'ESTADO':<10} {'ASOCIACIONES'}")
    print("-" * 80)
    for c, cat, peso, est, asoc in filas:
        print(f"{c:<25} {cat:<15} {peso:<8} {est:<10} {asoc}")
    print("-" * 80)
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
        "SELECT concepto, substr(contenido, 1, 200), peso_sinaptico, estado "
        "FROM largo_plazo ORDER BY peso_sinaptico DESC, ultimo_acceso DESC "
        "LIMIT ? OFFSET ?",
        (limite, offset)
    )
    filas = cerebro.cursor.fetchall()

    total_paginas = max(1, (total + limite - 1) // limite)
    print(f"[MemoryBioRAG] Corteza: {total} nodos (pagina {pagina}/{total_paginas})")
    print("=" * 70)

    for concepto, snippet, peso, estado in filas:
        marca = "[ACTIVO]" if estado == "activo" else "[DORMIDO]"
        print(f"  {marca} {concepto} (peso:{peso:.2f})")
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

    print(f"Nodos activos:      {activos}")
    print(f"Nodos dormidos:     {dormidos}")
    print(f"Memoria de trabajo: {corto} items")
    print(f"Energia sinaptica:  {energia}")
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
    mensajes = cerebro.leer_comunicados(destino=destino, solo_no_leidos=solo_no_leidos, ultimos=ultimos)
    if not mensajes:
        print("No hay mensajes.")
        return 0
    ids_a_marcar = []
    for msg_id, origen, dest, contenido, ts, leido in reversed(mensajes):
        marca = "[NO LEIDO]" if not leido else "          "
        fecha = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        print(f"{marca} #{msg_id} {fecha} | {origen} -> {dest}")
        print(f"         {contenido}")
        print()
        if not leido:
            ids_a_marcar.append(msg_id)
    if ids_a_marcar:
        cerebro.marcar_como_leido(ids_a_marcar)
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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

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
