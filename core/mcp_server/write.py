"""Deuda técnica trasladada intacta: submódulo de escritura MCP.

Expone tools de escritura y aprendizaje en BioRAG:
- aprender
- guardar
- agregar_sustantivos
- sustantivos
- actualizar
"""

import json
import re
import time
from typing import Annotated, Any, Optional

from pydantic import Field

from core.mcp_server._shared import (
    VENTANA_CORRECCION,
    _get_cerebro,
    _interceptar,
    _resolver_dimensiones,
    _sesiones_activas,
)
from core.categorizador import inferir_categoria
from core.sinapsis import (
    _peso_similitud,
    _tokenizar,
    auto_vincular,
    vincular_por_sinonimos,
)


# HELPER: Búsqueda retroactiva de nodos viejos relacionados
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

    # Ordenar por similitud descendente
    resultados.sort(key=lambda x: x[3], reverse=True)
    return resultados[:top_k]


def _aprender_impl(
    concepto: str,
    contenido: str,
    bridges: Any,
    syn: Optional[str] = None,
    cat: Optional[str] = None,
    dimensiones: Optional[Any] = None,
    predicados: Optional[Any] = None,
    valencia_somatica: Optional[float] = None,
    sustantivos_clave: Optional[str] = None,
    busqueda_previa: bool = False,
    vincular_con: Optional[Any] = None,
) -> str:
    clave = concepto.lower().replace(" ", "_")

    # ── VALIDACIÓN OBLIGATORIA (INVARIANTE) — Pre-flight Search ─────
    # Rechazar de inmediato si el agente no confirmó la búsqueda previa.
    # No se evalúa ningún otro parámetro ni se accede a la base de datos.
    if busqueda_previa is not True:
        return json.dumps({
            "status": "error",
            "codigo": "BUSQUEDA_PREVIA_REQUERIDA",
            "mensaje": (
                f"❌ BÚSQUEDA PREVIA REQUERIDA — el nodo '{clave}' NO fue guardado.\n\n"
                "INVARIANTE BIORAG: Ningún agente puede guardar o aprender información sin antes verificar "
                "si ya existe o se relaciona con conocimientos previos en la memoria.\n\n"
                "FLUJO OBLIGATORIO (3 pasos):\n"
                "  1. Llamá primero a `biorag_buscar` o `biorag_recordar` con la consulta del tema a guardar.\n"
                "  2. Evaluá los resultados:\n"
                "     • Si ya existe un nodo idéntico/complementario → usá `biorag_actualizar`.\n"
                "     • Si el tema es nuevo pero se relaciona con existentes → usá `biorag_aprender` con `vincular_con`.\n"
                "     • Si es un tema completamente independiente → usá `biorag_aprender` con `busqueda_previa=True`.\n"
                "  3. Repetí la llamada a `biorag_aprender` pasando explícitamente `busqueda_previa=True`.\n\n"
                "ACCIÓN REQUERIDA: Realizá la búsqueda previa y reintentá con `busqueda_previa=True`."
            ),
            "concepto": clave,
            "parametro_faltante": "busqueda_previa",
        }, ensure_ascii=False)

    # ── VALIDACIÓN OBLIGATORIA — ANTES de tocar la DB ──────────────
    # Rechazar acá, antes de percibir_corto_plazo(), significa que un
    # intento fallido no deja ningún estado a medias: el agente reintenta
    # con el mismo concepto/contenido y bridges corregidos, sin duplicados
    # ni nodos huérfanos.
    #
    # CASO ESPECIAL — bridges ausente (None):
    # Cuando el agente omite bridges por completo, Pydantic lo deja pasar
    # (bridges=None) en lugar de rechazar la llamada con un error de schema
    # que el agente no puede interpretar. Aquí emitimos un error accionable
    # que confirma qué llegó bien y solo pide los bridges, para que el
    # agente repita la llamada COMPLETA con todos los parámetros.
    from core.concept_hub import validar_bridges
    if bridges is None:
        return json.dumps({
            "status": "error",
            "codigo": "BRIDGES_AUSENTES",
            "mensaje": (
                f"❌ BRIDGES AUSENTES — el nodo '{clave}' NO fue guardado.\n\n"
                "Los parámetros concepto, contenido, dimensiones y syn ya llegaron correctamente. "
                "Solo falta el parámetro obligatorio 'bridges'.\n\n"
                "ACCIÓN REQUERIDA: repetí la llamada a biorag_aprender con TODOS los mismos parámetros "
                "más el campo bridges. No es necesario cambiar nada más — solo añadí bridges.\n\n"
                "Se requieren exactamente 5 bridges cubriendo los 5 ángulos semánticos distintos:\n"
                "  1. 'sinonimo': mismo significado con otro vocabulario\n"
                "  2. 'problema': dolor o falla que resuelve este nodo\n"
                "  3. 'solucion': técnica o herramienta que aplica este nodo\n"
                "  4. 'situacion': caso de uso, rol o contexto de búsqueda\n"
                "  5. 'ingenuo': búsqueda sin tecnicismos (cómo lo googlearía un novato)\n\n"
                "FORMATO — lista de 5 dicts obligatorios:\n"
                "bridges=[\n"
                "  {'text': 'modo reposo del sistema de memoria', 'angle': 'sinonimo'},\n"
                "  {'text': 'proceso que genera ideas en silencio', 'angle': 'problema'},\n"
                "  {'text': 'hilos de pensamiento espontaneo', 'angle': 'solucion'},\n"
                "  {'text': 'cerebro piensa solo cuando nadie pregunta', 'angle': 'situacion'},\n"
                "  {'text': 'que pasa cuando no hay actividad en BioRAG', 'angle': 'ingenuo'}\n"
                "]"
            ),
            "concepto": clave,
            "parametros_recibidos_ok": ["concepto", "contenido", "dimensiones", "syn", "cat"],
            "parametro_faltante": "bridges",
        }, ensure_ascii=False)

    bridges_validos, bridges_rechazados = validar_bridges(bridges, clave)
    if len(bridges_validos) != 5:
        return json.dumps({
            "status": "error",
            "codigo": "BRIDGES_INVALIDOS",
            "mensaje": (
                f"❌ Bridges inválidos ({len(bridges_validos)}/5 válidos) — el nodo '{clave}' NO fue guardado.\n\n"
                + (f"Motivos de rechazo: {'; '.join(bridges_rechazados)}.\n\n" if bridges_rechazados else "")
                + "ACCIÓN REQUERIDA: repetí la llamada a biorag_aprender con TODOS los mismos parámetros "
                "y corregí los bridges rechazados. No cambies concepto, contenido ni dimensiones.\n\n"
                "Se requieren exactamente 5 bridges válidos cubriendo los 5 ángulos semánticos distintos:\n"
                "  1. 'sinonimo': mismo significado con otro vocabulario\n"
                "  2. 'problema': dolor o falla que resuelve este nodo\n"
                "  3. 'solucion': técnica o herramienta que aplica este nodo\n"
                "  4. 'situacion': caso de uso, rol o contexto de búsqueda\n"
                "  5. 'ingenuo': búsqueda sin tecnicismos (cómo lo googlearía un novato)\n\n"
                "FORMATO — lista de 5 dicts obligatorios:\n"
                "bridges=[\n"
                "  {'text': 'modo reposo del sistema de memoria', 'angle': 'sinonimo'},\n"
                "  {'text': 'proceso que genera ideas en silencio', 'angle': 'problema'},\n"
                "  {'text': 'hilos de pensamiento espontaneo', 'angle': 'solucion'},\n"
                "  {'text': 'cerebro piensa solo cuando nadie pregunta', 'angle': 'situacion'},\n"
                "  {'text': 'que pasa cuando no hay actividad en BioRAG', 'angle': 'ingenuo'}\n"
                "]"
            ),
            "concepto": clave,
            "parametros_recibidos_ok": ["concepto", "contenido", "dimensiones", "syn", "cat"],
            "bridges_validos_recibidos": len(bridges_validos),
            "bridges_rechazados": bridges_rechazados,
        }, ensure_ascii=False)

    # ── VALIDACIÓN OBLIGATORIA — sustantivos_clave (T3 spec 001) ────────
    # Fail-fast ANTES de _get_cerebro() (Algoritmo A del plan 001): si el
    # intento falla aquí, NO se abre la DB ni se escribe nada. El agente
    # reintenta repitiendo la llamada completa solo añadiendo el campo.
    #
    # REGLA DE ORO DE RECUPERABILIDAD: un nodo sin sustantivos_clave es un
    # recuerdo sin centro de gravedad temático — solo lo encontraría la
    # búsqueda textual. Los sustantivos son el "de QUÉ TRATA" y garantizan
    # el boost BM25 (peso 4.0x) en recordar. Exigirlos obliga al agente a
    # pensar en la esencia del nodo antes de guardarlo.
    if not sustantivos_clave or not str(sustantivos_clave).strip():
        return json.dumps({
            "status": "error",
            "codigo": "SUSTANTIVOS_CLAVE_AUSENTES",
            "mensaje": (
                f"❌ SUSTANTIVOS_CLAVE_AUSENTES — el nodo '{clave}' NO fue guardado.\n\n"
                "Los parámetros concepto, contenido, dimensiones, syn y bridges ya llegaron correctamente. "
                "Solo falta el parámetro obligatorio 'sustantivos_clave'.\n\n"
                "ACCIÓN REQUERIDA: repetí la llamada a biorag_aprender con TODOS los mismos parámetros "
                "más el campo sustantivos_clave. No es necesario cambiar nada más — solo añadí "
                "sustantivos_clave.\n\n"
                "Protocolo: ¿De QUÉ TRATA este nodo? Identificá 2 a 10 sustantivos centrales. "
                "Formato: 'servidor,backend,timeout,conexion'"
            ),
            "concepto": clave,
            "parametros_recibidos_ok": ["concepto", "contenido", "dimensiones", "syn", "cat", "bridges"],
            "parametro_faltante": "sustantivos_clave",
        }, ensure_ascii=False)

    # Normalizar (RF-10) + auto-dedup preservando orden (RF-14) ANTES de validar
    # cantidad: los duplicados se eliminan y luego se evalúa el número de únicos.
    from core.memory_store import normalizar_sustantivos_clave
    sustantivos_norm = normalizar_sustantivos_clave(str(sustantivos_clave))
    sk_unicos = [t for t in sustantivos_norm.split(",") if t] if sustantivos_norm else []

    # Cantidad (RF-2, RF-9): entre 2 a 10 términos únicos tras dedup
    if len(sk_unicos) < 2 or len(sk_unicos) > 10:
        return json.dumps({
            "status": "error",
            "codigo": "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA",
            "mensaje": (
                f"❌ SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA — el nodo '{clave}' NO fue guardado.\n\n"
                "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA: se requieren entre 2 a 10 términos "
                f"únicos; se recibió {len(sk_unicos)} tras deduplicar. "
                "Formato: 'servidor,backend,timeout,conexion'"
            ),
            "concepto": clave,
            "cantidad_recibida": len(sk_unicos),
        }, ensure_ascii=False)

    # Formato por término (RF-3): 2-15 chars inclusivos, sin espacios, solo
    # alfanuméricos + guion bajo. La ñ se preserva (RF-10) y es alfanumérica
    # en español — por eso se incluye explícitamente en la clase de caracteres.
    for _sk_term in sk_unicos:
        if not re.fullmatch(r"[a-z0-9_ñ]{2,15}", _sk_term):
            return json.dumps({
                "status": "error",
                "codigo": "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO",
                "mensaje": (
                    f"❌ SUSTANTIVOS_CLAVE_FORMATO_INVALIDO — el nodo '{clave}' NO fue guardado.\n\n"
                    f"SUSTANTIVOS_CLAVE_FORMATO_INVALIDO: el término '{_sk_term}' no cumple formato "
                    "(2-15 chars, sin espacios, solo alfanuméricos y guion bajo)."
                ),
                "concepto": clave,
                "termino_invalido": _sk_term,
            }, ensure_ascii=False)

    cerebro = _get_cerebro()
    try:
        clave = concepto.lower().replace(" ", "_")
        categoria = cat or inferir_categoria(contenido)
        val_somatica = float(valencia_somatica or 0.0)
        if categoria and str(categoria).lower() in ('principle', 'protocol'):
            val_somatica = 1.0
        try:
            cerebro._resolver_categoria_id(categoria)
        except ValueError as e:
            return json.dumps({
                "status": "error",
                "mensaje": str(e),
            }, ensure_ascii=False)

        # Parsear dimensiones via helper compartido
        dimensiones_dict, _, dim_error, dim_meta = _resolver_dimensiones(cerebro, dimensiones)
        if dim_error:
            return dim_error

        # Parsear predicados SRL v16.0
        predicados_list = None
        if predicados:
            try:
                predicados_list = json.loads(predicados) if isinstance(predicados, str) else predicados
                if isinstance(predicados_list, str):
                    try:
                        predicados_list = json.loads(predicados_list)
                    except Exception:
                        pass
                if not isinstance(predicados_list, list):
                    predicados_list = [predicados_list]
            except (json.JSONDecodeError, TypeError):
                predicados_list = None

        cerebro.percibir_corto_plazo(clave, contenido, syn or "", categoria, dimensiones_dict, predicados=predicados_list, valencia_somatica=val_somatica, sustantivos_clave=sustantivos_norm)

        enlaces = auto_vincular(cerebro, clave, contenido)
        sinapsis_count = len(enlaces)

        if syn:
            syn_enlaces = vincular_por_sinonimos(cerebro, clave, syn)
            todas = list({e[0]: e for e in enlaces + syn_enlaces}.values())
            sinapsis_count = len(todas)

        # ── VINCULAR_CON (T3 Spec 004): Enlace sináptico explícito en aprendizaje ──
        vinculos_creados = []
        if vincular_con:
            raw_vinculos = []
            if isinstance(vincular_con, str):
                vinc_str = vincular_con.strip()
                if vinc_str.startswith("["):
                    try:
                        parsed = json.loads(vinc_str)
                        if isinstance(parsed, list):
                            raw_vinculos = [str(x) for x in parsed if x]
                    except Exception:
                        raw_vinculos = [s for s in vinc_str.split(",") if s.strip()]
                else:
                    raw_vinculos = [s for s in vinc_str.split(",") if s.strip()]
            elif isinstance(vincular_con, (list, tuple, set)):
                raw_vinculos = [str(x) for x in vincular_con if x]

            for item in raw_vinculos:
                target = item.lower().replace(" ", "_").strip()
                if not target or target == clave:
                    continue
                try:
                    cerebro.establecer_asociacion(clave, target)
                    vinculos_creados.append(target)
                except Exception:
                    pass

            if vinculos_creados:
                sinapsis_count += len(vinculos_creados)

        msg = f"'{clave}' aprendido en corto plazo."
        if syn:
            msg += f" Sinonimos: {syn}."
        if categoria != "general":
            msg += f" Categoria: {categoria}."
        if vinculos_creados:
            msg += f" Vinculado explícitamente con: {', '.join(vinculos_creados)}."
        elif sinapsis_count:
            msg += f" Vinculado con {sinapsis_count} nodo(s)."
        # Dimensiones auto-creadas → confirmar al agente
        if dim_meta.get("dimensiones_creadas"):
            msg += f" Dimensiones nuevas auto-creadas: {', '.join(dim_meta['dimensiones_creadas'])} (auto_generada=1, confianza=0.7)."
        msg += " Usa 'consolidar' para fijar a largo plazo."

        # ── WARNING DE VINCULACIÓN ──────────────────────────────────
        _warnings = []
        if sinapsis_count == 0:
            _warnings.append(f"⚠️ sinapsis=0 — '{clave}' no tiene conexiones. ¿Hay nodos relacionados? Vinculalos con biorag_vincular().")

        # Buscar nodos similares para sugerir vinculación
        _sugerencias = []
        try:
            # Dividir por underscores y guiones, luego filtrar tokens cortos
            tokens = set(t for t in re.split(r'[_\-\s]+', clave.lower()) if len(t) > 2)
            if len(tokens) > 1:
                # Buscar nodos que compartan tokens con el concepto
                condiciones = " OR ".join(["concepto LIKE ?" for _ in tokens])
                params_sug = [f"%{t}%" for t in tokens]
                cerebro.cursor.execute(
                    f"SELECT concepto FROM largo_plazo WHERE ({condiciones}) AND concepto != ? LIMIT 5",
                    params_sug + [clave]
                )
                _sugerencias = [r[0] for r in cerebro.cursor.fetchall() if r[0] != clave]
        except Exception:
            pass

        if _sugerencias:
            _warnings.append(f"⚠️ ¿'{clave}' tiene relación con estos nodos? Si sí, vinculalos: {', '.join(_sugerencias[:3])}")
        else:
            _warnings.append(f"⚠️ ¿'{clave}' tiene relación con otros nodos existentes? Si sí, vinculalos ANTES de consolidar.")

        # ── WARNING DE SYN (sin sinónimos el nodo es invisible) ─────
        if not syn:
            _warnings.append(
                f"⚠️ syn=None — Sin sinónimos, '{clave}' solo es visible por nombre exacto. "
                "Nadie que busque con otras palabras lo encontrará. "
                "Si consolidás sin syn, el nodo queda enterrado. "
                "Poné mínimo 5 sinónimos cubriendo: literal, relacionado, abstracto."
            )
            _warnings.append(
                "  Ejemplo de syn para este nodo:\n"
                "    syn='versión actual,latest,changelog,novedades,release notes'"
            )
        else:
            syn_terms = [s.strip() for s in syn.split(",") if s.strip()]
            syn_capas = {"literal": set(), "relacionado": set(), "abstracto": set()}
            for t in syn_terms:
                if any(kw in t.lower() for kw in [clave.lower().split("_")[0]]):
                    syn_capas["literal"].add(t)
            if len(syn_terms) == 0:
                _warnings.append(
                    f"⚠️ syn vacío — '{clave}' tiene syn pero sin términos. "
                    "Cada sinónimo es una arista de búsqueda. Poné todos los que el contenido justifique (mínimo 8)."
                )
            elif len(syn_terms) < 5:
                _warnings.append(
                    f"⚠️ syn insuficiente ({len(syn_terms)} términos) — "
                    "mínimo 8. Sin suficientes sinónimos, "
                    "el nodo queda como isla invisible. Revisá las 5 capas: Identidad, Dominio, Asociación, Problema, Búsqueda Ingenua."
                )
            elif len(syn_terms) < 8:
                _warnings.append(
                    f"⚠️ syn bajo ({len(syn_terms)} términos) — "
                    "ideal mínimo 8. Cada sinónimo que omitís es un camino de búsqueda que se cierra. "
                    "Extraé TODOS los que el contenido justifique."
                )

        # ── TIP DE PREDICADOS SRL (v16.0) ─────
        if not predicados:
            kw_srl = ["regla", "protocolo", "decision", "estableci", "creo", "autor", "prohibi", "fijo", "aprobo", "decidio", "hito", "leccion"]
            if any(kw in (clave + " " + contenido).lower() for kw in kw_srl):
                _warnings.append(
                    "💡 Tip SRL (Predicados): Este nodo expresa una regla, decisión o hito de autoría. "
                    "Para permitir consultas causales de 'quién hizo qué' (ej: '¿Qué reglas creó el usuario?'), "
                    "podés incluir predicados=[{'sujeto': 'usuario|agente_1', 'accion': 'establecio|creo', 'objeto': '...'}]"
                )

        # ── BRIDGES: Crear hub con bridges ya validados ──────────────
        # bridges_validos ya fue validado ANTES de _get_cerebro() — no hay basura.
        try:
            from core.concept_hub import crear_hub, agregar_bridges as _agregar_bridges
            hub_id = f"hub_{clave}"
            crear_hub(cerebro.conn, hub_id, clave, description="Bridges obligatorios desde aprender")
            _agregar_bridges(cerebro.conn, hub_id, bridges_validos)
        except Exception as e:
            # El nodo ya se guardó — no revertir por un error de hub, solo avisar
            pass

        msg += f" Hub 'hub_{clave}' creado con {len(bridges_validos)} bridges."

        # ── Búsqueda retroactiva: conexiones con el pasado ──
        tokens_nuevos = _tokenizar(clave + " " + contenido)
        viejos = _buscar_nodos_viejos_relacionados(cerebro, tokens_nuevos, contenido, top_k=3, umbral=0.05)
        if viejos:
            lineas_viejos = []
            for concepto_v, preview, dias_ant, sim in viejos:
                fecha = time.strftime("%d %b %Y", time.localtime(time.time() - dias_ant * 86400))
                lineas_viejos.append("  \u2728 {} ({}d) \u00b7 {} (sim={}) \u00b7 {}".format(fecha, dias_ant, concepto_v, sim, preview))
            msg += "\n\n\u2728 Conexiones con el pasado:"
            msg += "\n" + "\n".join(lineas_viejos)

        _interceptar("aprender", f"{clave}: {contenido}", cerebro)
        resultado_dict: dict = {
            "status": "ok",
            "mensaje": msg,
            "concepto": clave,
            "sinapsis": sinapsis_count,
        }
        if dim_meta.get("dimensiones_creadas"):
            resultado_dict["dimensiones_creadas"] = dim_meta["dimensiones_creadas"]
        if dim_meta.get("advertencias"):
            resultado_dict["advertencias_dimensiones"] = dim_meta["advertencias"]
        resultado = json.dumps(resultado_dict, ensure_ascii=False)
        if _warnings:
            return "\n".join(_warnings) + "\n\n" + resultado
        return resultado
    finally:
        cerebro.cerrar_sistema()


