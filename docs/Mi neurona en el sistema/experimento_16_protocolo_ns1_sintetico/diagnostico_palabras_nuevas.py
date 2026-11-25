"""Diagnóstico posterior (declarado como tal en RESULTADOS.md): ¿por qué la neurona v2 sube recuerdos irrelevantes
de D_Ireal en el canal 2? Mide cuántas palabras no comunes de cada recuerdo conoce la memoria semántica congelada."""
import sys, numpy as np
sys.path.insert(0,'.')
import analizar as A, neurona as NS, mundo as M
D=A.cargar('/tmp/exp16','v2_s1_D'); V=A.cargar('/tmp/exp16','v2_s1_D_Ireal')
R=A.Rasgos(D); dv=A.docs_de(V); info=V['info']
def cobertura(d): 
    t=[x for x in d['T'] if R.ref.idf(x)>=NS.COMUN]; return sum(1 for x in t if x in R.sem.idx)/max(1,len(t))
cD=[cobertura(dv[c]) for c,i in info.items() if i['grupo']=='D']; cI=[cobertura(dv[c]) for c,i in info.items() if i['grupo']=='I']
print('cobertura semántica (palabras no comunes conocidas): D %.2f  I %.2f'%(np.mean(cD),np.mean(cI)))
cand=A.candidatos(V); J={n:i for i,n in enumerate(NS.NOMBRES_V2)}
sI,sD=[],[]
for r,c in cand.items():
    if info[r]['grupo']!='D': continue
    for v in c:
        x=R.X([(r,v)],dv,{})[0]
        (sI if info[v]['grupo']=='I' else (sD if M.relevancia(info,r,v)==0 else [])).append(x[J['sem_coseno_raras']])
print('sem_coseno_raras medio: vecino I (irrelevante) %.3f | vecino D irrelevante %.3f'%(np.mean(sI),np.mean(sD)))
