"""Rellenos con dimensiones REALISTAS: cada relleno recibe las dimensiones del recuerdo real
más parecido a su texto (FTS unicode61 + bm25 sobre sus palabras clave)."""
import sqlite3,sys,re,shutil
src,dst=sys.argv[1],sys.argv[2]; shutil.copy(src,dst)
c=sqlite3.connect(dst)
c.execute("delete from largo_plazo_dimensiones where concepto like 'relleno_%'")
dims={}
for con,d in c.execute("select concepto,dimension_id from largo_plazo_dimensiones"): dims.setdefault(con,[]).append(d)
rell=c.execute("select concepto, sinonimos, contenido from largo_plazo where concepto like 'relleno_%'").fetchall()
ok=0
for con,sin,cont in rell:
    ws=[w for w in re.findall(r"\w{4,}", (sin or "")+" "+(cont or "")[:300]) if not w.isdigit()][:12]
    if not ws: continue
    q=" OR ".join('"%s"'%w.replace('"','') for w in ws)
    try:
        rows=c.execute("select l.concepto from largo_plazo_fts_unicode f join largo_plazo l on l.rowid=f.rowid "
                       "where largo_plazo_fts_unicode match ? and l.concepto not like 'relleno_%' order by bm25(largo_plazo_fts_unicode) limit 5",(q,)).fetchall()
    except sqlite3.Error: continue
    for (r,) in rows:
        if r in dims:
            for d in dims[r]: c.execute("insert or ignore into largo_plazo_dimensiones(concepto,dimension_id) values(?,?)",(con,d))
            ok+=1; break
c.commit(); print("rellenos con dimensiones del vecino real más parecido:",ok,"de",len(rell))
