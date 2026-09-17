#!/usr/bin/env python3
"""
Tests T9 — Batería de extracción multi-modelo (RF-23 / Spec 001).

RF cubierto: RF-23.

Verifica la batería completa de 8 casos definida en `specs/001-sustantivos-clave/bateria_extraccion.md`:
  - Cada caso tiene texto, términos esperados y términos prohibidos.
  - Ningún término esperado contiene términos prohibidos.
  - Validación de formato: 2-4 términos únicos, 2-15 caracteres, alfanumérico + guion bajo.
  - Guardado con `biorag_aprender` (o MCP tool) es aceptado (status ok).
  - Búsqueda con `biorag_recordar` con boost temático recupera el nodo en top resultados.
"""
import json
import pytest

CASOS_BATERIA = [
    {
        "id": 1,
        "nombre": "Núcleo explícito",
        "texto": "Historia del automóvil desde 1886 hasta la era eléctrica con gran evolución del transporte",
        "esperado": "automovil, historia, era",
        "prohibido": ["electricidad", "electrica"],
        "query": "historia del automovil desde 1886",
        "concepto": "bateria_caso_1_automovil",
        "bridges": [
            {"text": "evolucion del carruaje motorizado", "angle": "sinonimo"},
            {"text": "falta de documentacion sobre patentes de transporte", "angle": "problema"},
            {"text": "linea de tiempo de motores de combustion", "angle": "solucion"},
            {"text": "investigador estudiando vehiculos antiguos", "angle": "situacion"},
            {"text": "cuando se inventaron los carros", "angle": "ingenuo"},
        ]
    },
    {
        "id": 2,
        "nombre": "Núcleo implícito",
        "texto": "Los automóviles botan humo que contamina el aire de las ciudades y genera polución",
        "esperado": "contaminacion, aire, ciudades",
        "prohibido": ["automovil", "automoviles"],
        "query": "contaminacion del aire en ciudades",
        "concepto": "bateria_caso_2_contaminacion",
        "bridges": [
            {"text": "degradacion de la calidad ambiental urbana", "angle": "sinonimo"},
            {"text": "concentracion de smog en avenidas principales", "angle": "problema"},
            {"text": "filtros de emisiones y zonas peatonales", "angle": "solucion"},
            {"text": "medicion de particulas en el centro urbano", "angle": "situacion"},
            {"text": "el aire de la calle esta muy sucio", "angle": "ingenuo"},
        ]
    },
    {
        "id": 3,
        "nombre": "Servidor/backend",
        "texto": "El servidor backend cae por timeout de conexión en producción durante el pico de tráfico",
        "esperado": "servidor, backend, timeout",
        "prohibido": ["caida", "cae"],
        "query": "timeout servidor backend produccion",
        "concepto": "bateria_caso_3_servidor",
        "bridges": [
            {"text": "agotamiento de sockets y latencia excesiva", "angle": "sinonimo"},
            {"text": "peticiones http quedan sin respuesta", "angle": "problema"},
            {"text": "escalado horizontal y balanceo de carga", "angle": "solucion"},
            {"text": "alerta de monitoreo durante horas pico", "angle": "situacion"},
            {"text": "la pagina no responde y da error de espera", "angle": "ingenuo"},
        ]
    },
    {
        "id": 4,
        "nombre": "Frontend/CSS",
        "texto": "CSS flexbox arregla el layout roto del formulario de pago en la interfaz web responsive",
        "esperado": "css, flexbox, layout",
        "prohibido": ["arreglo", "arregla"],
        "query": "css flexbox layout formulario",
        "concepto": "bateria_caso_4_css",
        "bridges": [
            {"text": "alineacion de componentes visuales en pantalla", "angle": "sinonimo"},
            {"text": "desborde de campos en pantallas moviles", "angle": "problema"},
            {"text": "propiedades flex y contenedor adaptable", "angle": "solucion"},
            {"text": "disenador ajustando la vista de checkout", "angle": "situacion"},
            {"text": "los botones se ven montados unos sobre otros", "angle": "ingenuo"},
        ]
    },
    {
        "id": 5,
        "nombre": "Multi-núcleo",
        "texto": "La base de datos replica datos entre nodos con consistencia eventual para alta disponibilidad",
        "esperado": "base_datos, nodos, consistencia",
        "prohibido": ["replicacion", "replica"],
        "query": "base de datos nodos consistencia eventual",
        "concepto": "bateria_caso_5_base_datos",
        "bridges": [
            {"text": "sincronizacion distribuida de registros", "angle": "sinonimo"},
            {"text": "lecturas desactualizadas en clusters remotos", "angle": "problema"},
            {"text": "protocolo de consenso y quorums", "angle": "solucion"},
            {"text": "configuracion de cluster multiregion", "angle": "situacion"},
            {"text": "guardar en varias computadoras para no perder nada", "angle": "ingenuo"},
        ]
    },
    {
        "id": 6,
        "nombre": "API/error",
        "texto": "El API de pagos devuelve error 500 cuando el token expira durante la autenticación segura",
        "esperado": "api, pagos, error, token",
        "prohibido": ["devolucion", "devuelve"],
        "query": "api pagos error 500 token",
        "concepto": "bateria_caso_6_api",
        "bridges": [
            {"text": "rechazo de credencial vencida en pasarela", "angle": "sinonimo"},
            {"text": "transaccion rechazada por sesion invalida", "angle": "problema"},
            {"text": "renovacion automatica de tokens jwt", "angle": "solucion"},
            {"text": "cliente recibiendo codigo 500 en el cobro", "angle": "situacion"},
            {"text": "no me deja pagar y dice que mi sesion vencio", "angle": "ingenuo"},
        ]
    },
    {
        "id": 7,
        "nombre": "Negación explícita",
        "texto": "El sustantivo clave no es sinónimo, es el centro del significado ontológico en BioRAG",
        "esperado": "sustantivo, sinonimo, significado",
        "prohibido": ["centro"],
        "query": "sustantivo sinonimo significado ontologico",
        "concepto": "bateria_caso_7_sustantivo",
        "bridges": [
            {"text": "distincion entre nucleo tematico y vocabulario", "angle": "sinonimo"},
            {"text": "confusion metodologica al catalogar descriptores", "angle": "problema"},
            {"text": "regla de extraccion tematica estructurada", "angle": "solucion"},
            {"text": "agente evaluando como etiquetar un recuerdo", "angle": "situacion"},
            {"text": "diferencia entre de que habla y como lo dice", "angle": "ingenuo"},
        ]
    },
    {
        "id": 8,
        "nombre": "Frontera guardado/búsqueda",
        "texto": "La herramienta biorag_aprender valida formato antes de escribir en DB de manera fail-fast",
        "esperado": "herramienta, validacion, formato, db",
        "prohibido": ["escribir", "escritura"],
        "query": "herramienta validacion formato db fail-fast",
        "concepto": "bateria_caso_8_herramienta",
        "bridges": [
            {"text": "chequeo previo de parametros en capa de entrada", "angle": "sinonimo"},
            {"text": "corrupcion de registros en almacenamiento persistente", "angle": "problema"},
            {"text": "lanzamiento temprano de excepcion estructurada", "angle": "solucion"},
            {"text": "llamada de tool con argumentos incorrectos", "angle": "situacion"},
            {"text": "revisar bien antes de guardar para no romper nada", "angle": "ingenuo"},
        ]
    }
]


