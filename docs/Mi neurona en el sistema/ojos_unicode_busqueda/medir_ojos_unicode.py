"""Mide el Paso 1 «ojos Unicode» (criterios en CRITERIOS.md, fijados antes de medir).

Uso (Antes = árbol sin el cambio, Después = árbol con el cambio):
  PYTHONHASHSEED=0 BIORAG_NEURONA=0 python medir_ojos_unicode.py --repo /ruta/arbol --salida x.json

Construye un mundo sintético nuevo en una carpeta temporal con `aprender()`. Nunca abre la DB
viva ni el snapshot. Cada consulta corre sobre una copia nueva de la base (sin cachés cruzadas).
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

RELOJ_FIJO = 1_793_059_200.0

# (concepto, contenido). La palabra buscada va EN MEDIO de una corrida larga, que es el caso
# que fallaba; el concepto nunca es la palabra buscada (sin atajo por nombre).
MUNDO = [
    ("晚餐食谱一", "今晚我炒蒜和番茄配米饭。"),
    ("晚餐食谱二", "今天烤了番薯和土豆当晚饭。"),            # distractor de 番茄 (comparte 番)
    ("城市安全记录", "昨天消防队员从屋顶救出三只猫。"),
    ("城市安全记录二", "消息说明天会下大雨。"),               # distractor de 消防 (comparte 消)
    ("周末活动", "我们在公园踢足球一直到天黑。"),
    ("周末活动二", "朋友受伤了脚很疼。"),                     # distractor de 足球 (comparte 足)
    ("健康笔记", "下午去医院看医生检查眼睛。"),
    ("旅行计划", "明天早上坐火车去上海开会。"),
    ("院子笔记", "院子里有一棵很老的树开花了。"),
    ("家の記録", "朝ごはんの後で猫が窓辺で寝ていた。"),
    ("通勤メモ", "今日は電車が遅れて会社に遅刻した。"),
    ("通勤メモ二", "電話で上司に遅刻を伝えた。"),             # distractor de 電車 (comparte 電)
    ("買い物", "スーパーでパンと牛乳を買った。"),
    ("休日", "先週は友達と海で泳いだ。"),
    ("春の思い出", "公園で桜を見ながら弁当を食べた。"),
    ("아침_기록", "아침에 사과를 먹고 학교에 갔다."),
    ("주말_기록", "주말에 친구와 영화를 봤다."),
    ("дневник_утро", "Утром я пил чай с лимоном и читал книгу."),
    ("receta_sopa", "La sopa de tomate lleva ajo y albahaca fresca."),
    ("bomberos_ciudad", "Los bomberos rescataron tres gatos del tejado."),
    ("train_trip", "Tomorrow morning I take the train to Shanghai."),
    ("garden_note", "An old tree in the garden is flowering again."),
]

# U1: (consulta, objetivo, distractor o None)
U1 = [
    ("番茄", "晚餐食谱一", "晚餐食谱二"),
    ("消防", "城市安全记录", "城市安全记录二"),
    ("足球", "周末活动", "周末活动二"),
    ("医生", "健康笔记", None),
    ("火车", "旅行计划", None),
    ("树", "院子笔记", None),
    ("猫", "家の記録", None),
    ("電車", "通勤メモ", "通勤メモ二"),
    ("パン", "買い物", None),
    ("友達", "休日", None),
    ("桜", "春の思い出", None),
]
# U3: consultas CJK cortas que no aparecen en ningún recuerdo
U3 = ["钢琴", "鉛筆", "雪", "ピザ"]
# U4: control fuera de CJK corto (no debe cambiar nada)
U4 = ["사과", "영화", "чай", "лимоном", "tomate", "bomberos gatos", "train Shanghai", "old tree",
      "番茄配米饭", "電車が遅れて", "公园踢足球", "receta 番茄配米饭"]
# U5: recuerdos ajenos (ninguno contiene los términos de U1)
AJENOS = [(f"ajeno_{i:02d}", t) for i, t in enumerate([
    "今天天气很好我们去看电影。", "妈妈在厨房做饺子。", "老师在黑板上写字。", "他每天早上跑步。",
    "图书馆里非常安静。", "我喜欢听古典音乐。", "这本小说很有意思。", "孩子们在操场上玩。",
    "明天要交作业了。", "弟弟正在学游泳。", "山上的空气很新鲜。", "她买了一条红裙子。",
    "昨日は雨が降っていた。", "母が台所で料理を作った。", "日本語の勉強は楽しい。", "駅の近くに本屋がある。",
    "夏休みに祖父の家へ行った。", "コーヒーを一杯飲んだ。", "新しい靴を買いました。", "宿題を忘れてしまった。",
    "오늘은 날씨가 좋다.", "도서관에서 공부했다.", "Вечером мы гуляли в парке.", "Он купил новую машину.",
    "El museo abre los domingos.", "Mi hermana estudia música.", "La biblioteca cierra tarde.",
    "The river flooded last spring.", "She paints landscapes at dawn.", "Our neighbor fixes bicycles.",
    "Quarterly report shows growth.", "La reunión se movió al jueves.", "我们讨论了新的预算。",
    "会議は来週に延期された。", "그는 매일 아침 커피를 마신다.", "Мы обсуждали бюджет.",
    "Kids built a sandcastle.", "El tren nocturno llega a las seis.", "新的规定下个月开始。", "会社の方針が変わった。",
])]


def crear_base(path, recuerdos):
    from core.memory_service import aprender
    from core.memory_store import SQLiteMemoryBioRAG
    db = SQLiteMemoryBioRAG(str(path))
    try:
        for c, t in recuerdos:
            aprender(db, c, t, consolidar=True)
        db.conn.commit()
        db.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        db.cerrar_sistema()


def buscar(base, q, carpeta):
    from core.memory_store import SQLiteMemoryBioRAG
    with tempfile.TemporaryDirectory(dir=carpeta) as d:
        copia = Path(d) / "c.db"
        shutil.copyfile(base, copia)
        db = SQLiteMemoryBioRAG(str(copia))
        try:
            t0 = time.perf_counter()
            res, _ = db.buscar_por_frase(q, profundidad="activos", limite=5, ignore_peso_sinaptico=True)
            ms = (time.perf_counter() - t0) * 1000
            return [[r[0], round(float(r[4]), 6)] for r in res[:5]], ms
        finally:
            db.cerrar_sistema()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0" or os.environ.get("BIORAG_NEURONA") != "0":
        p.error("Inicia con PYTHONHASHSEED=0 BIORAG_NEURONA=0")
    sys.path.insert(0, os.path.abspath(a.repo))
    os.chdir(a.repo)
    out = {"repo": os.path.abspath(a.repo)}
    with tempfile.TemporaryDirectory(prefix="ojos_unicode_") as tmp, \
            patch("time.time", return_value=RELOJ_FIJO):
        tmp = Path(tmp)
        base, crecida = tmp / "base.db", tmp / "crecida.db"
        os.environ["BIORAG_PATH"] = str(base)
        os.environ["BIORAG_NO_LOG"] = "1"
        crear_base(base, MUNDO)
        crear_base(crecida, MUNDO + AJENOS)
        tiempos = []

        def q(db, consulta):
            r, ms = buscar(db, consulta, tmp)
            tiempos.append(ms)
            return r

        u1 = []
        for consulta, obj, dis in U1:
            r = q(base, consulta)
            nombres = [x[0] for x in r]
            rango = nombres.index(obj) + 1 if obj in nombres else None
            rango_dis = nombres.index(dis) + 1 if dis in nombres else None
            u1.append({"q": consulta, "objetivo": obj, "rango": rango, "distractor": dis,
                       "rango_distractor": rango_dis, "top5": r,
                       "top5_crecida": q(crecida, consulta)})
        out["U1"] = u1
        out["U3"] = [{"q": c, "top5": q(base, c)} for c in U3]
        out["U4"] = [{"q": c, "top5": q(base, c)} for c in U4]
        try:
            from core.memory import cjk_corto
            out["U6_terminos_no"] = list(cjk_corto.terminos("の"))
        except ImportError:
            out["U6_terminos_no"] = None
        out["ms_mediana"] = round(sorted(tiempos)[len(tiempos) // 2], 2)
        out["ms_max"] = round(max(tiempos), 2)
    out["resumen"] = {
        "U1_top5": sum(x["rango"] is not None for x in u1),
        "U1_top1": sum(x["rango"] == 1 for x in u1),
        "U2_distractor_arriba": sum(1 for x in u1 if x["rango_distractor"] is not None
                                    and (x["rango"] is None or x["rango_distractor"] < x["rango"])),
        "U3_con_resultados": sum(bool(x["top5"]) for x in out["U3"]),
        "U5_top5_iguales": sum(x["top5"] == x["top5_crecida"] for x in u1),
    }
    Path(a.salida).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["resumen"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
