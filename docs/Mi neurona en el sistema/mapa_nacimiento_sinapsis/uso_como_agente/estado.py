"""Foto de la tabla sinapsis de la copia y diff contra la foto anterior (guardada en /tmp/agente/foto.json)."""
import sqlite3, json, os, sys, collections
c = sqlite3.connect('file:/tmp/agente/cerebro.db?mode=ro', uri=True)
filas = {f"{o}|{d}": [t, round(p, 4), u is not None] for o, d, t, p, u in c.execute("SELECT origen,destino,tipo,peso,ultimo_uso FROM sinapsis")}
lp = dict(c.execute("SELECT 'activos',COUNT(*) FROM largo_plazo WHERE estado='activo' UNION ALL SELECT 'cp',COUNT(*) FROM corto_plazo UNION ALL SELECT 'lat',COUNT(*) FROM sinapsis_latentes UNION ALL SELECT 'cuar',COUNT(*) FROM sinapsis_cuarentena"))
print("totales:", len(filas), lp, dict(collections.Counter(v[0] for v in filas.values())))
F = '/tmp/agente/foto.json'
if os.path.exists(F) and '--reset' not in sys.argv:
    prev = json.load(open(F))
    nuevas = [k for k in filas if k not in prev]; muertas = [k for k in prev if k not in filas]
    cambio = [k for k in filas if k in prev and filas[k][:2] != prev[k][:2]]
    uso = [k for k in filas if k in prev and filas[k][2] and not prev[k][2]]
    print(f"nuevas={len(nuevas)} borradas={len(muertas)} peso/tipo cambiado={len(cambio)} ultimo_uso estrenado={len(uso)}")
    print(" nuevas por tipo:", dict(collections.Counter(filas[k][0] for k in nuevas)))
    print(" borradas por tipo:", dict(collections.Counter(prev[k][0] for k in muertas)))
    print(" cambios por tipo:", dict(collections.Counter((prev[k][0], filas[k][0]) for k in cambio)))
    import statistics
    sube=[k for k in cambio if filas[k][1]>prev[k][1]]; baja=[k for k in cambio if filas[k][1]<prev[k][1]]
    print(" suben:",dict(collections.Counter(filas[k][0] for k in sube)),"bajan:",dict(collections.Counter(filas[k][0] for k in baja)))
    print(" deltas que suben (muestra):",collections.Counter(round(filas[k][1]-prev[k][1],3) for k in sube).most_common(5))
    man = [(k, prev[k][1], filas[k][1]) for k in cambio if prev[k][0] in ('manual', 'manual_v7')]
    print(" MANUALES con peso cambiado:", man[:10], len(man))
    for k in nuevas[:int(os.environ.get('N', 8))]: print("   +", k, filas[k])
json.dump(filas, open(F, 'w'))
