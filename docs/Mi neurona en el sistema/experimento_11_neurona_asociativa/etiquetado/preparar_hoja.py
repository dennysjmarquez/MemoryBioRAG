"""Prepara la hoja de 100 pares para que Dennys los marque a mano.

Sale de la COPIA del snapshot (/tmp/e11/dennys.db, solo lectura). La hoja NO muestra la fuerza
de la neurona ni de dónde salió cada par (para no influir). Eso queda en clave_no_mirar.json.

Grupos (mezclados al azar en la hoja):
  A  40  conexiones que existen hoy (no manuales) y que la neurona CONSERVA (top 10)
  B  30  conexiones que existen hoy (no manuales) y que la neurona SOLTARÍA
  C  15  pares que Gemini sacó a cuarentena pero la neurona les da fuerza >= .60 (desacuerdo)
  D  15  pares que NO existen hoy y que la neurona propondría (sus candidatos más fuertes)

Uso:  python preparar_hoja.py [ruta_a_la_db]
      Sin ruta usa el snapshot del repo (snapshots/qa_escape_qcr_20260811.db).
      Nunca lee la DB original: primero la copia a un archivo temporal y lee la copia.
      Semilla fija: siempre sale la misma hoja.

PRIVACIDAD: la hoja y la clave muestran trozos de tus recuerdos. No se suben a git
(.gitignore de esta carpeta), porque el repo es público.
"""
import csv
import json
import os
import shutil
import sys
import tempfile

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import agujas  # noqa: E402
import corpus  # noqa: E402
import neurona_asociativa as na  # noqa: E402

SEMILLA = 11
SNAPSHOT = os.path.abspath(os.path.join(AQUI, "..", "..", "..", "..", "snapshots", "qa_escape_qcr_20260811.db"))
CUPOS = {"A": 40, "B": 30, "C": 15, "D": 15}


