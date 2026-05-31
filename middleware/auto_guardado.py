import re
import time

TTL = 1800

_PALABRAS_CLAVE = {
    "aprendi": "leccion",
    "aprendido": "leccion",
    "aprender": "leccion",
    "leccion": "leccion",
    "lección": "leccion",
    "nuevo patron": "patron",
    "nuevo patrón": "patron",
    "recuerda": "preferencia",
    "recordar": "preferencia",
    "prefiero": "preferencia",
    "prefiere": "preferencia",
    "preferencia": "preferencia",
    "no me gusta": "anti-patron",
    "error comun": "error",
    "error común": "error",
    "no usar": "anti-patron",
    "evitar": "anti-patron",
    "mejor practica": "buena_practica",
    "mejor práctica": "buena_practica",
    "solucion": "solucion",
    "solución": "solucion",
    "resolver": "solucion",
    "importante": "importante",
    "atencion": "importante",
    "atención": "importante",
    "clave": "importante",
    "critico": "importante",
    "crítico": "importante",
    "nunca": "anti-patron",
    "siempre": "regla",
    "regla": "regla",
    "conclusion": "leccion",
    "conclusión": "leccion",
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
    return "auto"


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

    if not palabras_detectadas and not fuerza:
        return None

    if "guardar" in acciones_recientes:
        return None

    categoria = _extraer_categoria(texto_completo)
    clave = _generar_clave(texto_completo)
    if not clave:
        return None

    existentes, _ = cerebro.buscar_por_frase(clave, limite=1)
    if existentes:
        return None

    sinonimos = ",".join(palabras_detectadas) if palabras_detectadas else categoria
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
