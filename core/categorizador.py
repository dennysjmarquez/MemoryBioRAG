CATEGORIA_PALABRAS = {
    'proyecto': [
        'proyecto', 'repo', 'repositorio', 'codigo', 'implementacion',
        'desarrollo', 'api', 'app', 'aplicacion', 'libreria', 'biblioteca',
        'modulo', 'package', 'componente', 'feature', 'funcionalidad',
    ],
    'solucion': [
        'error', 'bug', 'fallo', 'solucion', 'fix', 'arreglo', 'resuelto',
        'problema', 'issue', 'workaround', 'parche', 'debug', 'depuracion',
    ],
    'leccion': [
        'leccion', 'aprendizaje', 'principio', 'regla', 'leccion aprendida',
        'moraleja', 'insight', 'reflexion', 'descubrimiento',
    ],
    'arquitectura': [
        'arquitectura', 'diseno', 'esquema', 'estructura', 'patron',
        'diagrama', 'flujo', 'pipeline', 'kernel', 'capa', 'modular',
        'acoplamiento', 'dependencia', 'interfaz',
    ],
    'metacognicion': [
        'metacognicion', 'introspeccion', 'mentalidad', 'principio raiz',
        'pilares', 'identidad', 'proposito', 'conciencia', 'aprendizaje',
    ],
    'protocolo': [
        'protocolo', 'permiso', 'autorizacion', 'autonomia', 'consentimiento',
        'directiva', 'regla obligatoria', 'mandatory', 'invariant',
    ],
}


def inferir_categoria(contenido):
    if not contenido:
        return 'general'

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
        return 'general'

    return max(puntuaciones, key=puntuaciones.get)


def auto_categorizar_existentes(cerebro):
    cerebro.cursor.execute(
        "SELECT concepto, contenido FROM largo_plazo WHERE categoria = 'general'"
    )
    sin_categoria = cerebro.cursor.fetchall()

    actualizados = 0
    for concepto, contenido in sin_categoria:
        if not contenido:
            continue
        cat = inferir_categoria(contenido)
        if cat != 'general':
            cerebro.cursor.execute(
                "UPDATE largo_plazo SET categoria = ? WHERE concepto = ?",
                (cat, concepto)
            )
            actualizados += 1

    if actualizados:
        cerebro.cursor.connection.commit()
    return actualizados, len(sin_categoria)
