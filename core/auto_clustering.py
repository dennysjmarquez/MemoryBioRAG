import re
import time
import random
import os
from collections import Counter

# Lista extendida de stopwords en español e inglés
STOPWORDS = {
    # Español
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a", "y", "o", "u", "e", "en", "para", 
    "por", "con", "sin", "sobre", "tras", "desde", "hasta", "hacia", "como", "que", "es", "son", "este", "esta", 
    "estos", "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas", "mi", "mis", "tu", 
    "tus", "su", "sus", "nuestro", "nuestra", "nuestros", "nuestras", "yo", "me", "te", "se", "nos", "lo", "le", 
    "les", "otro", "otra", "otros", "otras", "muy", "mas", "pero", "si", "no", "ni", "ya", "aun", "tambien", 
    "tampoco", "cuando", "donde", "quien", "quién", "cual", "cuál", "cuyo", "cuya", "cuyos", "cuyas", "todo", 
    "toda", "todos", "todas", "algun", "alguna", "algunos", "algunas", "ningun", "ninguna", "ninguno", "mismo", 
    "misma", "mismos", "mismas", "tan", "entonces", "luego", "despues", "antes", "ahora", "hoy", "ayer", "mañana",
    "este", "esta", "esto", "estos", "estas", "tiene", "tienen", "tenemos", "hacer", "hecho", "puede", "pueden",
    # Inglés
    "the", "a", "an", "and", "or", "but", "if", "because", "as", "until", "while", "of", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "to", "from",
    "up", "down", "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", "there",
    "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", "don",
    "should", "now", "this", "that", "these", "those", "is", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "having", "do", "does", "did", "doing", "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves", "what", "which", "who", "whom", "am",
    "are", "is", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will",
    # Términos comunes de BioRAG a ignorar en nombres de clusters
    "nodo", "prueba", "test", "recuerdo", "concepto", "contenido", "sistema", "memoria"
}

def tokenizar_texto(texto):
    """Extrae palabras limpias en minúsculas."""
    if not texto:
        return []
    texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower())
    palabras = texto_limpio.split()
    return [p for p in palabras if len(p) >= 3 and p not in STOPWORDS]

