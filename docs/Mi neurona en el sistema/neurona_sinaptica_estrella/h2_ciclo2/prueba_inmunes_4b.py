"""Ejecuta el UPDATE exacto de 4b (motor) y de 4b-propio (sustitución del laboratorio) sobre recuerdos protegidos."""
import re, sqlite3
src = open("core/memory/consolidation.py", encoding="utf-8").read()
old = """    if peso_medio_activo > 0.70:
        self.cursor.execute(\"\"\"
            UPDATE largo_plazo
            SET peso_sinaptico = ROUND(peso_sinaptico * 0.98, 2)
            WHERE estado = 'activo'
"""
new = old.replace("if peso_medio_activo > 0.70:", "if True:").replace(
    "WHERE estado = 'activo'\n", "WHERE estado = 'activo' AND peso_sinaptico > 0.70\n")
assert src.count(old) == 1
def update_de(s, marca):
    i = s.index(marca); j = s.index('"""', i) + 3; k = s.index('"""', j)
    return s[j:k]
sql = {"4b": update_de(src, "if peso_medio_activo > 0.70:"),
       "4bp": update_de(src.replace(old, new), "if True:\n        self.cursor.execute")}
filas = [  # concepto, peso, valencia, categoria, prioridad
    ("normal", 0.90, 0.0, 1, 3), ("valencia_alta", 0.90, 0.85, 1, 3), ("principle", 0.90, 0.0, 2, 3),
    ("protocol", 0.90, 0.0, 3, 3), ("prioridad0", 0.90, 0.0, 1, 0), ("prioridad1", 0.90, 0.0, 1, 1),
    ("bajo_umbral", 0.60, 0.0, 1, 3), ("cat_null", 0.90, 0.0, None, 3)]
for nombre, q in sql.items():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE categories(id INTEGER PRIMARY KEY, name TEXT)")
    c.executemany("INSERT INTO categories VALUES (?,?)", [(1, "General"), (2, "Principle"), (3, "Protocol")])
    c.execute("CREATE TABLE largo_plazo(concepto TEXT, peso_sinaptico REAL, estado TEXT, valencia_somatica REAL, categoria INTEGER, prioridad INTEGER)")
    c.executemany("INSERT INTO largo_plazo VALUES (?,?,'activo',?,?,?)", filas)
    c.execute(q)
    res = {k: v for k, v in c.execute("SELECT concepto, peso_sinaptico FROM largo_plazo")}
    print(nombre, " ".join("%s=%s" % (k, "ESCALADO" if v < dict((f[0], f[1]) for f in filas)[k] else "intacto") for k, v in res.items()))
    print("   SQL:", " ".join(q.split()))
