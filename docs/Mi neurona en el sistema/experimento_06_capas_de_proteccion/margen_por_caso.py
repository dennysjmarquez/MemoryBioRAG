"""Por cada margen ε: cuántos casos gana y pierde el campeón frente a la fórmula, en estudio y guardia.
Uso: python margen_por_caso.py ruta.db   (solo lectura)"""
import sys
from _cargar_estado import cargar

N, est, campeon = cargar(sys.argv[1])
for nombre in ("estudio", "guardia"):
    casos = getattr(est, nombre)
    h = N._rangos(None, casos, 5)
    for e in N.MARGENES:
        c = N._rangos(campeon, casos, 5, e)
        print(nombre, e, "gana", int(((h != 1) & (c == 1)).sum()), "pierde", int(((h == 1) & (c != 1)).sum()), "n", len(casos))
