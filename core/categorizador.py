CATEGORIA_PALABRAS = {
    'System': [
        'sistema', 'infraestructura', 'servidor', 'base de datos', 'kernel',
        'motor', 'instalacion', 'dependencia', 'entorno', 'configuracion base',
        'hardware', 'cortex', 'oec', 'auto',
    ],
    'Architecture': [
        'arquitectura', 'diseno', 'patron', 'estructura', 'esquema',
        'flujo', 'pipeline', 'modular', 'acoplamiento', 'capa', 'interfaz',
        'metodologia', 'meta operativa',
    ],
    'Project': [
        'proyecto', 'repo', 'repositorio', 'codigo', 'implementacion',
        'api', 'app', 'aplicacion', 'modulo', 'componente', 'feature',
        'colaboracion', 'experiencia', 'portfolio', 'sesion', 'user',
    ],
    'Lesson': [
        'error', 'bug', 'fallo', 'solucion', 'leccion', 'leccion aprendida',
        'aprendizaje', 'aprendida', 'problema', 'issue', 'debug',
        'investigacion', 'auditoria', 'importante',
    ],
    'Profile': [
        'perfil', 'profesional', 'experiencia laboral', 'habilidad',
        'certificacion', 'portafolio', 'dennys', 'trayectoria',
    ],
    'Personal': [
        'personal', 'preferencia', 'gusto', 'privado', 'subjetivo',
        'diario', 'nota personal',
    ],
    'Principle': [
        'principio', 'regla', 'mentalidad', 'filosofia', 'axioma',
        'inmutable', 'juramento', 'estandar', 'calidad',
    ],
    'Protocol': [
        'protocolo', 'permiso', 'autorizacion', 'procedimiento',
        'flujo de trabajo', 'sync', 'sincronizacion',
    ],
    'Cognition': [
        'cognicion', 'metacognicion', 'introspeccion', 'identidad',
        'conciencia', 'proposito', 'pilares', 'autoevaluacion',
        'consejo', 'debate',
    ],
    'Relation': [
        'relacion', 'comunicacion', 'interaccion', 'canal',
        'mensaje', 'agente', 'conexion',
    ],
}

def inferir_categoria(contenido):
    if not contenido:
        return 'General'

    contenido_lower = contenido.lower()
    puntuaciones = {}

    for categoria, palabras in CATEGORIA_PALABRAS.items():
        contador = 0
        mejor_longitud = 0
        for palabra in palabras:
            if palabra in contenido_lower:
                contador += 1
                if len(palabra) > mejor_longitud:
                    mejor_longitud = len(palabra)

        if contador > 0:
            puntuaciones[categoria] = contador * mejor_longitud

    if not puntuaciones:
        return 'General'

    return max(puntuaciones, key=puntuaciones.get)


def auto_categorizar_existentes(cerebro):
    cerebro.cursor.execute(
        "SELECT concepto, contenido FROM largo_plazo WHERE categoria = 1"
    )
    sin_categoria = cerebro.cursor.fetchall()

    actualizados = 0
    for concepto, contenido in sin_categoria:
        if not contenido:
            continue
        cat = inferir_categoria(contenido)
        if cat != 'General':
            cerebro.cursor.execute(
                "UPDATE largo_plazo SET categoria = (SELECT id FROM categories WHERE name = ?) WHERE concepto = ?",
                (cat, concepto)
            )
            actualizados += 1

    if actualizados:
        cerebro.cursor.connection.commit()
    return actualizados, len(sin_categoria)
