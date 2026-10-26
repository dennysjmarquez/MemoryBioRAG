"""Copia la memoria crecida y le da a cada relleno las dimensiones de un recuerdo real al azar
(mantiene la proporción real: los recuerdos reales casi siempre traen dimensiones)."""
import sqlite3,sys,random,shutil
src,dst=sys.argv[1],sys.argv[2]; shutil.copy(src,dst)
c=sqlite3.connect(dst); rnd=random.Random(11)
reales=[r[0] for r in c.execute("select distinct concepto from largo_plazo_dimensiones")]
dims={}
for con,d in c.execute("select concepto,dimension_id from largo_plazo_dimensiones"): dims.setdefault(con,[]).append(d)
sin=[r[0] for r in c.execute("select concepto from largo_plazo where concepto like 'relleno_%'")]
# misma proporción que los reales (763/866)
n=0
for con in sin:
    if rnd.random() < 763/866:
        for d in dims[rnd.choice(reales)]:
            c.execute("insert or ignore into largo_plazo_dimensiones(concepto,dimension_id) values(?,?)",(con,d)); 
        n+=1
c.commit(); print("rellenos con dimensiones:",n,"de",len(sin))
