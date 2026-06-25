import re
import time

def escanear_familiaridad(user_input, cerebro):
    """
    Escanea la entrada del usuario en busca de conceptos familiares en largo plazo.
    Busca en clave y en contenido. Utiliza coincidencia exacta de tokens, similitud
    difusa por Jaccard y coincidencia en contenido.
    """
    # Extraer palabras de la entrada del usuario (limpiando puntuación)
    tokens = set(re.findall(r'\b\w{3,}\b', user_input.lower()))
    conceptos_familiares = []

    # Cargar todos los conceptos activos de largo plazo con su contenido
    cerebro.cursor.execute("SELECT concepto, contenido FROM largo_plazo WHERE estado = 'activo'")
    nodos_activos = cerebro.cursor.fetchall()

    for nodo, contenido in nodos_activos:
        # 1. Coincidencia exacta de token completo en clave
        if nodo in tokens:
            conceptos_familiares.append(nodo)
            continue
        
        # 2. Familiaridad difusa: Jaccard contra los tokens de la entrada
        encontrado = False
        for token in tokens:
            sim = cerebro._calcular_jaccard(token, nodo)
            if sim >= 0.55:
                conceptos_familiares.append(nodo)
                encontrado = True
                break
        
        if encontrado:
            continue

        # 3. Buscar tokens en el contenido
        contenido_lower = contenido.lower()
        for token in tokens:
            if token in contenido_lower:
                conceptos_familiares.append(nodo)
                break

    return list(set(conceptos_familiares))

def procesar_comandos_ocultos(texto_agente, cerebro):
    """
    Parsea las instrucciones dentro del bloque <pensamiento> del agente.
    Ejecuta en SQLite de forma instantánea las operaciones solicitadas:
    - [BUSCAR: clave] -> Evoca del disco e incrementa peso sináptico.
    - [GUARDAR: clave = valor] -> Guarda temporalmente en corto plazo.
    - [ASOCIAR: a = b] -> Establece sinapsis bidireccional en el grafo.
    
    Devuelve un diccionario con los resultados de las operaciones realizadas.
    """
    resultados = {
        "recordar": [],
        "aprender": [],
        "vincular": []
    }

    # Extraer bloques de pensamiento del agente
    bloques_pensamiento = re.findall(r'<pensamiento>(.*?)</pensamiento>', texto_agente, re.DOTALL)
    
    for bloque in bloques_pensamiento:
        # 1. Procesar búsquedas: [BUSCAR: concepto]
        busquedas = re.findall(r'\[BUSCAR:\s*([^\]]+)\]', bloque)
        for consulta in busquedas:
            clave = consulta.strip()
            contenido = cerebro.buscar_recuerdo_microsegundos(clave)
            resultados["recordar"].append({
                "clave": clave,
                "resultado": contenido
            })

        # 2. Procesar guardados: [GUARDAR: clave = valor]
        guardados = re.findall(r'\[GUARDAR:\s*([^=]+)=\s*([^\]]+)\]', bloque)
        for clave, valor in guardados:
            key = clave.strip()
            val = valor.strip()
            cerebro.percibir_corto_plazo(key, val)
            resultados["aprender"].append({
                "clave": key,
                "valor": val
            })

        # 3. Procesar asociaciones: [ASOCIAR: a = b]
        asociaciones = re.findall(r'\[ASOCIAR:\s*([^=]+)=\s*([^\]]+)\]', bloque)
        for a, b in asociaciones:
            nodo_a = a.strip()
            nodo_b = b.strip()
            cerebro.establecer_asociacion(nodo_a, nodo_b)
            resultados["vincular"].append({
                "concepto_a": nodo_a,
                "concepto_b": nodo_b
            })

    return resultados

def inyectar_contexto_familiaridad(user_input, cerebro):
    """
    Prepara la inyección del prompt de familiaridad.
    Si el escaneo detecta similitud, devuelve las notas formateadas para el agente.
    """
    conceptos = escanear_familiaridad(user_input, cerebro)
    if not conceptos:
        return user_input

    notas = []
    for c in conceptos:
        notas.append(f'[Nota de Familiaridad: Te resulta familiar el concepto "{c}"]')
    
    prefijo = "\n".join(notas)
    return f"{prefijo}\n\n{user_input}"
