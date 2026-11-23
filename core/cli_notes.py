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
    'update': 'Apply a safe program update in one command. The updater checks the selected database, stops only its own verified background daemon, makes and tests a database backup, updates code and dependencies, then verifies the database. If a step fails, it attempts to restore the previous code, dependencies and database. Dependency verification compares package names and versions; it is not a byte-for-byte environment snapshot. A failed rollback keeps the safety barrier active and preserves the backup and receipt. '
              'Use --dry-run for an optional preview. The checkout must be clean and the database must be outside it.',
    'recovery': 'If automatic rollback cannot be verified, do not restart BioRAG; keep the backup and receipt and contact support. Recovery staging can make separate copies, but does not overwrite live memory.',
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
REQUIRES_NODES = {'asociar', 'agregar_sustantivos', 'sustantivos', 'correcciones',
                  'correcciones registrar', 'correcciones revisar', 'correcciones confirmar'}


def usage_note(command):
    note = 'What is it for?\n' + fill(NOTES[command], width=88)
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
        note += '\n\nDates are Unix seconds. BIORAG_CORRECTIONS=0 disables operations. Message language is not interpreted.'
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
    'update': ('biorag update --dry-run', 'biorag update --db /path/copy.db'),
    'recovery': ('biorag recovery --receipt /path/update-receipts/receipt.json',
                 'biorag recovery --receipt /path/update-receipts/receipt.json --stage'),
    'correcciones': ('biorag correcciones registrar --help',
                     'biorag correcciones revisar --db /path/test-copy.db --id cambio-puerto-001',
                     'biorag correcciones confirmar --help'),
    'correcciones registrar': (
        'biorag correcciones registrar --db /path/test-copy.db \\\n    --id cambio-puerto-001 --mensaje "The service port changed from 8080 to 8443" \\\n    --nodo-anterior servicio_puerto_anterior --nodo-sucesor servicio_puerto_actual \\\n    --entidad service --atributo port --ambito test \\\n    --valor-anterior 8080 --valor-nuevo 8443 \\\n    --observado-en 1767225600 --efectivo-desde 1767225600 --anterior-desde 1735689600',),
    'correcciones revisar': ('biorag correcciones revisar --db /path/test-copy.db --id cambio-puerto-001',),
    'correcciones confirmar': (
        'biorag correcciones confirmar --db /path/test-copy.db \\\n    --id cambio-puerto-001 --digest REVIEW_DIGEST --request-id aprobacion-001',),
}


def command_examples(command):
    header = 'Examples:\n'
    if command.startswith('correcciones'):
        header += ('  Use an existing test copy; replace the illustrative paths and node IDs.\n'
                   '  UNIX dates are illustrative; never invent actual effective dates.\n'
                   '  Replace REVIEW_DIGEST with the digest returned by revisar.\n')
    return header + '\n'.join('  ' + example for example in EXAMPLES[command])


GLOSSARY = {
    'corteza': '`corteza` (cortex: permanent memory)',
    'sueno': '`sueno` (sleep: consolidation)',
    'sustantivos': '`sustantivos clave` (key nouns: the core topic of a memory)',
}
EXPECTED = {
    'buscar': 'Matching concepts with content previews and scores; no match exits with code 1. Scores and ordering depend on stored data.',
    'listar': 'A page of permanent concept names and content previews.',
    'corteza': 'Permanent node names, weights and states.',
    'estado': 'Active and dormant counts, working-memory count, energy and keyword coverage.',
    'familiaridad': 'Recognized concepts or a no-match notice.',
    'sustantivos': 'The selected concept and its assigned keyword list.',
    'guardar': 'A working-memory save confirmation, keyword list and consolidation reminder.',
    'agregar_sustantivos': 'The updated keyword list for the selected concept.',
    'asociar': 'An association confirmation for the two concepts.',
    'sueno': 'Consolidation and maintenance progress; details vary with stored data.',
    'comunicar': 'A message registration confirmation including sender and destination.',
    'leer_mensajes': 'Message IDs, read status, timestamps, sender, destination and message text.',
    'dashboard': 'Without --help: service startup diagnostics; dependency installation may occur. Startup was not executed in this audit (not verified).',
    'update': 'JSON plan or update receipt; messages are in English. Code availability and database readiness are separate; a dry run checks the database read-only and never changes source files or database contents.',
    'recovery': 'JSON recovery plan; --stage reports separate snapshots and live_database_unchanged. No live recovery was executed.',
    'correcciones': 'With no subcommand: this help. Operations return JSON; errors go to stderr.',
    'correcciones registrar': 'JSON pending proposal; registration is not confirmation.',
    'correcciones revisar': 'JSON evidence with a review digest; use the returned digest for confirmation.',
    'correcciones confirmar': 'JSON confirmation result; the original memories remain intact.',
}
SEE_ALSO = {
    'buscar': ('guardar', 'sueno', 'listar'),
    'guardar': ('buscar', 'sueno', 'listar'),
    'sueno': ('guardar', 'buscar', 'estado'),
    'listar': ('buscar', 'guardar', 'sueno'),
    'comunicar': ('leer_mensajes',), 'leer_mensajes': ('comunicar',),
    'update': ('recovery',), 'recovery': ('update',),
}


def help_intro(command, summary):
    note = usage_note(command)
    # Prerequisites and safety belong before Options, not after Examples.
    head, separator, rest = note.partition('\n\n')
    result = 'Summary:\n' + summary.strip() + '\n\n' + head
    terms = ['corteza', 'sueno', 'sustantivos'] if command in (
        'buscar', 'guardar', 'listar', 'sueno', 'corteza') else []
    if command in ('sustantivos', 'agregar_sustantivos'):
        terms = ['sustantivos']
    if terms:
        result += '\n\n' + '\n'.join('  - ' + GLOSSARY[t] for t in terms)
    if separator:
        result += '\n\nBefore you start:\n' + rest.replace('Before you start:', '').strip()
    if command == 'recovery':
        result += ('\n\nBefore you start:\nThe receipt selects the source database. BIORAG_PATH does not override it. '
                   'Keep the receipt and backup; verify code and data compatibility before using a staged copy.')
    return result


def help_end(command):
    links = SEE_ALSO.get(command, ('correcciones',) if command.startswith('correcciones ') else ('buscar', 'estado'))
    language_note = ('Updater messages are in English; machine-readable JSON keys and status codes are unchanged.'
                     if command == 'update' else
                     'Runtime messages retain their existing language (often Spanish); JSON keys are unchanged.')
    return (command_examples(command) + '\n\nExpected output:\n' + fill(EXPECTED[command], 88)
            + '\n' + language_note
            + '\n\nSee also:\n' + '\n'.join('  biorag ' + name + ' --help' for name in links))
