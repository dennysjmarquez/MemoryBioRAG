import re
import time

TTL = 1800

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


def _extraer_categoria(texto: str) -> str:
    texto_lower = texto.lower()
    for palabra, cat in _PALABRAS_CLAVE.items():
        if palabra in texto_lower:
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
    contexto = buffer_global.obtener()
    if not contexto:
        return None

    acciones_recientes = [c.get("accion", "") for c in contexto[-5:]]
    textos = [c.get("texto", "") for c in contexto if c.get("texto")]
    texto_completo = " ".join(textos)

    if len(texto_completo) < 80 and not fuerza:
        return None

    textual = texto_completo.lower()
    palabras_detectadas = {p for p in _PALABRAS_CLAVE if p in textual}
    emociones_detectadas = {val for key, val in _EMOCIONES_CLAVE.items() if key in textual}

    if not palabras_detectadas and not emociones_detectadas and not fuerza:
        return None

    if "aprender" in acciones_recientes:
        return None

    categoria = _extraer_categoria(texto_completo)
    clave = _generar_clave(texto_completo)
    if not clave:
        return None

    existentes, _ = cerebro.buscar_por_frase(clave, limite=1)
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



def registrar_accion(accion: str, texto: str = ""):
    buffer_global.agregar({"accion": accion, "texto": texto})
