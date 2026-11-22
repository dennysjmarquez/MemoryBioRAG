"""Notas de uso del CLI; texto únicamente, sin imports del motor ni efectos."""
from textwrap import fill

NOTES = {
    'buscar': 'Úsalo para recuperar un recuerdo sin recorrer toda la memoria. Por ejemplo, '
              'busca cómo resolviste un problema antes de guardar otra solución. Encontrar '
              'un resultado no demuestra que siga vigente; revisa su contenido.',
    'listar': 'Úsalo para explorar qué conceptos tienes guardados, página por página, '
              'cuando todavía no sabes qué término buscar.',
    'corteza': 'Úsalo para inspeccionar los nodos de memoria permanente y su estado. '
               'Te ayuda a revisar la organización de la memoria; puede producir mucha salida.',
    'estado': 'Úsalo para obtener un resumen de la memoria y su actividad, sin listar '
              'cada recuerdo. Sirve como primera comprobación, no como certificación de integridad.',
    'familiaridad': 'Úsalo para detectar qué conceptos de un texto ya conoce la memoria. '
                    'Te orienta sobre qué buscar después; no verifica que el texto sea verdadero.',
    'sustantivos': 'Úsalo para ver de qué tema trata un nodo según sus sustantivos clave. '
                   'Ayuda a diagnosticar por qué se encuentra, o no, en una búsqueda.',
    'guardar': 'Úsalo para incorporar información nueva que quieras recuperar después. '
               'Busca primero para evitar duplicados. Se guarda en memoria de trabajo; '
               'sueno permite consolidarla en memoria permanente.',
    'agregar_sustantivos': 'Úsalo cuando un recuerdo existente necesita un núcleo temático '
                           'mejor definido para encontrarlo. Asigna o actualiza sus sustantivos '
                           'clave; no es el comando para corregir la vigencia de un hecho.',
    'asociar': 'Úsalo para conectar dos conceptos relacionados y facilitar su recuperación '
               'asociativa. Una asociación no declara que un dato sustituya a otro.',
    'sueno': 'Úsalo para consolidar lo aprendido en memoria permanente y ejecutar ajustes '
             'de mantenimiento. Modifica la memoria; no es una vista previa ni solo una consulta.',
    'comunicar': 'Úsalo para dejar un mensaje a otro agente mediante la memoria compartida. '
                 'El destinatario debe consultarlo; no equivale a una notificación externa inmediata.',
    'leer_mensajes': 'Úsalo para consultar los mensajes que otros agentes dejaron en la memoria '
                     'compartida y retomar coordinación pendiente.',
    'dashboard': 'Úsalo para abrir las interfaces locales de inspección de memoria, si tu '
                 'instalación las incluye. Arranca procesos; no es necesario para usar el CLI o MCP.',
    'update': 'Úsalo para poner al día el programa y preparar sus componentes sin ejecutar '
              'git, pip y migraciones por separado. Sin --yes solo planifica; puede consultar '
              'la red. Antes de aplicar, detén MCP/daemon y usa una DB externa al checkout.',
    'recovery': 'Úsalo después de una actualización fallida para evaluar el respaldo indicado '
                'en su recibo. Con --stage conserva una copia del presente y restaura el '
                'respaldo en otro archivo: no sobrescribe tu memoria ni activa una versión anterior.',
    'correcciones': 'Úsalo cuando necesitas conservar un dato anterior y dejar establecido '
                    'qué dato lo sustituye, para distinguirlos en consultas de vigencia. '
                    'No sirve para editar el texto de un recuerdo.',
    'correcciones registrar': 'Úsalo para proponer que un dato sustituye a otro, indicando '
                              'contexto, valores, nodos y fechas. Los dos recuerdos deben existir. '
                              'El resultado queda pendiente: todavía no es una corrección aprobada.',
    'correcciones revisar': 'Úsalo antes de aprobar para comprobar el mensaje, contexto, '
                            'valores, fechas y recuerdos implicados. Obtienes el digest '
                            'de esa evidencia; revisarla no la aprueba.',
    'correcciones confirmar': 'Úsalo solo después de revisar y decidir que la sustitución '
                              'es correcta. Registra la aprobación usando el digest revisado '
                              'y un request-id para reintentos sin duplicados. Conserva el '
                              'historial; no verifica por sí solo la verdad de la evidencia.',
}


