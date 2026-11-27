"""Paso 3, capa V: corpus públicos → recuerdos con documento (la verdad) y partición por documento.

Protocolo: ../PROTOCOLO_PASO3.md §4 (capa V) y §9 (decisiones del 27-11). Nada de esto toca el motor.

Fuentes (fijadas por commit; se clonan superficialmente en /tmp/capa_V/fuentes). El corpus completo no se sube al
repositorio, solo el manifiesto con licencias y huellas. Excepción (27-11): paquete_ciego/ con es (CC BY 4.0, con
atribución) y zh (dominio público) para la sesión aislada:
  es  UD_Spanish-AnCora   CC BY 4.0           noticias; `# newdoc id`; sin párrafos → bloques de oraciones
  en  UD_English-EWT      CC BY-SA 4.0        web (blogs, correos, reseñas, foros); `# newdoc` y `# newpar`
  zh  Ac-heron/luxun      dominio público     ensayos y relatos de Lu Xun (†1936), 全集; el repositorio no declara
                                              licencia; se quitan las llamadas a notas editoriales 〔n〕 y las notas
  ja  aozorahack/aozorabunko_text  dominio público  Aozora Bunko: Akutagawa (000879), Miyazawa (000081),
                                              Terada (000042); se quitan ruby 《》, ｜, ［＃…］, cabecera y pie (底本)
Por qué no UD GSD zh/ja (candidatos del protocolo): zh-GSD no trae `newdoc` y ja-GSD pone un `newdoc` por oración;
sin límites de documento no hay verdad «mismo documento». UD PUD sigue fuera (decisión del 27-11).

Recuerdo = párrafos consecutivos de un mismo documento, unidos hasta MIN caracteres (sin pasar de MAX; un párrafo
más largo se corta por oraciones). Como mucho POR_DOC recuerdos por documento (los primeros), para que una novela no
domine. Documentos barajados con semilla fija; se toman N = 1690 recuerdos por idioma (EWT da 1697).
Partición por documento (sha256 del id de documento): 20 % Guardia sellada, 20 % Validación, 60 % Estudio.
El Paso 3 no toca la Guardia: sus recuerdos se ingieren (como en el uso real) pero no entran en ningún análisis.

Uso:  python corpus_v.py   → /tmp/capa_V/corpus_{es,en,zh,ja}.json + resultados/manifiesto_corpus.json
"""
import glob
import hashlib
import json
import os
import random
import re
import subprocess
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
TMP = "/tmp/capa_V"
FUENTES = os.path.join(TMP, "fuentes")
RES = os.path.join(AQUI, "resultados")
N = int(os.environ.get("CAPA_V_N", "1690"))   # EWT (en) da 1697: mismo N en los 4 idiomas
POR_DOC = 8
SEMILLA = 2711
MIN = {"es": 250, "en": 250, "zh": 100, "ja": 100}
MAX = {"es": 900, "en": 900, "zh": 350, "ja": 350}

REPOS = {
    "es": ("https://github.com/UniversalDependencies/UD_Spanish-AnCora.git",
           "3ea1f747220979d91787a6d04b85734a42bf22a4", None, "CC BY 4.0"),
    "en": ("https://github.com/UniversalDependencies/UD_English-EWT.git",
           "491be069d36e378f67c29f183699eea88308ea42", None, "CC BY-SA 4.0"),
    "zh": ("https://github.com/Ac-heron/luxun.git",
           "b859e5043211b9ead7417ba3f5776e81eaf9213c", None,
           "dominio público (Lu Xun, †1936); el repositorio no declara licencia"),
    "ja": ("https://github.com/aozorahack/aozorabunko_text.git",
           "0984f7dc18a2270bdfd2ff99bf14fd1b3ebb4f65", ["cards/000879", "cards/000081", "cards/000042"],
           "dominio público (Aozora Bunko: obras con derechos vencidos); el espejo no declara licencia"),
}


