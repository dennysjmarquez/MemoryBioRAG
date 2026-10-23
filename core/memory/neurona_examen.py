"""Autoexamen de la neurona: cada recuerdo se hace sus propias preguntas.

POR QUÉ: para aprender hace falta saber cuál era la respuesta correcta, y en una
búsqueda real nadie lo dice (experimento 03). Pero cuando un recuerdo se
consolida, la respuesta SÍ se conoce: es ese recuerdo. Este módulo genera, desde
el propio recuerdo, consultas con respuesta conocida ("tapar y adivinar").

Es el mismo tipo de preguntas que `scripts/generar_casos_qa.py` (variante, typo,
sinónimo, pregunta natural, por tema, cruce de idioma), copiado aquí para que el
motor no dependa de `scripts/` (que no se distribuye con el motor). No genera
"literal" ni "dormido": esos casos ya los resuelve el motor sin neurona.

Determinista: el azar se siembra con el nombre del concepto, así que el mismo
recuerdo siempre produce las mismas preguntas (reproducible y auditable).
Ref: docs/Mi neurona en el sistema/experimento_04_autoaprendizaje/README.md
"""
import hashlib
import random

from core.stopwords import STOPWORDS

BILINGUAL_DICT = {
    "memoria": "recollection", "sistema": "framework", "archivo": "record",
    "archivos": "records", "datos": "inputs", "red": "infrastructure",
    "error": "anomaly", "fallo": "breakdown", "conexion": "integration",
    "guardar": "persist", "recuperar": "fetch", "buscar": "query",
    "servidor": "host", "cliente": "consumer", "base": "repository",
    "usuario": "operator", "autenticacion": "verification",
    "autorizacion": "permissioning", "seguridad": "hardening",
    "arquitectura": "blueprint", "leccion": "insight", "proyecto": "undertaking",
    "pruebas": "validations", "prueba": "validation",
    "configuracion": "adjustments", "interfaz": "viewport",
    "desarrollo": "engineering", "codigo": "syntax", "nube": "cluster",
    "ruta": "endpoint", "controlador": "handler", "modelo": "representation",
    "vista": "renderer", "actualizar": "modify", "borrar": "purge",
    "crear": "instantiate",
}
REVERSE_BILINGUAL_DICT = {v: k for k, v in BILINGUAL_DICT.items()}

SYNONYM_MAP = {
    "datos": "informacion", "informacion": "datos", "fallo": "error",
    "error": "falla", "guardar": "almacenar", "almacenar": "persister",
    "crear": "generar", "generar": "crear", "borrar": "eliminar",
    "eliminar": "remover", "conexion": "enlace", "configuracion": "ajustes",
    "servidor": "server",
}

PLANTILLAS = (
    "¿Cómo se hace {}?",
    "¿Dónde encuentro la info de {}?",
    "Me acuerdo de algo sobre {}",
    "¿Qué tenemos registrado para {}?",
    "Explicame el tema de {}",
    "¿Qué me podés decir sobre {}?",
)


def _rng(concepto):
    semilla = int(hashlib.sha256(concepto.encode("utf-8")).hexdigest()[:12], 16)
    return random.Random(semilla)


def _typo(rng, w):
    if len(w) <= 3:
        return w
    op = rng.choice(("swap", "delete", "insert"))
    c = list(w)
    if op == "swap":
        i = rng.randint(0, len(c) - 2)
        c[i], c[i + 1] = c[i + 1], c[i]
    elif op == "delete":
        c.pop(rng.randint(0, len(c) - 1))
    else:
        c.insert(rng.randint(0, len(c)), rng.choice("abcdefghijklmnopqrstuvwxyz"))
    return "".join(c)


def _variar(w):
    if w.endswith("cion"):
        return w[:-4] + "ciones"
    if w.endswith("ciones"):
        return w[:-6] + "cion"
    if w.endswith("ador"):
        return w[:-4] + "adores"
    if w.endswith("o") and len(w) > 3:
        return w[:-1] + "ando"
    if w.endswith("ado") and len(w) > 3:
        return w[:-3] + "ar"
    if w.endswith("ar") and len(w) > 3:
        return w[:-2] + "ado"
    if w.endswith("a") and len(w) > 3:
        return w[:-1] + "as"
    return w + "s" if not w.endswith("s") else w[:-1]


def _palabras_clave(texto):
    out = set()
    for w in (texto or "").lower().replace("_", " ").split():
        w = "".join(ch for ch in w if ch.isalnum())
        if w and w not in STOPWORDS and len(w) > 2:
            out.add(w)
    return sorted(out)


def preguntas(concepto, contenido, sinonimos=""):
    """Lista de (categoria, consulta) con respuesta conocida = `concepto`.

    Descarta las consultas que coinciden con el nombre del concepto (esas las
    resuelve el match exacto y no enseñan nada).
    """
    rng = _rng(concepto)
    palabras = [w for w in concepto.replace("_", " ").replace("-", " ").split() if w]
    nombre = " ".join(palabras).lower()
    syns = [s.strip() for s in (sinonimos or "").split(",") if s.strip()]
    out = []

    out.append(("variante_gramatical",
                " ".join(_variar(w) if rng.random() < .5 else w for w in palabras)))
    out.append(("typo",
                " ".join(_typo(rng, w) if rng.random() < .5 and len(w) > 3 else w for w in palabras)))
    trad = [BILINGUAL_DICT.get(w, REVERSE_BILINGUAL_DICT.get(w, w)) for w in palabras]
    if trad != palabras:
        out.append(("cruce_idioma", " ".join(trad)))
    if syns:
        out.append(("sinonimo", rng.choice(syns)))
    else:
        mapa = [SYNONYM_MAP.get(w, w) for w in palabras]
        if mapa != palabras:
            out.append(("sinonimo", " ".join(mapa)))
    out.append(("pregunta_natural", rng.choice(PLANTILLAS).format(" ".join(palabras))))
    tema = [w for w in _palabras_clave(contenido) if w not in palabras]
    if len(tema) >= 2:
        out.append(("por_tema", " ".join(rng.sample(tema, min(3, len(tema))))))

    vistas, limpias = set(), []
    for cat, q in out:
        qn = q.strip().lower()
        if not qn or qn == nombre or qn == concepto.lower() or qn in vistas:
            continue
        vistas.add(qn)
        limpias.append((cat, q.strip()))
    return limpias