def detectar_comunidades(cerebro, min_densidad=0.3, min_nodos=5):
    """Algoritmo de Label Propagation (LPA) para detectar comunidades en el grafo de sinapsis.
    
    1. Cargar nodos activos y sus sinapsis.
    2. Ejecutar LPA.
    3. Para cada comunidad densa, generar nombre usando palabras clave y calcular confianza.
    Retorna una lista de dicts: [{'nodos': [conceptos], 'nombre': str, 'confianza': float}]
    """
    # Cargar nodos activos
    cerebro.cursor.execute("SELECT concepto, contenido, sinonimos FROM largo_plazo WHERE estado = 'activo'")
    nodos_rows = cerebro.cursor.fetchall()
    if not nodos_rows:
        return []
        
    nodos = [row[0] for row in nodos_rows]
    nodos_set = set(nodos)
    nodo_contenido = {row[0]: (row[1] or "") + " " + (row[2] or "") for row in nodos_rows}
    
    # Cargar sinapsis activas
    cerebro.cursor.execute("SELECT origen, destino, peso FROM sinapsis WHERE peso >= 0.1")
    sinapsis_rows = cerebro.cursor.fetchall()
    
    # Construir grafo de adyacencia (bidireccional)
    adj = {n: {} for n in nodos}
    for orig, dest, peso in sinapsis_rows:
        if orig in nodos_set and dest in nodos_set:
            adj[orig][dest] = max(adj[orig].get(dest, 0.0), peso)
            adj[dest][orig] = max(adj[dest].get(orig, 0.0), peso)
            
    # Inicializar etiquetas: cada nodo tiene su propia etiqueta
    labels = {n: n for n in nodos}
    
    # Label Propagation Algorithm
    random.seed(42)  # Determinismo
    max_iter = 50
    for _ in range(max_iter):
        cambios = 0
        orden_nodos = list(nodos)
        random.shuffle(orden_nodos)
        
        for u in orden_nodos:
            vecinos = adj[u]
            if not vecinos:
                continue
                
            # Sumar pesos de etiquetas de los vecinos
            label_weights = {}
            for v, peso in vecinos.items():
                lbl = labels[v]
                label_weights[lbl] = label_weights.get(lbl, 0.0) + peso
                
            if not label_weights:
                continue
                
            # Seleccionar etiqueta con máximo peso acumulado
            max_lbl = max(label_weights.items(), key=lambda x: x[1])[0]
            if labels[u] != max_lbl:
                labels[u] = max_lbl
                cambios += 1
                
        if cambios == 0:
            break
            
    # Agrupar nodos por etiqueta
    comunidades_raw = {}
    for nodo, lbl in labels.items():
        comunidades_raw.setdefault(lbl, []).append(nodo)
        
    comunidades_detectadas = []
    
    # Procesar comunidades
    for lbl, miembros in comunidades_raw.items():
        if len(miembros) < min_nodos:
            continue
            
        # Calcular densidad de sinapsis internas
        k = len(miembros)
        max_posibles_sinapsis = (k * (k - 1)) / 2 if k > 1 else 1
        sinapsis_internas_peso = 0.0
        conteo_sinapsis = 0
        
        miembros_set = set(miembros)
        for i in range(k):
            for j in range(i + 1, k):
                n1, n2 = miembros[i], miembros[j]
                if n2 in adj[n1]:
                    sinapsis_internas_peso += adj[n1][n2]
                    conteo_sinapsis += 1
                    
        densidad = sinapsis_internas_peso / max_posibles_sinapsis if k > 1 else 1.0
        
        # Filtrar comunidades poco densas
        if densidad < min_densidad:
            continue
            
        # Extraer tokens frecuentes de los contenidos del cluster
        cluster_texto = " ".join([nodo_contenido.get(m, "") for m in miembros])
        tokens = tokenizar_texto(cluster_texto)
        frecuencias = Counter(tokens)
        top_tokens = [w for w, count in frecuencias.most_common(3)]
        
        if not top_tokens:
            # Fallback en caso de que no haya palabras útiles
            nombre_cluster = f"auto_cluster_{abs(hash(frozenset(miembros))) % 100000}"
        else:
            nombre_cluster = "auto_" + "_".join(top_tokens)
            
        comunidades_detectadas.append({
            "nodos": miembros,
            "nombre": nombre_cluster,
            "confianza": float(round(densidad, 4))
        })
        
    return comunidades_detectadas

