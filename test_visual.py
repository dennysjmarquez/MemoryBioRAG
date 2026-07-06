import sqlite3
from core.semantica import init_semantica_table, auto_aprender_desde_sinonimos

conn = sqlite3.connect(':memory:')
cursor = conn.cursor()
init_semantica_table(cursor)

print("--- ESCENARIO 1: Aprendemos algo sobre 'Mantenimiento de Servidores' ---")
syns_1 = "mantenimiento de servidores, soporte tecnico, it ops"
print(f"Sinónimos proveídos por el agente: '{syns_1}'")
auto_aprender_desde_sinonimos(cursor, syns_1)

cursor.execute("SELECT termino, equivalente FROM semantica WHERE termino='mantenimiento de servidores' OR equivalente='mantenimiento de servidores'")
print("\nConexiones directas creadas en la Base de Datos para 'mantenimiento de servidores':")
for t, e in cursor.fetchall():
    print(f"   [ {t} ] <---- se asocia con ----> [ {e} ]")

print("\n\n--- ESCENARIO 2: Más tarde, aprendemos sobre 'Help Desk' ---")
syns_2 = "soporte tecnico, help desk, asistencia a usuarios"
print(f"Sinónimos proveídos por el agente: '{syns_2}'")
auto_aprender_desde_sinonimos(cursor, syns_2)

cursor.execute("SELECT termino, equivalente FROM semantica WHERE termino='soporte tecnico'")
print("\nConexiones directas creadas en la Base de Datos para 'soporte tecnico' (El puente):")
for t, e in cursor.fetchall():
    print(f"   [ {t} ] <---- se asocia con ----> [ {e} ]")