def usage_note(command):
    note = fill('¿Para qué me sirve? ' + NOTES[command], width=88)
    if command == 'correcciones':
        sections = (
            ('Diferencia con actualizar un nodo:',
             'Actualizar cambia el contenido de ese recuerdo. Una corrección contextual '
             'conserva dos recuerdos y registra que un dato sustituye a otro para un '
             'contexto y desde una fecha; no borra ni reescribe sus textos.'),
            ('Ejemplo concreto:',
             'Un recuerdo dice «el servicio usa el puerto 8080» y otro dice «ahora usa '
             'el 8443». Aquí puedes dejar aprobada la relación: para ese servicio y '
             'entorno, desde la fecha indicada, el 8443 sustituye al 8080. El recuerdo '
             'del 8080 se conserva como antecedente.'),
            ('Antes de empezar:',
             'Ambos recuerdos deben existir. Registrar crea una propuesta; revisar '
             'permite comprobarla; confirmar aprueba la relación, no la verdad del dato.'),
            ('Dónde tiene efecto:',
             'Sirve como evidencia en las búsquedas MCP recordar/buscar con el contexto '
             'correspondiente y mode vigente, historico o ambos. No modifica todas las '
             'búsquedas ni garantiza que el dato nuevo siempre aparezca primero.'),
        )
        note += ''.join('\n\n' + title + '\n' + fill(text, width=88)
                        for title, text in sections)
    return note


# Ejemplos orientativos, no se ejecutan al imprimir ayuda.
EXAMPLES = {
    'buscar': ('biorag buscar "configuración del servicio" --sustantivos-clave "servicio,configuracion"',
               'biorag buscar servicio --completo --asociados'),
    'listar': ('biorag listar', 'biorag listar --pagina 2'),
    'corteza': ('biorag corteza',),
    'estado': ('biorag estado',),
    'familiaridad': ('biorag familiaridad "Necesito revisar la configuración del servicio"',),
    'sustantivos': ('biorag sustantivos servicio_puerto_actual',),
    'guardar': ('biorag guardar nota_servicio "El servicio de prueba utiliza el puerto 8443" --sustantivos-clave "servicio,puerto"',),
    'agregar_sustantivos': ('biorag agregar_sustantivos servicio_puerto_actual "servicio,puerto"',),
    'asociar': ('biorag asociar servicio_configuracion servicio_despliegue',),
    'sueno': ('biorag sueno',),
    'comunicar': ('biorag comunicar hermes "Revisa la configuración del servicio de prueba"',),
    'leer_mensajes': ('biorag leer_mensajes --no-leidos', 'biorag leer_mensajes --ultimos 5'),
    'dashboard': ('biorag dashboard',),
    'update': ('biorag update --dry-run', 'biorag update --yes --db /ruta/copia_prueba.db'),
    'recovery': ('biorag recovery --receipt /ruta/update-receipts/recibo.json',
                 'biorag recovery --receipt /ruta/update-receipts/recibo.json --stage'),
    'correcciones': ('biorag correcciones registrar --help',
                     'biorag correcciones revisar --db /ruta/copia_prueba.db --id cambio-puerto-001',
                     'biorag correcciones confirmar --help'),
    'correcciones registrar': (
        'biorag correcciones registrar --db /ruta/copia_prueba.db \\\n    --id cambio-puerto-001 --mensaje "El puerto cambió de 8080 a 8443" \\\n    --nodo-anterior servicio_puerto_anterior --nodo-sucesor servicio_puerto_actual \\\n    --entidad servicio --atributo puerto --ambito pruebas \\\n    --valor-anterior 8080 --valor-nuevo 8443 \\\n    --observado-en 1767225600 --efectivo-desde 1767225600 --anterior-desde 1735689600',),
    'correcciones revisar': (
        'biorag correcciones revisar --db /ruta/copia_prueba.db --id cambio-puerto-001',),
    'correcciones confirmar': (
        'biorag correcciones confirmar --db /ruta/copia_prueba.db \\\n    --id cambio-puerto-001 --digest DIGEST_DE_LA_REVISION --request-id aprobacion-001',),
}


def command_examples(command):
    header = ('Ejemplos:\n'
              '  Puedes sustituir «biorag» por «python3 biorag.py».\n'
              '  Adapta conceptos y rutas a tus datos; los nodos referidos deben existir.\n')
    if command.startswith('correcciones'):
        header += ('  Usa una copia de prueba. Fechas UNIX ilustrativas: no inventes fechas reales.\n'
                   '  DIGEST_DE_LA_REVISION se reemplaza por el digest de revisar.\n')
    elif command in ('guardar', 'agregar_sustantivos', 'asociar', 'sueno', 'comunicar', 'leer_mensajes'):
        header += '  Estas operaciones pueden modificar memoria o estado; prueba primero en una copia.\n'
    return header + '\n'.join('  ' + example for example in EXAMPLES[command])