def traer(idioma):
    url, commit, sparse, _lic = REPOS[idioma]
    d = os.path.join(FUENTES, idioma)
    if not os.path.isdir(os.path.join(d, ".git")):
        os.makedirs(FUENTES, exist_ok=True)
        args = ["git", "clone", "-q", "--depth", "1"]
        if sparse:
            args += ["--filter=blob:none", "--sparse"]
        subprocess.run(args + [url, d], check=True)
        if sparse:
            subprocess.run(["git", "-C", d, "sparse-checkout", "set"] + sparse, check=True)
    real = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if real != commit:   # la rama avanzó: se intenta fijar el commit registrado
        subprocess.run(["git", "-C", d, "fetch", "-q", "--depth", "1", "origin", commit], check=True)
        subprocess.run(["git", "-C", d, "checkout", "-q", commit], check=True)
    return d


# ------------------------------------------------------------------ lectura por fuente → [(doc_id, [párrafos])]
def leer_ud(d, por_parrafo):
    docs, actual, par, sent = [], None, [], []

    def cerrar_par():
        nonlocal par
        if par:
            actual[1].append(" ".join(par))
        par = []
    for f in sorted(glob.glob(os.path.join(d, "*.conllu"))):
        for linea in open(f, encoding="utf-8"):
            linea = linea.rstrip("\n")
            if linea.startswith("# newdoc"):
                if actual:
                    cerrar_par()
                m = re.search(r"id\s*=\s*(\S+)", linea)
                actual = (m.group(1) if m else "doc%d" % len(docs), [])
                docs.append(actual)
            elif linea.startswith("# newpar") and por_parrafo and actual:
                cerrar_par()
            elif linea.startswith("# text = ") and actual:
                par.append(linea[9:].strip())
                if not por_parrafo:   # sin párrafos: cada oración es una pieza; se agrupan después
                    cerrar_par()
        if actual:
            cerrar_par()
    return [(i, ps) for i, ps in docs if ps]


def leer_luxun(d):
    docs = []
    for f in sorted(glob.glob(os.path.join(d, "全集", "*", "*.md"))):
        if "目录" in os.path.basename(f):
            continue
        txt = open(f, encoding="utf-8", errors="replace").read().replace("```", "")
        # las notas editoriales van al final, desde la primera línea que empieza por 〔1〕 o tras «注释»
        corte = re.search(r"\n\s*(注\s*释|〔1〕)", txt)
        cuerpo = txt[:corte.start()] if corte else txt
        cuerpo = re.sub(r"〔\d+〕", "", cuerpo)
        pars, cur = [], ""
        for linea in cuerpo.split("\n"):
            if linea.startswith("　　") or not linea.strip():   # sangría = párrafo nuevo; línea vacía = corte
                if cur.strip():
                    pars.append(cur.strip())
                cur = linea.strip()
            else:
                cur += linea.strip()
        if cur.strip():
            pars.append(cur.strip())
        pars = [p for p in pars if len(p) >= 15]   # títulos y firmas sueltas
        if pars:
            docs.append(("luxun/" + os.path.relpath(f, os.path.join(d, "全集")), pars))
    return docs


def leer_aozora(d):
    docs = []
    for f in sorted(glob.glob(os.path.join(d, "cards", "*", "files", "*", "*.txt"))):
        raw = open(f, "rb").read()
        try:
            txt = raw.decode("cp932")
        except UnicodeDecodeError:
            continue
        txt = txt.replace("\r\n", "\n")
        partes = re.split(r"\n-{20,}\n", txt)
        cuerpo = partes[2] if len(partes) >= 3 else txt
        cuerpo = re.split(r"\n底本[:：]", cuerpo)[0]
        cuerpo = re.sub(r"《[^》]*》", "", cuerpo)
        cuerpo = re.sub(r"［＃[^］]*］", "", cuerpo).replace("｜", "").replace("※", "")
        pars = [p.strip().strip("　") for p in cuerpo.split("\n")]
        pars = [p for p in pars if len(p) >= 15]
        if pars:
            docs.append(("aozora/" + os.path.relpath(f, os.path.join(d, "cards")), pars))
    # una obra puede venir en dos archivos (ruby y sin ruby, o versiones): se deja la primera por id de obra
    vistos, out = set(), []
    for i, ps in docs:
        obra = i.split("/")[-2].split("_")[0] if "/" in i else i
        if obra in vistos:
            continue
        vistos.add(obra)
        out.append((i, ps))
    return out