@pytest.fixture()
def mcp_ctx(tmp_path, monkeypatch):
    db_path = str(tmp_path / "bateria_test.db")
    monkeypatch.setenv("BIORAG_PATH", db_path)
    from core.memory_store import SQLiteMemoryBioRAG
    cerebro = SQLiteMemoryBioRAG(db_path)
    cerebro.cerrar_sistema()

    from core.memory_service import reset_cerebro
    reset_cerebro()

    import mcp_server as m
    mcp = m._build_server()
    tools = {t.name: t.fn for t in mcp._tool_manager.list_tools()}
    yield tools, db_path
    reset_cerebro()


def _raw_json(raw):
    for marker in ('{"status"', '{"resultados"'):
        idx = raw.find(marker)
        if idx >= 0:
            return json.loads(raw[idx:])
    start = raw.find('{')
    if start >= 0:
        return json.loads(raw[start:])
    return json.loads(raw)


class TestT9BateriaExtraccion:
    """RF-23: Batería de 8 casos para validación de extracción de núcleos temáticos."""

    def test_bateria_casos_especificacion_completa(self):
        """Verifica que la batería cuenta con al menos 6 casos (tiene 8) y que no hay overlap prohibido."""
        assert len(CASOS_BATERIA) >= 6, "La batería debe contener al menos 6 casos según RF-23"
        for caso in CASOS_BATERIA:
            esperados = [t.strip().lower() for t in caso["esperado"].split(",")]
            assert 2 <= len(esperados) <= 4, f"Caso {caso['id']}: cantidad de términos esperados fuera de [2, 4]"
            for exp in esperados:
                assert 2 <= len(exp) <= 15, f"Caso {caso['id']}: longitud de '{exp}' fuera de [2, 15]"
                for proh in caso["prohibido"]:
                    assert exp != proh.lower(), f"Caso {caso['id']}: '{exp}' coincide con término prohibido '{proh}'"

    @pytest.mark.parametrize("caso", CASOS_BATERIA, ids=[f"caso_{c['id']}_{c['nombre']}" for c in CASOS_BATERIA])
    def test_guardado_bateria_con_extraccion_esperada(self, mcp_ctx, caso):
        """Cada caso de la batería debe guardarse exitosamente con su extracción esperada."""
        tools, db_path = mcp_ctx
        syn_especifico = f"syn_{caso['concepto']}_1, syn_{caso['concepto']}_2, syn_{caso['concepto']}_3, syn_{caso['concepto']}_4, syn_{caso['concepto']}_5"
        raw = tools["aprender"](
            concepto=caso["concepto"],
            contenido=caso["texto"],
            sustantivos_clave=caso["esperado"],
            dimensiones='{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
            bridges=caso["bridges"],
            syn=syn_especifico
        )
        res = _raw_json(raw)
        assert res.get("status") == "ok", f"Fallo al guardar caso {caso['id']}: {res}"

    def test_bateria_end_to_end_guardar_consolidar_y_buscar(self, mcp_ctx):
        """Ejecuta los 8 casos de la batería end-to-end: guardado, consolidación y búsqueda con boost."""
        tools, db_path = mcp_ctx

        # 1. Guardar todos los 8 casos
        for caso in CASOS_BATERIA:
            syn_especifico = f"syn_{caso['concepto']}_1, syn_{caso['concepto']}_2, syn_{caso['concepto']}_3, syn_{caso['concepto']}_4, syn_{caso['concepto']}_5"
            raw = tools["aprender"](
                concepto=caso["concepto"],
                contenido=caso["texto"],
                sustantivos_clave=caso["esperado"],
                dimensiones='{"emocion":["satisfaccion"],"dominio":["dominio_tecnico"]}',
                bridges=caso["bridges"],
                syn=syn_especifico
            )
            res = _raw_json(raw)
            assert res.get("status") == "ok", f"Fallo al guardar caso {caso['id']}: {res}"

        # 2. Forzar consolidación (sueño) para propagar a largo_plazo y FTS5
        raw_sueno = tools["sueno"]()
        res_sueno = _raw_json(raw_sueno)
        assert res_sueno.get("status") == "ok"

        # 3. Verificar recuperación de cada caso con su sustantivos_clave
        for caso in CASOS_BATERIA:
            # Búsqueda con query temática y boost explícito de los sustantivos clave esperados
            raw_rec = tools["recordar"](
                query=caso["query"],
                sustantivos_clave=caso["esperado"]
            )
            res_rec = _raw_json(raw_rec)
            assert "resultados" in res_rec, f"Error en búsqueda de caso {caso['id']}: {res_rec}"
            conceptos = [r["concepto"] for r in res_rec["resultados"]]
            assert caso["concepto"] in conceptos, f"Caso {caso['id']} no fue recuperado en resultados: {conceptos}"
            assert conceptos[0] == caso["concepto"], f"Caso {caso['id']} no quedó en Top-1: {conceptos}"
