"""Buffer de sesión + autoguardado.

Historia: nació en v2.2 (Interceptor V2, 2026-05-31) para guardar lo que los
agentes olvidaban guardar. Las reglas de escritura posteriores (búsqueda
previa, bridges, sustantivos clave) solo se aplicaron a ``aprender``, y este
camino quedó como el único que se las salta. En la práctica metía basura en la
corteza: consultas de ``recordar`` encadenadas, la salida de consola del sueño,
"activos:N dormidos:M", "a <--> b" y ecos de ``aprender`` (nodos duplicados),
con claves armadas con las 3 primeras palabras largas del búfer.

Comportamiento actual:
- El guardado heurístico por herramienta queda APAGADO por defecto. Se activa
  con ``BIORAG_AUTOGUARDADO_HEURISTICO=1`` (comportamiento histórico).
- El texto de las acciones de ``_ACCIONES_SIN_TEXTO`` nunca entra al búfer
  (solo queda la marca de la acción).
- ``contexto_fin`` guarda únicamente el ``resumen`` que escribe el agente, en
  la clave determinista ``sesion_<agente>_<AAAAMMDD>`` con el sinónimo
  ``auto_guardado`` para poder identificarlo y auditarlo.
- Las palabras clave y emociones se comparan como palabra completa ("mal" ya
  no matchea "normal"; "clave" ya no matchea "sustantivos_clave").
"""

import os
import re
import time

TTL = 1800

# Acciones cuyo TEXTO no es conocimiento: consultas, ecos de lo ya guardado y
# salidas de máquina. Se registra la acción (para la guarda "aprender
# reciente") pero sin texto.
_ACCIONES_SIN_TEXTO = frozenset({
    "recordar",
    "aprender",
    "consolidar",
    "introspeccion",
    "mapear",
    "vincular",
})

_SINONIMOS_RESUMEN_SESION = "auto_guardado,resumen_sesion"


def autoguardado_heuristico_activo() -> bool:
    """Flag leído en cada llamada (no al importar) para que tests y entornos
    puedan cambiarlo sin reiniciar el proceso."""
    return os.environ.get("BIORAG_AUTOGUARDADO_HEURISTICO", "0") == "1"

_PALABRAS_CLAVE = {
    "aprendi": "Lesson",
    "aprendí": "Lesson",
    "aprendido": "Lesson",
    "aprender": "Lesson",
    "leccion": "Lesson",
    "lección": "Lesson",
    "nuevo patron": "Architecture",
    "nuevo patrón": "Architecture",
    "recuerda": "Personal",
    "recordar": "Personal",
    "prefiero": "Personal",
    "prefiere": "Personal",
    "preferencia": "Personal",
    "no me gusta": "Lesson",
    "error comun": "Lesson",
    "error común": "Lesson",
    "no usar": "Lesson",
    "evitar": "Lesson",
    "mejor practica": "Principle",
    "mejor práctica": "Principle",
    "solucion": "Lesson",
    "solución": "Lesson",
    "resolver": "Lesson",
    "importante": "General",
    "atencion": "General",
    "atención": "General",
    "clave": "General",
    "critico": "General",
    "crítico": "General",
    "nunca": "Lesson",
    "siempre": "Principle",
    "regla": "Principle",
    "conclusion": "Lesson",
    "conclusión": "Lesson",
}


_EMOCIONES_CLAVE = {
    "te quiero": "emocion_afecto",
    "cariño": "emocion_afecto",
    "afecto": "emocion_afecto",
    "aprecio": "emocion_afecto",
    "amor": "emocion_afecto",
    "estimación": "emocion_afecto",
    "estimacion": "emocion_afecto",
    
    "error": "emocion_frustracion",
    "fallo": "emocion_frustracion",
    "problema": "emocion_frustracion",
    "mal": "emocion_frustracion",
    "molesto": "emocion_frustracion",
    "enojo": "emocion_frustracion",
    "rabia": "emocion_frustracion",
    "frustrado": "emocion_frustracion",
    "frustracion": "emocion_frustracion",
    
    "excelente": "emocion_satisfaccion",
    "logro": "emocion_satisfaccion",
    "satisfaccion": "emocion_satisfaccion",
    "alegria": "emocion_satisfaccion",
    "exito": "emocion_satisfaccion",
    "bien": "emocion_satisfaccion",
    "genial": "emocion_satisfaccion",
    
    "duda": "emocion_preocupacion",
    "preocupado": "emocion_preocupacion",
    "preocupación": "emocion_preocupacion",
    "riesgo": "emocion_preocupacion",
    "alerta": "emocion_preocupacion",
}


class SesionBuffer:
    def __init__(self, ttl=TTL):
        self._ttl = ttl
        self._buffer = []

    def limpiar_expirados(self):
        ahora = time.time()
        self._buffer = [e for e in self._buffer if ahora - e["ts"] < self._ttl]

    def agregar(self, entrada: dict):
        self.limpiar_expirados()
        self._buffer.append({"ts": time.time(), **entrada})
        self._buffer = self._buffer[-20:]

    def obtener(self):
        self.limpiar_expirados()
        return list(self._buffer)

    def limpiar(self):
        self._buffer = []