_FIN = re.compile(r"(?<=[\.\!\?。！？])\s*")


def recuerdos_de(pars, idioma):
    lo, hi = MIN[idioma], MAX[idioma]
    piezas = []
    for p in pars:
        if len(p) <= hi:
            piezas.append(p)
            continue
        cur = ""
        for o in [x for x in _FIN.split(p) if x]:
            if cur and len(cur) + len(o) > hi:
                piezas.append(cur)
                cur = ""
            cur += ("" if idioma in ("zh", "ja") or not cur else " ") + o
        if cur:
            piezas.append(cur)
    out, cur = [], ""
    for p in piezas:
        if cur and len(cur) + len(p) > hi:
            if len(cur) >= lo:
                out.append(cur)
            cur = ""
        cur += ("" if idioma in ("zh", "ja") or not cur else "\n") + p
        if len(cur) >= lo:
            out.append(cur)
            cur = ""
    if len(cur) >= lo:
        out.append(cur)
    return [unicodedata.normalize("NFC", x[:hi]) for x in out]


def particion(doc_id):
    h = int(hashlib.sha256(("capaV|" + doc_id).encode()).hexdigest(), 16) % 100
    return "G" if h < 20 else ("V" if h < 40 else "E")


def preparar(idioma):
    d = traer(idioma)
    docs = {"es": lambda: leer_ud(d, False), "en": lambda: leer_ud(d, True),
            "zh": lambda: leer_luxun(d), "ja": lambda: leer_aozora(d)}[idioma]()
    g = random.Random("%d|%s" % (SEMILLA, idioma))
    g.shuffle(docs)
    out, n_docs = [], 0
    for doc_id, pars in docs:
        rs = recuerdos_de(pars, idioma)[:POR_DOC]
        if not rs:
            continue
        n_docs += 1
        part = particion(doc_id)
        for k, r in enumerate(rs):
            out.append({"doc": doc_id, "k": k, "part": part, "contenido": r})
        if len(out) >= N:
            break
    out = out[:N]
    for r in out:   # id opaco: no delata documento ni orden
        r["rid"] = idioma + hashlib.sha256(("rid|%s|%d" % (r["doc"], r["k"])).encode()).hexdigest()[:8]
    assert len({r["rid"] for r in out}) == len(out)
    json.dump(out, open(os.path.join(TMP, "corpus_%s.json" % idioma), "w"), ensure_ascii=False)
    por_doc = {}
    for r in out:
        por_doc.setdefault(r["doc"], []).append(r)
    largos = sorted(len(r["contenido"]) for r in out)
    return {"fuente": REPOS[idioma][0], "commit": REPOS[idioma][1], "subconjunto": REPOS[idioma][2],
            "licencia": REPOS[idioma][3], "documentos_disponibles": len(docs), "documentos_usados": len(por_doc),
            "recuerdos": len(out), "docs_con_2_o_mas": sum(1 for v in por_doc.values() if len(v) >= 2),
            "por_particion": {p: sum(1 for r in out if r["part"] == p) for p in "EVG"},
            "largo_mediana": largos[len(largos) // 2] if largos else 0,
            "huella": hashlib.sha256(json.dumps(out, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}


def main():
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(RES, exist_ok=True)
    man = {"N": N, "por_doc": POR_DOC, "semilla": SEMILLA, "min": MIN, "max": MAX,
           "particion": "sha256('capaV|'+doc) % 100: <20 G, <40 V, resto E", "idiomas": {}}
    for idioma in ("es", "en", "zh", "ja"):
        man["idiomas"][idioma] = preparar(idioma)
        print(idioma, json.dumps(man["idiomas"][idioma], ensure_ascii=False), flush=True)
    json.dump(man, open(os.path.join(RES, "manifiesto_corpus%s.json" % ("" if N == 1690 else "_n%d" % N)), "w"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
