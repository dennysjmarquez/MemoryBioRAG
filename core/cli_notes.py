"""Notas de uso del CLI; texto únicamente, sin imports del motor ni efectos."""

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
    'correcciones': 'Úsalo cuando un dato recordado cambió y necesitas distinguir el antecedente '
                    'del dato que lo sustituye sin perder historia. Por ejemplo, un puerto '
                    'pasó de 8080 a 8443. Registrar propone, revisar muestra evidencia y '
                    'confirmar aprueba la relación; no reescribe el contenido de los recuerdos '
                    'ni adivina cuál dato es correcto.',
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
    return '¿Para qué me sirve? ' + NOTES[command]
