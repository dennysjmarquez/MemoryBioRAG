"""User-facing CLI explanations. Text only: no engine imports or side effects."""
from textwrap import fill

NOTES = {
    'buscar': 'Retrieve a permanent memory before saving a duplicate. Newly saved working '
              'memories become searchable after biorag sueno. Results are not proof that a fact is current.',
    'listar': 'Browse permanent concepts page by page when you do not yet know what to search for.',
    'corteza': 'Inspect permanent memory nodes, including their state. This can print a large list.',
    'estado': 'Check memory counts and activity without listing every memory. This is a summary, not an integrity test.',
    'familiaridad': 'Find concepts from permanent memory mentioned in a text, to decide what to search next. This does not verify the text.',
    'sustantivos': 'Inspect the topic keywords assigned to an existing permanent or working-memory node when diagnosing retrieval.',
    'guardar': 'Save information in working memory. Search first to avoid duplicates; then run biorag sueno '
               'to consolidate it so buscar can retrieve it.',
    'agregar_sustantivos': 'Assign or update topic keywords on an existing permanent or working memory to improve retrieval. '
                           'This does not establish which version of a fact is current.',
    'asociar': 'Connect related concepts for associative retrieval. An association does not mean one fact replaces another.',
    'sueno': 'Consolidate working memories into permanent memory and run maintenance adjustments. This changes stored data; it is not a preview.',
    'comunicar': 'Leave a message in the shared memory database. The recipient must read it; there is no immediate external notification. '
                 'AGENT_NAME identifies the sender. Current routing restricts recipient IDs: unknown IDs are broadcast to todos, '
                 'not delivered privately. Use todos for an explicit broadcast.',
    'leer_mensajes': 'Read shared messages and mark displayed unread messages as read for the current AGENT_NAME. '
                     'This changes read status. Unsupported destination filters are ignored by the current engine.',
    'dashboard': 'Start the local inspection interfaces, if included. This can install Python and Node dependencies, '
                 'start servers on ports 8001 and 3000, and open a browser. It is not required for CLI or MCP use.',
    'update': 'Update the program and prepare its components in one command. Without --yes this only plans and may access the network. '
              'Stop the MCP server (the process connecting your agent to memory tools) and background maintenance daemon before applying. '
              'A clean Git checkout has no local changes; an external database is stored outside that checkout.',
    'recovery': 'After an update failure, inspect the backup referenced by its update receipt. With --stage, '
                'preserve a snapshot of the present and restore the old backup to a separate file. '
                'This never overwrites live memory or activates an older program version.',
    'correcciones': 'Keep an earlier fact and record which fact replaces it for a specific context and effective date. '
                    'This is not a command for editing memory text.',
    'correcciones registrar': 'Propose that one fact replaces another, providing context, values, existing nodes and dates. '
                              'This creates a pending proposal, not an approved correction.',
    'correcciones revisar': 'Before approving, inspect the original message, context, values, dates and referenced memories. '
                            'Obtain the digest identifying that evidence. Reviewing does not approve it.',
    'correcciones confirmar': 'After reviewing and deciding the replacement is correct, approve it with the reviewed digest '
                              'and a request ID for duplicate-free retries. History is preserved; the command does not establish that the evidence is true.',
}

# Commands whose handlers write memory or state; initialization may also prepare schema.
WRITES = {'buscar', 'guardar', 'agregar_sustantivos', 'asociar', 'sueno', 'comunicar', 'leer_mensajes'}
REQUIRES_NODES = {'asociar', 'agregar_sustantivos', 'sustantivos', 'correcciones'}