def register(mcp: Any) -> None:
    @mcp.tool(
        name="aprender",
        description=(
            "VIOLACIÓN CRÍTICA — NO GUARDAR SIN VINCULAR:\n"
            "Si guardás un nodo que tiene relación con otros nodos existentes, VINCULALO con biorag_vincular() ANTES de consolidar.\n"
            "Si no vinculás, el nodo queda huérfano. La otra sesión no lo encuentra. Se pierde tiempo, se confunde, se crean nodos duplicados.\n"
            "REGLA: Antes de consolidar, preguntate: '¿Estos nodos tienen relación?' Si sí, vinculalos.\n"
            "Ejemplo: Si guardás 'cv_adevcom_arquitectura' y ya existe 'cv_seccion_d_estado', vinculalos:\n"
            "  biorag_vincular(a='cv_adevcom_arquitectura', b='cv_seccion_d_estado')\n\n"
            "GUARDAR EN BIORAG NO ES COPIAR TEXTO. ES PENSAR CÓMO SE RECUPERA.\n"
            "Si no pensás en recuperabilidad, el nodo se pierde. Esto es MALO para la memoria y MALO para los agentes.\n\n"
            "Guarda algo nuevo en la memoria temporal de BioRAG. El nombre se convierte en clave limpia automáticamente (snake_case). El sistema conecta el nodo con otros relacionados solo.\n\n"
            "Clave: si no llamás a consolidar después, el recuerdo se borra en el siguiente ciclo de limpieza.\n\n"
            "Hay categorías para clasificar (System, Architecture, Project, Lesson, Profile, Personal, Principle, Protocol, Cognition, Relation, General, Etc...)\n\n"
            "Protocolo obligatorio: antes de guardar, mostrá al usuario qué dimensiones y categoría le puso. Sin confirmación, no se ejecuta. Nunca.\n\n"
            "Guardar en BioRAG no es copiar texto a la base. Es pensar en cómo alguien lo va a buscar después. "
            "Cuando guardás un nodo, elegí las palabras correctas, conectalo con otros conceptos que tengan que ver, y etiquetalo con las dimensiones que alguien usaría para encontrarlo. "
            "La gente no busca igual — si guardás solo con tus palabras, quizás nadie lo recupere. "
            "Pensá: 'si en 3 meses alguien busca X, ¿este nodo aparece?' Con millones de nodos, el que no tiene conexiones ni dimensiones bien puestas se pierde. Es como tener un libro sin índice.\n\n"
            "REGLA CRÍTICA — syn (sinónimos): Mínimo 5. Sin syn, el nodo solo es visible "
            "por nombre exacto. Nadie que busque con otras palabras lo encuentra. "
            "Cubrí tres capas: literal, relacionado, abstracto. "
            "La tool lanza warning si no ponés syn o es insuficiente."
        ),
    )
    def biorag_aprender(
        concepto: Annotated[str, Field(
            description=(
                "Nombre único del recuerdo. Se normaliza a snake_case minúsculas automáticamente "
                "(ej: 'Error HTTP 500' → 'error_http_500'). "
                "Usar nombres descriptivos y específicos del dominio."
            )
        )],
        contenido: Annotated[str, Field(
            description=(
                "Texto o conocimiento a almacenar. "
                "Debe ser autocontenido — incluir suficiente contexto para que sea útil "
                "sin necesitar la conversación original. "
                "Recomendado: 100-1000 caracteres por nodo."
            )
        )],
        dimensiones: Annotated[Any, Field(
            description=(
                "🚨🚨🚨 DANGER — LEÉ ESTO ANTES DE ELEGIR CUALQUIER VALOR 🚨🚨🚨\n"
                "═══════════════════════════════════════════════════════════════\n"
                "Dimensiones Semánticas-> Pregunta que responde -> ¿QUÉ NATURALEZA tiene este recuerdo? -> Metáfora -> El sentimiento o la categoría ontológica (un momento de tensión, una regla que aprendí, una herramienta).\n\n"
                "EL CATÁLOGO DE DIMENSIONES YA EXISTE. NO INVENTES VALORES.\n"
                "PROTOCOLO OBLIGATORIO — ORDEN ESTRICTO:\n"
                "  PASO 1: Leé la descripción de cada eje abajo. Entendé QUÉ clasifica.\n"
                "  PASO 2: Si el contenido lo justifica, usá el valor curado que más aplica.\n"
                "  PASO 3: Si NINGÚN valor curado aplica con honestidad → mandá tu valor\n"
                "          en snake_case sin tildes. Se auto-crea (ESTO ES EL ÚLTIMO RECURSO).\n"
                "\n"
                "⚠️  POR QUÉ IMPORTA: Cada valor nuevo fragmenta el espacio semántico.\n"
                "Si 'preocupacion' ya existe y mandás 'preocupacion_leve' → creás una isla\n"
                "que jamás se conectará con los nodos correctos.\n"
                "═══════════════════════════════════════════════════════════════\n\n"
                "EJES CERRADOS (no se crean nuevos) / VALORES: mundo abierto (creá si falta).\n"
                "Nodo sin dimensión al guardar = INVISIBLE para búsquedas ontológicas PARA SIEMPRE.\n\n"
                "LOS 13 EJES — DESCRIPCIÓN COMPLETA + VALORES CURADOS:\n"
                "───────────────────────────────────────────────────────────────\n"
                "1. EMOCION — (El 'Sentir')\n"
                "   La carga emocional o la reacción subjetiva ante la experiencia.\n"
                "   Pregunta: ¿El contenido expresa o evoca una emoción?\n"
                "   Valores: afecto, alegria, frustracion, tristeza, preocupacion, confusion,\n"
                "            sorpresa, miedo, alivio, apatia, culpa, satisfaccion\n"
                "───────────────────────────────────────────────────────────────\n"
                "2. ENTIDAD — (El 'Qué')\n"
                "   Cualquier tipo de ente, objeto o concepto identificable: personas, agentes\n"
                "   de IA, dispositivos, software, organizaciones o ideas abstractas.\n"
                "   Pregunta: ¿Qué entidades concretas o abstractas aparecen?\n"
                "   Valores: identidad_individual, identidad_social_legal, identidad_organizacional,\n"
                "            identidad_digital, identidad_artificial, identidad_fisica_hardware,\n"
                "            identidad_natural, identidad_concepto, identidad_institucion,\n"
                "            identidad_evento, identidad_vinculo\n"
                "───────────────────────────────────────────────────────────────\n"
                "3. ACCION — (El 'Hacer' o 'Estar')\n"
                "   Verbos, transiciones, procesos físicos y cognitivos.\n"
                "   Pregunta: ¿Qué se hace, ocurre o transiciona en el contenido?\n"
                "   Valores: accion_fisica, accion_transformacion_material, accion_persistencia_computacion,\n"
                "            accion_rutina_automatica, accion_comunicacion, accion_interaccion_social,\n"
                "            accion_cognitiva, accion_estado_ser, accion_evaluar, accion_observar, accion_fallar\n"
                "───────────────────────────────────────────────────────────────\n"
                "4. CUALIDAD — (El 'Cómo')\n"
                "   Propiedades, descripciones, tamaños y valoraciones de las cosas.\n"
                "   Pregunta: ¿Cómo es o está algo? ¿Qué característica lo define?\n"
                "   Valores: cualidad_dimension_fisica, cualidad_estado_condicion, cualidad_valoracion,\n"
                "            cualidad_sensorial, cualidad_material_composicion, cualidad_temporal_duracion,\n"
                "            cualidad_relacional_comparativa, cualidad_abstracta_conceptual,\n"
                "            cualidad_economica, cualidad_urgente, cualidad_autentica\n"
                "───────────────────────────────────────────────────────────────\n"
                "5. COORDENADA — (Espacio y Tiempo)\n"
                "   La ubicación física, las relaciones de distancia y la cronología.\n"
                "   Pregunta: ¿Cuándo o dónde ocurre? ¿Hay referencia temporal o espacial?\n"
                "   Valores: coordenada_cronologia_absoluta, coordenada_anclaje_deictico,\n"
                "            coordenada_secuencia_relativa, coordenada_ciclo_periodico,\n"
                "            coordenada_inclusion_topologica, coordenada_distancia_proximal,\n"
                "            coordenada_vector_direccional, coordenada_trayectoria_limite,\n"
                "            coordenada_etapa, coordenada_hito\n"
                "───────────────────────────────────────────────────────────────\n"
                "6. INTENCION — (El 'Por Qué')\n"
                "   Propósito o razón por la que se guardó el nodo. Captura la intención\n"
                "   del autor al momento de guardar.\n"
                "   Pregunta: ¿Para qué se guarda esto? ¿Qué quiere lograr quien guarda?\n"
                "   Valores: intencion_aprender, intencion_decidir, intencion_reflexionar,\n"
                "            intencion_resolver, intencion_solucionar, intencion_documentar,\n"
                "            intencion_desahogar, intencion_registrar\n"
                "───────────────────────────────────────────────────────────────\n"
                "7. DOMINIO — (El 'Dónde')\n"
                "   Área de vida o campo de aplicación del conocimiento. Dónde aplica el nodo.\n"
                "   Pregunta: ¿En qué ámbito o campo de conocimiento cae este contenido?\n"
                "   Valores: dominio_tecnico, dominio_personal, dominio_profesional, dominio_academico,\n"
                "            dominio_salud, dominio_finanzas, dominio_ambiental, dominio_social,\n"
                "            dominio_creativo, dominio_espiritual\n"
                "───────────────────────────────────────────────────────────────\n"
                "8. CUALIA — (El 'Modo de explicación')\n"
                "   Las 4 causas aristotélicas / qualia de Pustejovsky (Generative Lexicon).\n"
                "   Cómo se explica algo: qué es, de qué está hecho, cómo surgió, para qué sirve.\n"
                "   Pregunta: ¿El nodo define, describe composición, explica origen, o establece función?\n"
                "   Valores: formal_categoria, constitutiva_composicion, agentiva_origen, telica_funcion\n"
                "───────────────────────────────────────────────────────────────\n"
                "9. EPISTEMIA — (El 'Cómo lo sé')\n"
                "   Evidencialidad (Aikhenvald) + certeza. Fuente y grado de verdad del conocimiento:\n"
                "   directo, verificado, inferido, reportado, hipótesis, obsoleto.\n"
                "   Pregunta: ¿Cómo se obtuvo este conocimiento? ¿Qué tan confiable es?\n"
                "   Valores: directa_experiencial, verificada, inferida, reportada_externa,\n"
                "            hipotetica, obsoleta\n"
                "───────────────────────────────────────────────────────────────\n"
                "10. ESCALA_ABSTRACCION — (El 'Nivel de generalidad')\n"
                "    Del caso concreto a la ley universal.\n"
                "    Pregunta: ¿Es un caso puntual, un patrón, un principio o una ley?\n"
                "    Valores: instancia, patron, principio, ley_modelo, metafora\n"
                "───────────────────────────────────────────────────────────────\n"
                "11. CENTRALIDAD_IDENTITARIA — (El 'Cuánto es mío')\n"
                "    Self-reference effect. Grado en que el contenido define o toca la identidad.\n"
                "    Pregunta: ¿Este contenido define quién es el autor o tiene relevancia personal?\n"
                "    Valores: nucleo_identitario, relevante_personal, relevante_contextual,\n"
                "             informacion_externa, impersonal\n"
                "───────────────────────────────────────────────────────────────\n"
                "12. TEXTURA_EXPERIENCIAL — (El 'Cómo se sentía estar ahí')\n"
                "    Cualidad fenómenica del momento vivido (ínsula). Flujo, tensión,\n"
                "    desorientación, rutina, presencia plena.\n"
                "    Pregunta: ¿Cómo se sintió subjetivamente el momento que describe el nodo?\n"
                "    Valores: flujo, tension, desorientacion, rutina, presencia_plena\n"
                "───────────────────────────────────────────────────────────────\n"
                "13. MODALIDAD — (El 'Debo/Puedo')\n"
                "    Modalidad deóntica (Palmer). Obligación, prohibición, permiso, capacidad.\n"
                "    Pregunta: ¿El contenido establece algo obligatorio, prohibido, permitido o posible?\n"
                "    Valores: obligacion, prohibicion, permiso, capacidad\n"
                "───────────────────────────────────────────────────────────────\n\n"
                "REGLAS DE RIGOR:\n"
                "- ¿Podés señalar la frase exacta del contenido que justifica la dimensión? → ponela.\n"
                "- ¿No se sostiene en el texto? → no la pongas. Tu conocimiento externo no vale.\n"
                "- Evaluá los 13 ejes uno por uno. Mínimo esperable (contenido rico): 7-10 ejes.\n"
                "- Si ponés menos de 6, revisá epistemia, escala_abstraccion, cualia, intencion, dominio.\n\n"
                "FORMATO — STRING JSON con comillas dobles:\n"
                '{"emocion":["satisfaccion"],"entidad":["identidad_artificial"],"accion":["accion_cognitiva"],'
                '"cualidad":["cualidad_abstracta_conceptual"],"coordenada":["coordenada_cronologia_absoluta"],'
                '"intencion":["intencion_documentar"],"dominio":["dominio_tecnico"],'
                '"cualia":["telica_funcion"],"epistemia":["directa_experiencial"],'
                '"escala_abstraccion":["instancia"],"centralidad_identitaria":["impersonal"],'
                '"textura_experiencial":["flujo"],"modalidad":["capacidad"]}'
            )
        )],
        syn: Annotated[Optional[str], Field(
            description=(
                "FIRMA DE BÚSQUEDA DEL CONTENIDO.\n\n"
                "QUÉ ES syn:\n"
                "BM25 ya busca dentro del contenido y del nombre del concepto. Pero si alguien "
                "busca con PALABRAS DIFERENTES a las que se usaron al guardar, BM25 no lo encuentra. "
                "syn cierra esa brecha: son todas las palabras con las que alguien podría buscar "
                "este nodo que NO ESTÁN YA en el contenido ni en el nombre del concepto.\n\n"
                "PROCESO — Leé el contenido completo y preguntate:\n"
                "Para cada concepto, entidad, acción y propiedad mencionada en el texto:\n"
                "  → ¿Tiene abreviaturas, siglas o variantes? (CSS → cascading style sheets, hojas de estilo)\n"
                "  → ¿Tiene traducción al otro idioma? (formulario → form, búsqueda → search)\n"
                "  → ¿Cómo lo nombraría alguien informalmente? (peso sináptico → importancia, fuerza de conexión)\n"
                "  → ¿Cuál es el problema que resuelve? (si el contenido es la solución, poné el problema)\n"
                "  → ¿Cuál es la solución? (si el contenido es el problema, poné la solución)\n"
                "  → ¿Quién participó o está asociado pero no está mencionado en el texto?\n"
                "  → ¿Con qué otros conceptos del dominio se relaciona que no se nombran?\n"
                "  → ¿Cómo buscaría esto alguien que NO sabe que este nodo existe?\n\n"
                "REGLA DE ORO: Si una palabra ya está en el contenido o en el nombre del concepto, "
                "NO la pongas en syn (BM25 ya la indexa con peso 1.0x en contenido y 5.0x en concepto). "
                "syn es para lo que FALTA — las palabras que cierran la brecha de vocabulario.\n\n"
                "MÍNIMO 8. IDEAL 12-20. Sin límite máximo — cada sinónimo es una arista de búsqueda.\n"
                "Formato: separados por coma, sin espacios extra.\n"
                "Incluir español E inglés si el contenido es técnico.\n\n"
                "EJEMPLO — concepto: 'css_flexbox_fix_formulario'\n"
                "contenido: 'Se corrigió el layout del formulario usando display:flex y align-items:center...'\n"
                "syn (lo que NO está en el contenido): "
                "alineación,alignment,form,caja flexible,flexible box,layout roto,broken layout,"
                "centrado vertical,vertical centering,bug visual,responsive,maquetación,"
                "grid vs flex,posicionamiento,positioning,adevcom,peritaje\n\n"
                "syn ≠ sustantivos_clave: syn = todas las formas de buscar el nodo (sin límite, cierra la brecha de vocabulario). "
                "sustantivos_clave = de qué TRATA el nodo en 2 a 10 palabras núcleo (boost directo en recuperación)."
            )
        )] = None,
        cat: Annotated[Optional[str], Field(
            description=(
                "Categoría del recuerdo. Si se omite, se infiere del contenido automáticamente. "
                "Valores: System | Architecture | Project | Lesson | Profile | "
                "Personal | Principle | Protocol | Cognition | Relation | General. "
                "Usar listar_categorias para ver descripciones de cada una."
            )
        )] = None,
        predicados: Annotated[Optional[Any], Field(
            description=(
                "Estructura SRL (Semantic Role Labeling) de tripletas/cuádruplas causales.\n"
                "Formato: JSON o lista de dicts [{'sujeto': '...', 'accion': '...', 'objeto': '...', 'contexto': '...'}]\n\n"
                "CUÁNDO USARLO: En recuerdos sobre decisiones, reglas, acuerdos, autoría o acciones (ej: 'El usuario instruyó no usar CSS global' → sujeto: 'usuario', accion: 'instruyo', objeto: 'no_usar_css_global').\n"
                "CUÁNDO OMITIRLO: En datos técnicos puros, snippets de código o configs sin autoría (dejar None)."
            )
        )] = None,
        valencia_somatica: Annotated[Optional[float], Field(
            description="Valencia emocional/somática (0.0 a 1.0). Nodos con valencia >= 0.80 son inmunes al decaimiento por sueño y la poda."
        )] = None,
        bridges: Annotated[Optional[Any], Field(
            description=(
                "OBLIGATORIO — exactamente 5 frases estructuradas cubriendo los 5 ángulos semánticos.\n"
                "Sin 5 bridges válidos con sus 5 ángulos distintos, el nodo NO se guarda (rechazo preventivo pre-DB).\n"
                "Si bridges llega vacío o ausente, la tool retorna error accionable con instrucciones exactas para reintentar.\n\n"
                "QUÉ ES UN BRIDGE: una frase de 2 o más palabras de contenido real (sin stopwords) "
                "que alguien escribiría para encontrar este nodo SIN usar las mismas palabras del nombre ni del contenido.\n\n"
                "FORMATO OFICIAL: lista de 5 dicts {'text': '...', 'angle': '...'}:\n"
                "  bridges=[\n"
                "    {'text': 'sinonimo conceptual con otras palabras', 'angle': 'sinonimo'},\n"
                "    {'text': 'dolor o falla que este nodo resuelve', 'angle': 'problema'},\n"
                "    {'text': 'herramienta o solucion tecnica que aplica', 'angle': 'solucion'},\n"
                "    {'text': 'quien y en que situacion o caso de uso lo busca', 'angle': 'situacion'},\n"
                "    {'text': 'como lo buscaria un novato a ciegas sin tecnicismos', 'angle': 'ingenuo'}\n"
                "  ]\n\n"
                "LOS 5 ÁNGULOS PERMITIDOS (exactamente 1 por cada ángulo):\n"
                "  - 'sinonimo': concepto equivalente con vocabulario disjunto\n"
                "  - 'problema': síntoma, error o necesidad\n"
                "  - 'solucion': técnica, patrón o respuesta\n"
                "  - 'situacion': rol o contexto de aplicación\n"
                "  - 'ingenuo': búsqueda en lenguaje común sin jerga\n\n"
                "EJEMPLO COMPLETO — nodo 'leccion_http_500_timeout':\n"
                "  bridges=[\n"
                "    {'text': 'corte intempestivo de comunicacion backend', 'angle': 'sinonimo'},\n"
                "    {'text': 'pagina en blanco sin respuesta del servidor', 'angle': 'problema'},\n"
                "    {'text': 'reintentos exponenciales y keepalive configurado', 'angle': 'solucion'},\n"
                "    {'text': 'usuario reportando caida intermitente de la web', 'angle': 'situacion'},\n"
                "    {'text': 'la web se cae sola y no carga', 'angle': 'ingenuo'}\n"
                "  ]"
            )
        )] = None,
        sustantivos_clave: Annotated[Optional[str], Field(
            description=(
                "Sustantivos Clave -> Pregunta que responde -> ¿DE QUÉ trata exactamente? -> Metáfora -> La huella dactilar o el rostro de alguien (específico, concreto, único).\n\n"
                "Los sustantivos clave son el campo más importante al guardar un nodo. No es relleno: es lo que decide si el recuerdo se encuentra o no.\n"
                "1. ¿De qué trata el nodo? — no qué palabras contiene, sino de qué se trata.\n"
                "2. No repetir palabras que ya están en contenido o en syn: los pesos se suman y el nodo se infla.\n"
                "3. Son la identidad del nodo: el artefacto, la herramienta, el dominio. Ejemplo: un script que bajaba fuentes de\n\n" "NotebookLM → descarga, fuente, cuaderno.\n\n"
                "4. Criterio de éxito: ¿aparece este nodo cuando alguien lo busque dentro de 3 meses, con otras palabras?\n"
                "a. Escribí de qué TRATA el nodo, no las palabras que aparecen en el texto.\n"
                "b. NO repitas palabras que ya están en contenido ni en syn.\n"
                "c. Incluí: la herramienta, el artefacto y el dominio.\n"
                "Ejemplo — nodo sobre un script que descarga fuentes de NotebookLM: descarga,fuente,cuaderno,notebooklm\n\n"
                "OBLIGATORIO — centro de gravedad semántico: 2 a 10 sustantivos que definen de QUÉ TRATA el nodo (peso BM25 4.0x).\n"
                "PROPÓSITO: hacen que nodos que NO comparten palabras se encuentren por el núcleo temático — un sustantivo mal puesto = nodo que jamás aparece.\n"
                "PROTOCOLO DE EXTRACCIÓN — sacalos SIEMPRE de lo que se está guardando, nunca los inventes. Tres preguntas:\n"
                "  1. ¿Qué se hizo o qué estoy guardando? (la acción/objeto concreto)\n"
                "  2. ¿De qué se trata? (el núcleo temático — por eso se llaman CLAVES)\n"
                "  3. ¿Con qué se relaciona? (tema que otro nodo futuro también pueda tocar)\n"
                "Ejemplos (contenido → sustantivos_clave):\n"
                "  - perro/Manchita: 'Me gusta pasar por las tardes con mi perro mi perra que se llama manchita...' → 'tarde,perro,perra,manchita'\n"
                "  - olvido del jefe: 'Se me olvidó que tenía que llamar a mi jefe, mañana...' → 'olvido,jefe,llamada'\n"
                "  - arepitas: 'A Dennys le gusta hacer arepitas dulces y comerlas en la tarde...' → 'arepitas,comer,tarde,gustos'\n"
                "  - trabajo sin parar: 'cuando trabajo demasiado sin parar y no puedo hacer pausa' → 'trabajo,pausa'\n"
                "Relación a futuro: guardaste 'traduccion,script,deepseek' y mañana guardás 'traducción de un documento'\n"
                "  → comparte 'traduccion' y al buscarlo lo clavás aunque los nodos no compartan más palabras.\n"
                "Formato: 2 a 10 términos únicos separados por coma, minúsculas, sin tildes ni espacios.\n"
                "🔒 PROHIBICIONES ABSOLUTAS:\n"
                "🔒 INVARIANTE — MANDATORY (incumplir = nodo mal indexado, no se recupera):\n"
                "✗ NO métricas, efectos ni consecuencias ('recall', 'ranking', 'dilucion', 'top1') — describen lo que PASÓ, no qué ES; van en contenido/syn.\n"
                "✗ NO palabras que no estén LITERALMENTE en lo que guardás — si no la escribiste ahí, no existe para el índice.\n"
                "✗ NO nominalizar verbos del flujo (postular → 'postulacion', analizar → 'analisis').\n"
                "✗ NO abstracciones vacías de segundo orden ('estrategia', 'transicion', 'diferenciacion').\n\n"
                "✗ NO repetir palabras del nombre del concepto (ya tienen peso 5.0x en BM25).\n"
                "✗ NO nominalizar verbos (postular→'postulacion', analizar→'analisis').\n"
                "✗ NO abstracciones vacías ('estrategia', 'metodologia', 'proceso', 'filosofia').\n"
                "✗ NO métricas ni consecuencias ('recall', 'ranking', 'impacto', 'top1').\n"
                "✗ NO palabras ausentes del contenido (si no está escrito, no va).\n\n"
                "EJEMPLOS CONTRASTADOS:\n"
                "  Nodo sobre montar Obsidian con FUSE en Google Drive:\n"
                "    ✗ MAL: ocamlfuse,lanzador,terminal → terminal no pasa Test 2, falta el tema central\n"
                "    ✓ BIEN: obsidian,vault,ocamlfuse,fuse → cada uno pasa ambos tests\n"
                "  Nodo sobre traducir un script de ruso a español con DeepSeek:\n"
                "    ✗ MAL: idiomas,soporte,proceso → genéricos, nominalizan, no discriminan\n"
                "    ✓ BIEN: traduccion,script,deepseek → identidad + artefacto + herramienta\n"
                "  Nodo personal sobre paseo con mascota:\n"
                "    ✓ BIEN: perro,perra,manchita → identidad irreducible del recuerdo."
            )
        )] = None,
        busqueda_previa: Annotated[Optional[bool], Field(
            description=(
                "🔒 OBLIGATORIO — Confirmación de búsqueda previa (Invariante Pre-flight Search).\n"
                "Debe ser True obligatoriamente. Antes de aprender o guardar, el agente debe haber consultado "
                "biorag_buscar o biorag_recordar para verificar duplicados o nodos relacionados."
            )
        )] = False,
        vincular_con: Annotated[Optional[Any], Field(
            description=(
                "Lista o string de conceptos con los que vincular este nodo inmediatamente al crearlo "
                "(ej: ['nodo_a', 'nodo_b'] o 'nodo_a,nodo_b'). Establece sinapsis bidireccionales en el connectome."
            )
        )] = None,
    ) -> str:
        return _aprender_impl(
            concepto,
            contenido,
            bridges,
            syn=syn,
            cat=cat,
            dimensiones=dimensiones,
            predicados=predicados,
            valencia_somatica=valencia_somatica,
            sustantivos_clave=sustantivos_clave,
            busqueda_previa=bool(busqueda_previa),
            vincular_con=vincular_con,
        )

    @mcp.tool(
        name="guardar",
        description=(
            "(legado) Alias de 'aprender' — preferir 'aprender' para identificar la operación cognitiva real. "
            "Misma funcionalidad y parámetros.\n\n"
            "Parámetros: concepto (str), contenido (str), bridges (5 ángulos REQUERIDO), busqueda_previa (bool REQUERIDO True), "
            "vincular_con (list/str opcional), syn (str opcional), cat (str opcional), "
            "dimensiones (str JSON opcional), predicados (str JSON opcional), valencia_somatica (float opcional).\n\n"
            "Retorna: {status, mensaje, concepto (str normalizado), sinapsis (int)}"
        ),
    )
    def biorag_guardar(
        concepto: Annotated[str, Field(description="Nombre unique del recuerdo (se normaliza a snake_case).")],
        contenido: Annotated[str, Field(description="Texto o conocimiento a almacenar.")],
        syn: Annotated[Optional[str], Field(
            description=(
                "Sinónimos separados por coma. Ver descripción en `aprender` para reglas y ejemplos. "
                "Ojo: sin syn el nodo queda invisible — mínimo 5 sinónimos."
            )
        )] = None,
        cat: Annotated[Optional[str], Field(description="Categoría. Ver aprender para valores válidos.")] = None,
        dimensiones: Annotated[Optional[Any], Field(
            description=(
                "🚨 DANGER — LEE ESTO PRIMERO 🚨\n"
                "Dimensiones Semánticas-> Pregunta que responde -> ¿QUÉ NATURALEZA tiene este recuerdo? -> Metáfora -> El sentimiento o la categoría ontológica (un momento de tensión, una regla que aprendí, una herramienta).\n\n"
                "PASO 1: Usá valores curados del catálogo listados abajo.\n"
                "PASO 2: Si encuentrás uno que aplica → USALO. Punto.\n"
                "PASO 3: Si NINGÚN valor curado aplica → mandá tu valor en snake_case (se auto-crea). ÚLTIMO RECURSO.\n"
                "Cada valor nuevo que inventás fragmenta el espacio semántico. Respetá el catálogo.\n\n"
                "13 EJES — VALORES CURADOS:\n"
                "emocion → afecto, alegria, frustracion, tristeza, preocupacion, confusion, sorpresa, miedo, alivio, apatia, culpa, satisfaccion\n"
                "entidad → identidad_individual, identidad_social_legal, identidad_organizacional, identidad_digital, identidad_artificial, identidad_fisica_hardware, identidad_natural, identidad_concepto, identidad_institucion, identidad_evento, identidad_vinculo\n"
                "accion → accion_fisica, accion_transformacion_material, accion_persistencia_computacion, accion_rutina_automatica, accion_comunicacion, accion_interaccion_social, accion_cognitiva, accion_estado_ser, accion_evaluar, accion_observar, accion_fallar\n"
                "cualidad → cualidad_dimension_fisica, cualidad_estado_condicion, cualidad_valoracion, cualidad_sensorial, cualidad_material_composicion, cualidad_temporal_duracion, cualidad_relacional_comparativa, cualidad_abstracta_conceptual, cualidad_economica, cualidad_urgente, cualidad_autentica\n"
                "coordenada → coordenada_cronologia_absoluta, coordenada_anclaje_deictico, coordenada_secuencia_relativa, coordenada_ciclo_periodico, coordenada_inclusion_topologica, coordenada_distancia_proximal, coordenada_vector_direccional, coordenada_trayectoria_limite, coordenada_etapa, coordenada_hito\n"
                "intencion → intencion_aprender, intencion_decidir, intencion_reflexionar, intencion_resolver, intencion_solucionar, intencion_documentar, intencion_desahogar, intencion_registrar\n"
                "dominio → dominio_tecnico, dominio_personal, dominio_profesional, dominio_academico, dominio_salud, dominio_finanzas, dominio_ambiental, dominio_social, dominio_creativo, dominio_espiritual\n"
                "cualia → formal_categoria, constitutiva_composicion, agentiva_origen, telica_funcion\n"
                "epistemia → directa_experiencial, verificada, inferida, reportada_externa, hipotetica, obsoleta\n"
                "escala_abstraccion → instancia, patron, principio, ley_modelo, metafora\n"
                "centralidad_identitaria → nucleo_identitario, relevante_personal, relevante_contextual, informacion_externa, impersonal\n"
                "textura_experiencial → flujo, tension, desorientacion, rutina, presencia_plena\n"
                "modalidad → obligacion, prohibicion, permiso, capacidad\n\n"
                "Protocolo: recorré los 13 ejes uno por uno. Mínimo 7-10 ejes si el contenido es rico. "
                "Ver descripción completa con reglas de veracidad en `aprender`."
            )
        )] = None,
        predicados: Annotated[Optional[Any], Field(
            description="Estructura SRL (JSON o lista de dicts). Ver descripción en `aprender` para reglas y ejemplos de uso."
        )] = None,
        valencia_somatica: Annotated[Optional[float], Field(
            description="Valencia emocional/somática (0.0 a 1.0)."
        )] = None,
        bridges: Annotated[Optional[Any], Field(
            description=(
                "OBLIGATORIO — exactamente 5 frases estructuradas cubriendo los 5 ángulos semánticos. "
                "Ver descripción completa con ejemplos en `aprender`. "
                "Si se omite, la tool retorna error accionable con instrucciones exactas para reintentar."
            )
        )] = None,
        sustantivos_clave: Annotated[Optional[str], Field(
            description=(
                "Sustantivos Clave -> Pregunta que responde -> ¿DE QUÉ trata exactamente? -> Metáfora -> La huella dactilar o el rostro de alguien (específico, concreto, único).\n\n"
                "OBLIGATORIO — SOMA del nodo: 2 a 10 sustantivos que son su IDENTIDAD irreducible (peso BM25 4.0x). "
                "PROTOCOLO — 2 TESTS MECÁNICOS (ver `aprender` para detalle completo): "
                "TEST 1 IDENTIDAD: «Este nodo ES un nodo sobre ___.» Natural→PASA, forzado→NO PASA. "
                "TEST 2 DISCRIMINACIÓN: «¿>30% de los nodos podrían tener esta palabra?» Sí→INVÁLIDO, No→VÁLIDO. "
                "Formato: minúsculas, sin tildes, separados por coma, extraídos del contenido. "
                "🔒 PROHIBICIONES: No repetir palabras del concepto, no nominalizar verbos, "
                "no abstracciones vacías, no métricas, no palabras ausentes del contenido."
            )
        )] = None,
        busqueda_previa: Annotated[Optional[bool], Field(
            description=(
                "🔒 OBLIGATORIO — Confirmación de búsqueda previa (Invariante Pre-flight Search).\n"
                "Debe ser True obligatoriamente. Antes de aprender o guardar, el agente debe haber consultado "
                "biorag_buscar o biorag_recordar para verificar duplicados o nodos relacionados."
            )
        )] = False,
        vincular_con: Annotated[Optional[Any], Field(
            description=(
                "Lista o string de conceptos con los que vincular este nodo inmediatamente al crearlo "
                "(ej: ['nodo_a', 'nodo_b'] o 'nodo_a,nodo_b'). Establece sinapsis bidireccionales en el connectome."
            )
        )] = None,
    ) -> str:
        return _aprender_impl(
            concepto,
            contenido,
            bridges,
            syn=syn,
            cat=cat,
            dimensiones=dimensiones,
            predicados=predicados,
            valencia_somatica=valencia_somatica,
            sustantivos_clave=sustantivos_clave,
            busqueda_previa=bool(busqueda_previa),
            vincular_con=vincular_con,
        )

    # ── SUSTANTIVOS CLAVE TOOLS (T4 Spec 001) ────────────────────────────────

    @mcp.tool(
        name="agregar_sustantivos",
        description=(
            "Actualiza o agrega sustantivos_clave a un nodo existente en largo_plazo (o corto_plazo).\n"
            "Permite enriquecer nodos legacy creados antes de la introducción de sustantivos_clave "
            "o corregir/refinar el centro de gravedad semántico de un nodo.\n\n"
            "Parámetros: concepto (str), sustantivos_clave (str: 2 a 10 términos separados por coma).\n"
            "Retorna: {status: 'ok', concepto: str, sustantivos_anteriores: str, sustantivos_nuevos: str}\n"
            "O error {status: 'error', codigo: '...', mensaje: '...'}"
        ),
    )
    def biorag_agregar_sustantivos(
        concepto: Annotated[str, Field(description="Nombre del nodo existente (se normaliza a snake_case).")],
        sustantivos_clave: Annotated[str, Field(
            description=(
                "Sustantivos Clave -> Pregunta que responde -> ¿DE QUÉ trata exactamente? -> Metáfora -> La huella dactilar o el rostro de alguien (específico, concreto, único).\n\n"
                "SOMA del nodo: 2 a 10 sustantivos que son su IDENTIDAD irreducible (peso BM25 4.0x).\n"
                "PROTOCOLO — 2 TESTS MECÁNICOS (nodo ya existente — mirá qué contiene antes de elegir):\n"
                "TEST 1 IDENTIDAD: «Este nodo ES un nodo sobre ___.» Natural→PASA, forzado→NO PASA.\n"
                "TEST 2 DISCRIMINACIÓN: «¿>30% de los nodos podrían tener esta palabra?» Sí→INVÁLIDO (va en syn), No→VÁLIDO.\n"
                "Formato: 2 a 10 términos, minúsculas, sin tildes, separados por coma, extraídos del contenido.\n"
                "🔒 PROHIBICIONES: No repetir palabras del concepto, no nominalizar verbos, "
                "no abstracciones vacías, no métricas, no palabras ausentes del contenido."
            )
        )],
    ) -> str:
        clave = concepto.lower().strip().replace(" ", "_")

        if not sustantivos_clave or not str(sustantivos_clave).strip():
            return json.dumps({
                "status": "error",
                "codigo": "SUSTANTIVOS_CLAVE_AUSENTES",
                "mensaje": (
                    f"❌ SUSTANTIVOS_CLAVE_AUSENTES — no se pudo actualizar '{clave}'.\n\n"
                    "Falta el parámetro obligatorio 'sustantivos_clave'.\n"
                    "Formato: 2 a 10 términos únicos separados por coma (ej: 'servidor,backend,timeout')."
                ),
                "concepto": clave,
            }, ensure_ascii=False)

        from core.memory_store import normalizar_sustantivos_clave
        sustantivos_norm = normalizar_sustantivos_clave(str(sustantivos_clave))
        sk_unicos = [t for t in sustantivos_norm.split(",") if t] if sustantivos_norm else []

        if len(sk_unicos) < 2 or len(sk_unicos) > 10:
            return json.dumps({
                "status": "error",
                "codigo": "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA",
                "mensaje": (
                    f"❌ SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA — no se pudo actualizar '{clave}'.\n\n"
                    "SUSTANTIVOS_CLAVE_CANTIDAD_INVALIDA: se requieren entre 2 a 10 términos "
                    f"únicos; se recibió {len(sk_unicos)} tras deduplicar. "
                    "Formato: 'servidor,backend,timeout,conexion'"
                ),
                "concepto": clave,
                "cantidad_recibida": len(sk_unicos),
            }, ensure_ascii=False)

        for _sk_term in sk_unicos:
            if not re.fullmatch(r"[a-z0-9_ñ]{2,15}", _sk_term):
                return json.dumps({
                    "status": "error",
                    "codigo": "SUSTANTIVOS_CLAVE_FORMATO_INVALIDO",
                    "mensaje": (
                        f"❌ SUSTANTIVOS_CLAVE_FORMATO_INVALIDO — no se pudo actualizar '{clave}'.\n\n"
                        f"SUSTANTIVOS_CLAVE_FORMATO_INVALIDO: el término '{_sk_term}' no cumple formato "
                        "(2-15 chars, sin espacios, solo alfanuméricos y guion bajo)."
                    ),
                    "concepto": clave,
                    "termino_invalido": _sk_term,
                }, ensure_ascii=False)

        cerebro = _get_cerebro()
        try:
            # 1. Buscar en largo_plazo
            cerebro.cursor.execute("SELECT sustantivos_clave FROM largo_plazo WHERE concepto = ?", (clave,))
            row_lp = cerebro.cursor.fetchone()
            if row_lp is not None:
                anterior = row_lp[0] or ""
                cerebro.cursor.execute("UPDATE largo_plazo SET sustantivos_clave = ? WHERE concepto = ?", (sustantivos_norm, clave))
                cerebro.conn.commit()
                return json.dumps({
                    "status": "ok",
                    "concepto": clave,
                    "sustantivos_anteriores": anterior,
                    "sustantivos_nuevos": sustantivos_norm,
                }, ensure_ascii=False)

            # 2. Fallback a corto_plazo
            cerebro.cursor.execute("SELECT sustantivos_clave FROM corto_plazo WHERE concepto = ?", (clave,))
            row_cp = cerebro.cursor.fetchone()
            if row_cp is not None:
                anterior = row_cp[0] or ""
                cerebro.cursor.execute("UPDATE corto_plazo SET sustantivos_clave = ? WHERE concepto = ?", (sustantivos_norm, clave))
                cerebro.conn.commit()
                return json.dumps({
                    "status": "ok",
                    "concepto": clave,
                    "sustantivos_anteriores": anterior,
                    "sustantivos_nuevos": sustantivos_norm,
                }, ensure_ascii=False)

            return json.dumps({
                "status": "error",
                "codigo": "NODO_NO_ENCONTRADO",
                "mensaje": f"El concepto '{clave}' no existe en la base de datos.",
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="sustantivos",
        description=(
            "Consulta los sustantivos_clave de un nodo existente en largo_plazo o corto_plazo.\n"
            "Retorna: {status: 'ok', concepto: str, sustantivos_clave: str, items: [str]}\n"
            "O error {status: 'error', codigo: 'NODO_NO_ENCONTRADO', mensaje: '...'}"
        ),
    )
    def biorag_sustantivos(
        concepto: Annotated[str, Field(description="Nombre del nodo a consultar (snake_case).")],
    ) -> str:
        clave = concepto.lower().strip().replace(" ", "_")
        cerebro = _get_cerebro()
        try:
            # 1. Buscar en largo_plazo
            cerebro.cursor.execute("SELECT sustantivos_clave FROM largo_plazo WHERE concepto = ?", (clave,))
            row = cerebro.cursor.fetchone()
            if row is None:
                # 2. Fallback a corto_plazo
                cerebro.cursor.execute("SELECT sustantivos_clave FROM corto_plazo WHERE concepto = ?", (clave,))
                row = cerebro.cursor.fetchone()

            if row is None:
                return json.dumps({
                    "status": "error",
                    "codigo": "NODO_NO_ENCONTRADO",
                    "mensaje": f"El concepto '{clave}' no existe en la base de datos.",
                }, ensure_ascii=False)

            val = row[0] or ""
            items = [x.strip() for x in val.split(",") if x.strip()] if val else []
            return json.dumps({
                "status": "ok",
                "concepto": clave,
                "sustantivos_clave": val,
                "items": items,
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()

    @mcp.tool(
        name="actualizar",
        description=(
            "Actualiza o sobrescribe campos de un nodo existente en largo_plazo sin restricción temporal.\n\n"
            "Parámetros:\n"
            "- concepto (str): Nombre del nodo a actualizar (snake_case).\n"
            "- contenido (str, opcional): Nuevo contenido del nodo.\n"
            "- peso_sinaptico (float, opcional): Nuevo peso sináptico (0.0 a 1.0).\n"
            "- estado (str, opcional): Nuevo estado: 'activo', 'dormido', 'cuarentena'.\n"
            "- sinonimos (str, opcional): Nuevos sinónimos separados por coma.\n"
            "- sustantivos_clave (str, opcional): Nuevos sustantivos clave (2 a 10 términos separados por coma).\n"
            "- dimensiones (str JSON / dict, opcional): Nuevas coordenadas dimensionales.\n"
            "- categoria (str, opcional): Nueva categoría.\n"
            "- sobrescribir (bool, default False): Si es True, reemplaza completamente el contenido y metadatos del nodo.\n\n"
            "Retorna: {status: 'ok', mensaje, campos_modificados, sobrescrito: bool} o error si no existe."
        ),
    )
    def biorag_actualizar(
        concepto: Annotated[str, Field(
            description="Nombre del nodo a actualizar (snake_case). Debe existir en largo_plazo."
        )],
        contenido: Annotated[Optional[str], Field(
            description="Nuevo contenido del nodo."
        )] = None,
        peso_sinaptico: Annotated[Optional[float], Field(
            description="Nuevo peso sináptico (0.0 a 1.0)."
        )] = None,
        estado: Annotated[Optional[str], Field(
            description="Nuevo estado: activo, dormido, cuarentena."
        )] = None,
        sinonimos: Annotated[Optional[str], Field(
            description="Nuevos sinónimos separados por coma."
        )] = None,
        sustantivos_clave: Annotated[Optional[str], Field(
            description=(
                "Sustantivos Clave -> Pregunta que responde -> ¿DE QUÉ trata exactamente? -> Metáfora -> La huella dactilar o el rostro de alguien (específico, concreto, único).\n\n"
                "SOMA del nodo: 2 a 10 sustantivos IDENTIDAD irreducible (BM25 4.0x). "
                "Aplicar TEST 1 IDENTIDAD («ES un nodo sobre ___») + TEST 2 DISCRIMINACIÓN («¿>30% podrían tenerlo?»). "
                "Ver protocolo completo en `aprender`."
            )
        )] = None,
        dimensiones: Annotated[Optional[Any], Field(
            description="Clasificación dimensional (JSON string o dict)."
        )] = None,
        categoria: Annotated[Optional[str], Field(
            description="Nueva categoría del recuerdo."
        )] = None,
        sobrescribir: Annotated[Optional[bool], Field(
            description="Si es True, sobrescribe por completo el contenido y metadatos del nodo."
        )] = False,
        agente: Annotated[Optional[str], Field(
            description="Nombre del agente (opcional, para compatibilidad)."
        )] = None,
    ) -> str:
        cerebro = _get_cerebro()
        try:
            cur = cerebro.cursor
            cur.execute("SELECT 1, creado_en FROM largo_plazo WHERE concepto=?", (concepto,))
            row = cur.fetchone()
            if not row:
                return json.dumps({
                    "status": "error",
                    "mensaje": f"Nodo '{concepto}' no encontrado",
                }, ensure_ascii=False)

            updates = []
            params = []
            if contenido is not None:
                updates.append("contenido = ?")
                params.append(contenido)
            if peso_sinaptico is not None:
                if not 0.0 <= peso_sinaptico <= 1.0:
                    return json.dumps({
                        "status": "error",
                        "mensaje": f"peso_sinaptico debe estar entre 0.0 y 1.0, recibido: {peso_sinaptico}",
                    }, ensure_ascii=False)
                updates.append("peso_sinaptico = ?")
                params.append(peso_sinaptico)
            if estado is not None:
                estados_validos = {"activo", "dormido", "cuarentena"}
                if estado not in estados_validos:
                    return json.dumps({
                        "status": "error",
                        "mensaje": f"estado debe ser uno de {estados_validos}, recibido: '{estado}'",
                    }, ensure_ascii=False)
                updates.append("estado = ?")
                params.append(estado)
            if sinonimos is not None:
                updates.append("sinonimos = ?")
                params.append(sinonimos)
            if sustantivos_clave is not None:
                from core.memory_store import normalizar_sustantivos_clave
                sk_norm = normalizar_sustantivos_clave(str(sustantivos_clave))
                updates.append("sustantivos_clave = ?")
                params.append(sk_norm)
            if categoria is not None:
                cat_id = cerebro._resolver_categoria_id(categoria)
                updates.append("categoria = ?")
                params.append(cat_id)

            if sobrescribir:
                updates.append("creado_en = ?")
                params.append(time.time())

            # Manejar dimensiones si fueron provistas
            modifico_dimensiones = False
            if dimensiones is not None:
                if isinstance(dimensiones, str):
                    try:
                        dim_dict = json.loads(dimensiones)
                    except Exception:
                        dim_dict = {}
                elif isinstance(dimensiones, dict):
                    dim_dict = dimensiones
                else:
                    dim_dict = {}

                cur.execute("DELETE FROM largo_plazo_dimensiones WHERE concepto = ?", (concepto,))
                for tipo_nombre, valores in dim_dict.items():
                    if not valores:
                        continue
                    if isinstance(valores[0], int):
                        ids_validos = valores
                    else:
                        ids_validos, _, _ = cerebro._resolver_dimension_ids(
                            tipo_nombre,
                            ",".join(valores) if isinstance(valores, list) else valores,
                        )
                    for eid in ids_validos:
                        cur.execute(
                            "INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id) VALUES (?, ?)",
                            (concepto, eid),
                        )
                modifico_dimensiones = True

            if not updates and not modifico_dimensiones:
                return json.dumps({
                    "status": "sin_cambios",
                    "mensaje": "No se especificaron campos a actualizar",
                }, ensure_ascii=False)

            if updates:
                params.append(concepto)
                cur.execute(
                    f"UPDATE largo_plazo SET {', '.join(updates)} WHERE concepto=?",
                    params,
                )
            cerebro.conn.commit()

            # Clasificación simbólica y SDM tras modificación
            if contenido is not None or sinonimos is not None:
                try:
                    cur.execute("SELECT contenido, sinonimos FROM largo_plazo WHERE concepto = ?", (concepto,))
                    row_c = cur.fetchone()
                    if row_c:
                        cerebro._clasificar_nodo_wordnet(concepto, row_c[0] or "", row_c[1] or "")
                        from core.sdm import indexar_nodo_sdm
                        indexar_nodo_sdm(cerebro, concepto)
                except Exception:
                    pass

            campos_modificados = [u.split(" =")[0] for u in updates]
            if modifico_dimensiones:
                campos_modificados.append("dimensiones")

            return json.dumps({
                "status": "ok",
                "mensaje": f"Nodo '{concepto}' actualizado",
                "campos_modificados": campos_modificados,
                "sobrescrito": bool(sobrescribir),
            }, ensure_ascii=False)
        finally:
            cerebro.cerrar_sistema()