buffer_global = SesionBuffer()


def _contiene_termino(texto_lower: str, termino: str) -> bool:
    """Coincidencia por palabra completa (no subcadena)."""
    return re.search(r"(?<!\w)" + re.escape(termino) + r"(?!\w)", texto_lower) is not None


def _extraer_categoria(texto: str) -> str:
    texto_lower = texto.lower()
    for palabra, cat in _PALABRAS_CLAVE.items():
        if _contiene_termino(texto_lower, palabra):
            return cat
    return "General"


def _generar_clave(texto: str) -> str | None:
    palabras = re.findall(r"\b(\w{4,})\b", texto.lower())
    palabras = [p for p in palabras if p not in ("para", "como", "con", "que", "por", "los", "las", "una", "del")]
    if not palabras:
        palabras = re.findall(r"\b(\w{3,})\b", texto.lower())
    if not palabras:
        return None
    return "_".join(palabras[:3])


def analizar_y_autoguardar(cerebro, fuerza=False) -> dict | None:
    """Guardado heurístico histórico a partir del búfer.

    Sin ``fuerza`` solo corre si ``BIORAG_AUTOGUARDADO_HEURISTICO=1``.
    Con ``fuerza=True`` corre siempre (llamada explícita).
    """
    if not fuerza and not autoguardado_heuristico_activo():
        return None
    contexto = buffer_global.obtener()
    if not contexto:
        return None

    acciones_recientes = [c.get("accion", "") for c in contexto[-5:]]
    textos = [c.get("texto", "") for c in contexto if c.get("texto")]
    texto_completo = " ".join(textos)

    if len(texto_completo) < 80 and not fuerza:
        return None

    textual = texto_completo.lower()
    palabras_detectadas = {p for p in _PALABRAS_CLAVE if _contiene_termino(textual, p)}
    emociones_detectadas = {val for key, val in _EMOCIONES_CLAVE.items() if _contiene_termino(textual, key)}

    if not palabras_detectadas and not emociones_detectadas and not fuerza:
        return None

    if "aprender" in acciones_recientes:
        return None

    categoria = _extraer_categoria(texto_completo)
    clave = _generar_clave(texto_completo)
    if not clave:
        return None

    existentes, _ = cerebro.buscar_por_frase(clave, limite=1, modo_estricto=True)
    if existentes:
        return None

    sinonimos_list = list(palabras_detectadas) + list(emociones_detectadas)
    sinonimos = ",".join(sinonimos_list) if sinonimos_list else categoria
    cerebro.percibir_corto_plazo(
        concepto=clave,
        contenido=texto_completo[:1200].strip(),
        sinonimos=sinonimos,
        categoria=categoria,
    )

    buffer_global.limpiar()
    return {"concepto": clave, "categoria": categoria, "sinonimos": sinonimos}


def autoguardar_fin_sesion(cerebro, agente: str, resumen: str) -> dict | None:
    """Autoguardado de ``contexto_fin``.

    Por defecto guarda SOLO el ``resumen`` escrito por el agente, en la clave
    determinista ``sesion_<agente>_<AAAAMMDD>`` (dos cierres del mismo agente
    el mismo día se fusionan en el mismo nodo vía consolidar_concepto). Nada
    del búfer (consultas, salidas de herramientas) entra al contenido.
    Resumen vacío → no guarda nada.

    Con ``BIORAG_AUTOGUARDADO_HEURISTICO=1`` conserva el comportamiento
    histórico (``analizar_y_autoguardar(fuerza=True)``).
    """
    if autoguardado_heuristico_activo():
        return analizar_y_autoguardar(cerebro, fuerza=True)

    buffer_global.limpiar()
    resumen = (resumen or "").strip()
    if not resumen:
        return None

    agente_txt = (agente or "").strip() or "agente"
    agente_slug = re.sub(r"\W+", "_", agente_txt.lower()).strip("_") or "agente"
    fecha = time.strftime("%Y%m%d")
    clave = f"sesion_{agente_slug}_{fecha}"
    categoria = "General"
    cerebro.percibir_corto_plazo(
        concepto=clave,
        contenido=f"Resumen de sesión de {agente_txt} ({time.strftime('%Y-%m-%d')}): {resumen}",
        sinonimos=_SINONIMOS_RESUMEN_SESION,
        categoria=categoria,
    )
    return {"concepto": clave, "categoria": categoria, "sinonimos": _SINONIMOS_RESUMEN_SESION}


def registrar_accion(accion: str, texto: str = ""):
    if accion in _ACCIONES_SIN_TEXTO:
        texto = ""
    buffer_global.agregar({"accion": accion, "texto": texto})