def usage_note(command):
    note = fill('Why use it? ' + NOTES[command], width=88)
    if command == 'correcciones':
        sections = (
            ('How is this different from updating a node?',
             'Updating a node changes its text. A contextual correction keeps two memories '
             'and records that one fact replaces another in a context from a given date. '
             'It does not delete or rewrite either memory.'),
            ('Concrete example:',
             'One memory says the service uses port 8080; another says it now uses 8443. '
             'Approve the relationship: for this service and environment, from the specified '
             'date, 8443 replaces 8080. The earlier memory remains available as history.'),
            ('Before you start:',
             'Both memories must already exist. Register proposes, review checks the evidence, '
             'and confirm approves the relationship, not the truth of the fact.'),
            ('Where does it apply?',
             'It supplies evidence to MCP recordar/buscar with the matching context and mode '
             'vigente, historico or ambos. It does not change every search or guarantee '
             'that the newer fact always ranks first. These modes are not CLI buscar options.'),
        )
        note += ''.join('\n\n' + title + '\n' + fill(text, width=88) for title, text in sections)
    if command == 'buscar':
        note += '\n\n' + fill('Side effects: --deep wakes retrieved dormant nodes and changes their weight. '
                               'Search may also write search logs and learning state; it is not a read-only audit.', width=88)
    if command in REQUIRES_NODES:
        note += '\n\nBefore you start: referenced nodes must already exist.'
    if command in WRITES:
        note += '\n\n' + fill('Changes memory or state. To test on a disposable copy, use: '
                               'BIORAG_PATH=/path/copy.db biorag ' + command + ' ...', width=88)
    if command.startswith('correcciones'):
        note += '\n\nDatabase: --db overrides BIORAG_PATH. Use an existing disposable copy.'
    return note


EXAMPLES = {
    'buscar': ('biorag buscar "service configuration" --sustantivos-clave "service,config"',
               'biorag buscar service --completo --asociados'),
    'listar': ('biorag listar', 'biorag listar --pagina 2'),
    'corteza': ('biorag corteza',),
    'estado': ('biorag estado',),
    'familiaridad': ('biorag familiaridad "Check the service configuration"',),
    'sustantivos': ('biorag sustantivos servicio_puerto_actual',),
    'guardar': ('biorag guardar service_note "The test service uses port 8443" --sustantivos-clave "service,port"',
                'biorag sueno'),
    'agregar_sustantivos': ('biorag agregar_sustantivos servicio_puerto_actual "service,port"',),
    'asociar': ('biorag asociar service_configuration service_deployment',),
    'sueno': ('biorag sueno',),
    'comunicar': ('AGENT_NAME=agent_a biorag comunicar todos "Please review the test service"',),
    'leer_mensajes': ('AGENT_NAME=agent_b biorag leer_mensajes --no-leidos',
                      'biorag leer_mensajes --ultimos 5'),
    'dashboard': ('biorag dashboard --help',),
    'update': ('biorag update --dry-run', 'biorag update --yes --db /path/copy.db'),
    'recovery': ('biorag recovery --receipt /path/update-receipts/receipt.json',
                 'biorag recovery --receipt /path/update-receipts/receipt.json --stage'),
    'correcciones': ('biorag correcciones registrar --help',
                     'biorag correcciones revisar --db /ruta/copia_prueba.db --id cambio-puerto-001',
                     'biorag correcciones confirmar --help'),
    'correcciones registrar': (
        'biorag correcciones registrar --db /ruta/copia_prueba.db \\\n    --id cambio-puerto-001 --mensaje "The service port changed from 8080 to 8443" \\\n    --nodo-anterior servicio_puerto_anterior --nodo-sucesor servicio_puerto_actual \\\n    --entidad service --atributo port --ambito test \\\n    --valor-anterior 8080 --valor-nuevo 8443 \\\n    --observado-en 1767225600 --efectivo-desde 1767225600 --anterior-desde 1735689600',),
    'correcciones revisar': ('biorag correcciones revisar --db /ruta/copia_prueba.db --id cambio-puerto-001',),
    'correcciones confirmar': (
        'biorag correcciones confirmar --db /ruta/copia_prueba.db \\\n    --id cambio-puerto-001 --digest DIGEST_DE_LA_REVISION --request-id aprobacion-001',),
}


def command_examples(command):
    header = 'Examples:\n'
    if command.startswith('correcciones'):
        header += ('  Use an existing test copy; replace the illustrative paths and node IDs.\n'
                   '  UNIX dates are illustrative; never invent actual effective dates.\n'
                   '  Replace DIGEST_DE_LA_REVISION with the digest returned by revisar.\n')
    if command == 'dashboard':
        header += '  Help is safe; running dashboard without --help can install dependencies and start services.\n'
    return header + '\n'.join('  ' + example for example in EXAMPLES[command])
