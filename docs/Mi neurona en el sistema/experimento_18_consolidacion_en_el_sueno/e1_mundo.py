"""Experimento 18, E1 — mundo con estructura declarada (PROTOCOLO_V3.md §3). Semilla 18.

Textos: mundos_espejo.py. Estructura (dimensiones y sustantivos clave) generada con el MISMO azar en los
4 idiomas, así que solo cambia el texto. Categoría única y sin sinónimos.
No toca el motor ni ninguna base.
"""
import random

from mundos_espejo import D, I, TEMAS

IDIOMAS = ["es", "en", "zh", "ja"]

# sustantivo clave de cada tema (escrito a mano) y pozos de genéricos, por idioma
CLAVE_TEMA = {
    "es": ["tomate", "bomberos", "astronomía", "jardín", "base de datos", "fútbol", "salud", "viaje"],
    "en": ["tomato", "firefighters", "astronomy", "garden", "database", "football", "health", "trip"],
    "zh": ["番茄", "消防", "天文", "花园", "数据库", "足球", "健康", "旅行"],
    "ja": ["トマト", "消防", "天体", "庭", "データベース", "サッカー", "健康", "旅行"],
}
GENERICOS_D = {
    "es": ["nota", "día", "idea", "plan", "lista"],
    "en": ["note", "day", "idea", "plan", "list"],
    "zh": ["笔记", "日子", "想法", "计划", "清单"],
    "ja": ["メモ", "日", "アイデア", "計画", "リスト"],
}
GENERICOS_I = {
    "es": ["trámite", "papeles", "cita", "recibo", "agenda"],
    "en": ["paperwork", "papers", "appointment", "receipt", "agenda"],
    "zh": ["手续", "文件", "预约", "收据", "日程"],
    "ja": ["手続き", "書類", "予約", "領収書", "日程"],
}
P_DIM_TEMA, P_CLAVE_TEMA, P_GENERICO = 0.707, 0.548, 0.5


def nombre(i, irrelevante=False):
    return ("irrelevante_%d" % i) if irrelevante else ("%s_%d" % (TEMAS[i // 3], i % 3))


def generar(catalogo):
    """Devuelve {idioma: {'D': [eventos], 'I': [eventos]}} y la estructura usada (para auditar)."""
    dom, cual = catalogo["dominio"], catalogo["cualidad"]
    assert len(dom) >= 10 and len(cual) >= 10
    r = random.Random(18)
    plan_D = []
    for i in range(24):
        t = i // 3
        dims = {"cualidad": [r.choice(cual[:5])]}
        if r.random() < P_DIM_TEMA:
            dims["dominio"] = [dom[t]]
        usa_clave = r.random() < P_CLAVE_TEMA
        gen = r.randrange(5) if r.random() < P_GENERICO else None
        plan_D.append((dims, usa_clave, gen))
    plan_I = []
    for k in range(8):
        dims = {"cualidad": [r.choice(cual[5:10])], "dominio": [dom[8 + (k % 2)]]}
        gen = r.randrange(5) if r.random() < P_GENERICO else None
        plan_I.append((dims, gen))

    out = {}
    for lg in IDIOMAS:
        ev_D = []
        for i, (dims, usa_clave, gen) in enumerate(plan_D):
            sk = ([CLAVE_TEMA[lg][i // 3]] if usa_clave else []) + ([GENERICOS_D[lg][gen]] if gen is not None else [])
            ev_D.append({"concepto": nombre(i), "contenido": D[lg][i], "syn": "", "cat": "General",
                         "dims": dims, "sk": ",".join(sk), "tema": i // 3})
        ev_I = []
        for k, (dims, gen) in enumerate(plan_I):
            sk = [GENERICOS_I[lg][gen]] if gen is not None else []
            ev_I.append({"concepto": nombre(k, True), "contenido": I[lg][k], "syn": "", "cat": "General",
                         "dims": dims, "sk": ",".join(sk), "tema": None})
        out[lg] = {"D": ev_D, "I": ev_I}
    return out