def asignar_dimensiones_emergentes(cerebro, comunidades):
    """Inserta las dimensiones auto-generadas e indexa los nodos correspondientes en largo_plazo_dimensiones."""
    ahora = time.time()
    
    # 0. Migración de Limpieza Única (One-time cleanup)
    cerebro.cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = 'migration_autoclustering_v1'")
    if not cerebro.cursor.fetchone():
        # Purgar todas las dimensiones auto-generadas legacy y sus asociaciones
        cerebro.cursor.execute("""
            DELETE FROM largo_plazo_dimensiones 
            WHERE dimension_id IN (SELECT id FROM dimensiones_semanticas WHERE auto_generada = 1)
        """)
        cerebro.cursor.execute("DELETE FROM dimensiones_semanticas WHERE auto_generada = 1")
        # Registrar la migración (tipo_id = 7: dominio, auto_generada = 0 para que no sea purgada)
        cerebro.cursor.execute("""
            INSERT INTO dimensiones_semanticas (name, description, tipo_id, auto_generada, confianza, generado_en)
            VALUES ('migration_autoclustering_v1', 'Marcador de migración de limpieza de auto-clustering.', 7, 0, 1.0, ?)
        """, (ahora,))
        cerebro.conn.commit()

    umbral_solapamiento = float(os.environ.get("BIORAG_UMBRAL_SOLAPAMIENTO_CLUSTER", "0.5"))
    dim_ids_actuales = set()

    for comm in comunidades:
        nombre = comm["nombre"]
        conf = comm["confianza"]
        nodos = comm["nodos"]
        
        # Desambiguación de colisiones de nombres de dimensiones
        nombre_final = nombre
        sufijo = 1
        while sufijo < 50:
            cerebro.cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = ?", (nombre_final,))
            row_dim = cerebro.cursor.fetchone()
            if not row_dim:
                # El nombre no existe, se puede usar
                break
            dim_id = row_dim[0]
            # Obtener miembros actuales de esta dimensión en la DB
            cerebro.cursor.execute("SELECT concepto FROM largo_plazo_dimensiones WHERE dimension_id = ?", (dim_id,))
            miembros_existentes = {r[0] for r in cerebro.cursor.fetchall()}
            if not miembros_existentes:
                # Si la dimensión existe pero no tiene miembros vinculados, la reutilizamos
                break
            
            # Calcular Jaccard de solapamiento
            set_nuevos = set(nodos)
            union = set_nuevos | miembros_existentes
            overlap = len(set_nuevos & miembros_existentes) / len(union) if union else 0.0
            
            if overlap >= umbral_solapamiento:
                # Es la misma comunidad en evolución, reutilizamos el nombre
                break
            
            # Colisión: intentar con un nuevo sufijo
            sufijo += 1
            nombre_final = f"{nombre}_{sufijo}"
        
        nombre = nombre_final
        
        # 1. Asegurar la creación de la dimensión semántica auto-generada (tipo_id = 7: dominio)
        cerebro.cursor.execute("""
            INSERT OR IGNORE INTO dimensiones_semanticas (name, description, tipo_id, auto_generada, confianza, generado_en)
            VALUES (?, ?, 7, 1, ?, ?)
        """, (nombre, f"Dimensión temática auto-generada vía clustering semántico con confianza {conf:.2f}.", conf, ahora))
        
        # Si ya existe, actualizar confianza y fecha de generación
        cerebro.cursor.execute("""
            UPDATE dimensiones_semanticas
            SET confianza = ?, generado_en = ?
            WHERE name = ? AND auto_generada = 1
        """, (conf, ahora, nombre))
        
        # Obtener el ID de la dimensión
        cerebro.cursor.execute("SELECT id FROM dimensiones_semanticas WHERE name = ?", (nombre,))
        dim_id = cerebro.cursor.fetchone()[0]
        dim_ids_actuales.add(dim_id)
        
        # 2. Asociar los nodos del cluster a esta dimensión
        for nodo in nodos:
            cerebro.cursor.execute("""
                INSERT OR IGNORE INTO largo_plazo_dimensiones (concepto, dimension_id)
                VALUES (?, ?)
            """, (nodo, dim_id))
            
        # Limpiar miembros obsoletos que ya no están en esta comunidad
        nodos_placeholder = ",".join(["?"] * len(nodos))
        cerebro.cursor.execute(f"""
            DELETE FROM largo_plazo_dimensiones
            WHERE dimension_id = ? AND concepto NOT IN ({nodos_placeholder})
        """, [dim_id] + list(nodos))
            
    # 3. Limpieza global de dimensiones auto-generadas desaparecidas
    if dim_ids_actuales:
        placeholders = ",".join(["?"] * len(dim_ids_actuales))
        # Eliminar membresías de dimensiones auto-generadas desaparecidas
        cerebro.cursor.execute(f"""
            DELETE FROM largo_plazo_dimensiones
            WHERE dimension_id IN (
                SELECT id FROM dimensiones_semanticas 
                WHERE auto_generada = 1 AND id NOT IN ({placeholders})
            )
        """, list(dim_ids_actuales))
        # Eliminar las dimensiones auto-generadas desaparecidas en sí
        cerebro.cursor.execute(f"""
            DELETE FROM dimensiones_semanticas
            WHERE auto_generada = 1 AND id NOT IN ({placeholders})
        """, list(dim_ids_actuales))
    else:
        # Si no se detectó ninguna comunidad en este ciclo, eliminar todas las auto-generadas
        cerebro.cursor.execute("""
            DELETE FROM largo_plazo_dimensiones
            WHERE dimension_id IN (
                SELECT id FROM dimensiones_semanticas WHERE auto_generada = 1
            )
        """)
        cerebro.cursor.execute("DELETE FROM dimensiones_semanticas WHERE auto_generada = 1")

    cerebro.conn.commit()