PLANTILLA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>100 pares para marcar</title>
<style>
 body{background:#0b1426;color:#e8eef8;font-family:system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:20px}
 h1{font-size:22px} .sub{color:#8fa3c4}
 .barra{position:sticky;top:0;background:#0b1426;padding:10px 0;border-bottom:1px solid #2a3b5c;z-index:2;
        display:flex;gap:14px;align-items:center}
 .prog{flex:1;height:10px;background:#1b2a48;border-radius:6px;overflow:hidden}
 .prog div{height:100%;background:#5ee08f;width:0}
 .par{background:#111f3a;border:1px solid #2a3b5c;border-radius:12px;padding:14px;margin:14px 0}
 .par.hecho{border-color:#5ee08f}
 .num{color:#f2c14e;font-weight:bold}
 .dos{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:10px 0}
 .rec h3{margin:0 0 6px;font-size:14px;color:#4fd1e8;word-break:break-all}
 .rec p{margin:0;font-size:13px;color:#c9d4e8;line-height:1.4}
 .bot button{margin:4px 6px 0 0;padding:8px 14px;border-radius:8px;border:1px solid #2a3b5c;
             background:#1b2a48;color:#e8eef8;cursor:pointer;font-size:14px}
 .bot button.sel{background:#5ee08f;color:#0b1426;font-weight:bold}
 .bot button[data-r=no].sel{background:#ff6b6b}
 .bot button[data-r=momento].sel{background:#4fd1e8}
 .bot button[data-r=contradicen].sel{background:#ff9f43}
 .bot button[data-r=nose].sel{background:#8fa3c4}
 input.nota{width:100%;margin-top:8px;background:#0b1426;border:1px solid #2a3b5c;color:#e8eef8;
            border-radius:6px;padding:6px}
 .grande{padding:10px 16px;border-radius:8px;border:0;background:#f2c14e;color:#0b1426;font-weight:bold;cursor:pointer}
</style></head><body>
<h1>100 pares de tu memoria — ¿tienen que ver?</h1>
<p class="sub">No sabes qué opina la neurona ni de dónde salió cada par (para no influirte).
Tus respuestas se guardan solas en este navegador. Al terminar, pulsa <b>Descargar respuestas</b> y
pon el archivo <code>hoja_para_dennys.csv</code> en la carpeta <code>etiquetado/</code> (reemplaza al
que está). Luego: <code>python medir_hoja.py</code>.</p>
<p class="sub"><b>sí</b> = deberían estar conectados · <b>no</b> = no tienen que ver ·
<b>mismo momento</b> = no hablan de lo mismo pero son del mismo momento o proyecto ·
<b>se contradicen</b> = dicen cosas opuestas · <b>no sé</b></p>
<div class="barra"><span id="cuenta">0 / 100</span><div class="prog"><div id="pb"></div></div>
<button class="grande" id="bajar">Descargar respuestas</button></div>
<div id="lista"></div>
<script>
const DATOS = __DATOS__;
const OPC = [["si","sí"],["no","no"],["momento","mismo momento"],["contradicen","se contradicen"],["nose","no sé"]];
const KEY = "biorag_hoja_100_pares";
let R = JSON.parse(localStorage.getItem(KEY) || "{}");
function guardar(){ localStorage.setItem(KEY, JSON.stringify(R)); contar(); }
function contar(){ const n = DATOS.filter(d => R[d.id] && R[d.id].r).length;
  document.getElementById("cuenta").textContent = n + " / " + DATOS.length;
  document.getElementById("pb").style.width = (100*n/DATOS.length) + "%"; }
const lista = document.getElementById("lista");
for (const d of DATOS) {
  const c = document.createElement("div"); c.className = "par";
  const h = document.createElement("div"); h.className = "num"; h.textContent = "Par " + d.id; c.appendChild(h);
  const dos = document.createElement("div"); dos.className = "dos";
  for (const [n, t] of [[d.a, d.ta], [d.b, d.tb]]) {
    const r = document.createElement("div"); r.className = "rec";
    const t3 = document.createElement("h3"); t3.textContent = n;
    const p = document.createElement("p"); p.textContent = t;
    r.appendChild(t3); r.appendChild(p); dos.appendChild(r); }
  c.appendChild(dos);
  const bot = document.createElement("div"); bot.className = "bot";
  for (const [v, txt] of OPC) {
    const b = document.createElement("button"); b.textContent = txt; b.dataset.r = v;
    if (R[d.id] && R[d.id].r === v) b.classList.add("sel");
    b.onclick = () => { R[d.id] = Object.assign(R[d.id] || {}, {r: v});
      bot.querySelectorAll("button").forEach(x => x.classList.toggle("sel", x === b));
      c.classList.add("hecho"); guardar(); };
    bot.appendChild(b); }
  c.appendChild(bot);
  const nota = document.createElement("input"); nota.className = "nota"; nota.placeholder = "nota (opcional)";
  nota.value = (R[d.id] && R[d.id].nota) || "";
  nota.oninput = () => { R[d.id] = Object.assign(R[d.id] || {}, {nota: nota.value}); guardar(); };
  c.appendChild(nota);
  if (R[d.id] && R[d.id].r) c.classList.add("hecho");
  lista.appendChild(c); }
contar();
function campo(x){ x = String(x == null ? "" : x); return '"' + x.replace(/"/g, '""') + '"'; }
document.getElementById("bajar").onclick = () => {
  const filas = [["id","recuerdo_A","que_dice_A","recuerdo_B","que_dice_B",
                  "tu_respuesta (si / no / momento / contradicen / nose)","nota (opcional)"]];
  for (const d of DATOS) { const r = R[d.id] || {};
    filas.push([d.id, d.a, d.ta, d.b, d.tb, r.r || "", r.nota || ""]); }
  const csv = "\ufeff" + filas.map(f => f.map(campo).join(",")).join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
  a.download = "hoja_para_dennys.csv"; a.click(); };
</script></body></html>
"""


def resumen(texto, n=240):
    cuerpo = texto.split(". ", 1)[1] if ". " in texto else texto
    cuerpo = " ".join(cuerpo.split())
    return cuerpo[:n] + ("…" if len(cuerpo) > n else "")


def main():
    rng = np.random.default_rng(SEMILLA)
    origen = sys.argv[1] if len(sys.argv) > 1 else SNAPSHOT
    tmp = tempfile.mkdtemp(prefix="hoja_")
    copia = os.path.join(tmp, "copia.db")
    shutil.copyfile(origen, copia)             # se trabaja SIEMPRE sobre una copia
    mem = corpus.dennys(copia)
    con, sin, cuar, textos = mem["conceptos"], mem["sin"], mem["cuarentena"], mem["textos"]
    m = agujas.Memoria(textos, orden=mem["orden"], etiquetas=mem["etiquetas"])
    p = na.cargar()

    pares = sorted(sin)
    f = na.fuerza(m.agujas(pares), agujas.NOMBRES_TODAS, p=p)
    k10 = na.competencia(f, pares, 10)
    no_manual = [i for i, k in enumerate(pares) if sin[k][0] not in ("manual", "manual_v7", "test")]
    A = [i for i in no_manual if k10[i]]
    B = [i for i in no_manual if not k10[i]]

    no_g = sorted(k for k, v in cuar.items() if v[2] == 0 and v[3] != "manual" and "prueba" not in v[0]
                  and k not in sin)
    fg = na.fuerza(m.agujas(no_g), agujas.NOMBRES_TODAS, p=p)
    C = [i for i in range(len(no_g)) if fg[i] >= 0.60]

    existentes = set(sin) | set(cuar)
    cand = [k for k in m.candidatos(rng=np.random.default_rng(0)) if k not in existentes]
    fc = na.fuerza(m.agujas(cand), agujas.NOMBRES_TODAS, p=p)
    kc = na.competencia(fc, cand, 10)
    D = [i for i in range(len(cand)) if kc[i] and fc[i] >= 0.60]

    filas, clave, usados = [], {}, set()

    def tomar(grupo, idx, lista_pares, fuerzas, tipo_de):
        elegidos = rng.choice(len(idx), size=min(CUPOS[grupo], len(idx)), replace=False)
        for j in elegidos:
            i = idx[j]
            a, b = lista_pares[i]
            if (a, b) in usados:
                continue
            usados.add((a, b))
            filas.append((grupo, a, b, float(fuerzas[i]), tipo_de(lista_pares[i])))

    tomar("A", A, pares, f, lambda k: sin[k][0])
    tomar("B", B, pares, f, lambda k: sin[k][0])
    tomar("C", C, no_g, fg, lambda k: "cuarentena_gemini")
    tomar("D", D, cand, fc, lambda k: "no_existe_hoy")
    rng.shuffle(filas)

    ruta_hoja = os.path.join(AQUI, "hoja_para_dennys.csv")
    with open(ruta_hoja, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "recuerdo_A", "que_dice_A", "recuerdo_B", "que_dice_B",
                    "tu_respuesta (si / no / momento / contradicen / nose)", "nota (opcional)"])
        for n, (g, a, b, fz, t) in enumerate(filas, 1):
            w.writerow([n, con[a], resumen(textos[a]), con[b], resumen(textos[b]), "", ""])
            clave[n] = {"grupo": g, "a": con[a], "b": con[b], "fuerza": round(fz, 3), "tipo_hoy": t}
    datos = [{"id": n, "a": con[a], "ta": resumen(textos[a], 400), "b": con[b], "tb": resumen(textos[b], 400)}
             for n, (g, a, b, fz, t) in enumerate(filas, 1)]
    html = PLANTILLA.replace("__DATOS__", json.dumps(datos, ensure_ascii=False).replace("</", "<\\/"))
    with open(os.path.join(AQUI, "hoja_para_dennys.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    resumen_grupos = {g: {"en_hoja": sum(1 for v in clave.values() if v["grupo"] == g),
                          "poblacion": len(x)} for g, x in (("A", A), ("B", B), ("C", C), ("D", D))}
    json.dump({"semilla": SEMILLA, "grupos": resumen_grupos, "pares": clave},
              open(os.path.join(AQUI, "clave_no_mirar.json"), "w"), ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    print("ok", ruta_hoja, len(filas), "pares |", resumen_grupos)


if __name__ == "__main__":
    main()
