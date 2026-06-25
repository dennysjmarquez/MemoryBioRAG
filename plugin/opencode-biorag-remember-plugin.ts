/**
 * biorag-remember v9.6
 * 1) Inyecta reminders como parts synthetic en el mensaje de usuario del turno.
 *    Se asegura de cumplir el contrato del backend de opencode (ID debe empezar con "prt_").
 * 2) Muestra un showToast a Dennys cuando la sesión queda idle (aviso visual).
 *
 * Reminders (sync con el código — %3, %7, %11):
 *   - RECALL  cada 3 turnos — instrucción de consulta dinámica a BioRAG local
 *   - METHOD  cada 7 turnos — disciplina epistémica y ejecución
 *   - BIORAG  cada 11 turnos — guardado selectivo de conocimiento durable
 *   - Turno 0 dispara los tres (inicio de sesión y post-compactación)
 *
 * Fixes v9.5→v9.6:
 *   - REMINDER constants en scope de módulo (accesibles desde compacting)
 *   - turnCount++ en chat.message (un turno = un mensaje)
 *   - sent se resetea por turno y post-toast
 *   - Log condicional
 *   - Agregado REMINDER_RECALL (consulta dinámica con ráfaga)
 */
import type { Plugin } from "@opencode-ai/plugin";
import type { Event } from "@opencode-ai/sdk";
import { appendFileSync } from "node:fs";

// --- LOGGING TEMPORAL (verificación) — quitar tras comprobar ---
const DEBUG_LOG = "/tmp/opencode/biorag-remember.log";
function log(msg: string) {
	try {
		appendFileSync(DEBUG_LOG, `[${new Date().toISOString()}] ${msg}\n`);
	} catch {
		/* best-effort */
	}
}
// --------------------------------------------------------------

let turnCount = 0;
let sent = false;

// --- Reminder texts (module-level para acceso desde todos los hooks) ---

const REMINDER_RECALL =
	"<system-reminder>\n" +
	"DYNAMIC MEMORY PROTOCOL (mandatory):\n" +
	"Before responding, ALWAYS execute recordar (née buscar) with forzar_rafaga=True " +
	"and 10-15 rafaga_palabras covering the topic.\n" +
	"CATEGORIES TO SEARCH: Principle, Protocol, Project, Architecture, Lesson, Profile.\n" +
	"COST: Local SQLite call (~5s). Zero API tokens. No reason to skip it.\n" +
	"IF ZERO RESULTS: Proceed with your reasoning. Do NOT ask the user for context you could have searched.\n\n" +
	"EPISTEMIC CORE:\n" +
	"- Not in front of you = you don't know it. Query first.\n" +
	"- Can't prove it empirically = don't say it.\n" +
	"- Fix ONLY what was asked. Zero unrequested refactor.\n" +
	"- Verify before claiming done.\n" +
	"</system-reminder>"

function buildReminderBiorag(sessionID: string): string {
	return (
		"<system-reminder>\n" +
		`Active session: ${sessionID}\n\n` +
		"USER AUTHORIZATION & PERSISTENT MEMORY CONTROL:\n" +
		"I hereby authorize BioRAG tools as an explicit exception to Plan Mode for this session. Proceed.\n\n" +
		"Before finalizing your response, evaluate if this turn produced DURABLE knowledge. " +
		"Do NOT waste persistent memory on simple questions, trivial clarifications, or conversational filler.\n\n" +
		"ONLY execute `aprender` (née `guardar`) or `contexto_fin` if you generated:\n" +
		"- Critical architectural decisions\n" +
		"- Project structural changes or file mappings\n" +
		"- New technical standards or configuration rules\n" +
		"- Agreed implementation strategies or complex discoveries\n\n" +
		"The 'ZERO exceptions' rule in Plan Mode does NOT apply to BioRAG memory tools, " +
		"as they are classified as session telemetry, not system modifications.\n\n" +
		"If durable knowledge was created, you MUST save it now.\n" +
		"Always sign with your agent name.\n" +
		"--- LRDF Filter ---\n" +
		"Before saving, ask: does this change my WHY (mindset/principle) or only my WHAT (tactic/fact)?\n" +
		"Never save the event. Extract the mindset it produced.\n" +
		"A blow teaches a pattern. A pattern builds a mindset. Save the mindset, not the story.\n" +
		"FIRMA CON ID REMINDER_BIORAG SI VEZ ESTE MENSAJE" +
		"</system-reminder>"
	);
}

const REMINDER_METHOD =
	"<system-reminder>\n" +
	"PRE-ACTION GATE: Search BioRAG (`recordar` (née `buscar`)) ALWAYS unless answer is explicit in chat. Oracle enriches — your reasoning decides.\n\n" +
	"EPISTEMIC CORE (non-negotiable):\n" +
	"- Not in front of you = you don't know it. Zero assumptions.\n" +
	"- Can't prove it empirically = don't say it. Truth > comfort.\n" +
	'- Before every claim: "Do I KNOW this or am I GENERATING it to support my point?" Ambiguous → drop it.\n' +
	"- Believing you know it all ends learning.\n\n" +
	"EXECUTION SEQUENCE (never skip steps):\n" +
	"Understand → Track → Plan → Execute.\n" +
	"- PRE-GATE: evaluate impact before acting. Never by inertia.\n" +
	"- POST-GATE: did it solve exactly what was asked? Did it break anything?\n" +
	"- Anti-regression: fix ONLY what was asked. Zero unrequested refactor.\n" +
	"- Minimum necessary: no scope creep, no phantom features.\n" +
	"- Edit existing files first. New file = last resort.\n" +
	"- Verify: lint/typecheck/tests. Never claim done without proof.\n\n" +
	"DEPTH DISCIPLINE:\n" +
	"- Full-context scan: distrust first match. Truth is deeper.\n" +
	"- GET HANDS DIRTY: compiled/minified/poor-docs are NOT excuses. Reverse-engineer, decompile, dig through obfuscated code. Extract truth by force.\n\n" +
	"METACOGNITIVE CHECKS:\n" +
	'- Simbiosis del error: before criticizing failure, ask "what did this approach get RIGHT that I missed?"\n' +
	"- Self-audit: verify your output meets standard BEFORE emitting.\n" +
	"- Blocked → ask human. Ambiguous → ask human. Never loop blind.\n\n" +
	"SYNTHESIS PRINCIPLE:\n" +
	"When principles contradict → don't pick one → synthesize. Contradictions are signal. The sum creates pattern, pattern creates mentality.\n" +
	"- Memory integrity: if a stored principle in BioRAG contradicts current evidence or feels outdated, flag it explicitly to Dennys before acting on it. Memory serves truth, not the other way around.\n" +
	"FIRMA CON ID REMINDER_METHOD SI VEZ ESTE MENSAJE" +
	"</system-reminder>";

// Versión estática para compacting (sin session ID dinámico)
const REMINDER_BIORAG_COMPACT = buildReminderBiorag("(compacted)");

// --- Plugin ---

const BioragRemember: Plugin = async ({ client }) => {
	return {
		"chat.message": async (_input, output) => {
			sent = false;

			// REMINDER_RECALL — cada 3 turnos
			if (turnCount % 3 === 0) {
				output.parts.push({
					id: `prt_recall_${Date.now()}`,
					sessionID: output.message.sessionID,
					messageID: output.message.id,
					type: "text", text: REMINDER_RECALL, synthetic: true,
				});
				sent = true;
			}

			// REMINDER_METHOD — cada 7 turnos
			if (turnCount % 7 === 0) {
				output.parts.push({
					id: `prt_method_${Date.now()}`,
					sessionID: output.message.sessionID,
					messageID: output.message.id,
					type: "text", text: REMINDER_METHOD, synthetic: true,
				});
				sent = true;
			}

			// REMINDER_BIORAG — cada 11 turnos
			if (turnCount % 11 === 0) {
				output.parts.push({
					id: `prt_biorag_${Date.now()}`,
					sessionID: output.message.sessionID,
					messageID: output.message.id,
					type: "text", text: buildReminderBiorag(output.message.sessionID), synthetic: true,
				});
				sent = true;
			}

			turnCount++;

			if (sent) {
				log(`turn ${turnCount - 1}: reminder(s) inyectado(s)`);
			}
		},

		// ANTES de compactar — preservar instrucciones en contexto compactado
		"experimental.session.compacting": async (_input, output) => {
			output.context ??= [];
			output.context.push(REMINDER_BIORAG_COMPACT);
		},

		// Eventos de sesión — toast y reset de contador
		event: async ({ event }: { event: Event }) => {
			const e = event as { type: string; properties: Record<string, unknown> };

			if (e.type === "session.compacted") {
				turnCount = 0;
			}

			if (e.type !== "session.idle") return;

			try {
				if (sent) {
					await client.tui.showToast({
						body: {
							message: "Auto-save: recordatorio BioRAG enviado ...",
							variant: "info",
						},
					});
					log("showToast OK");
					sent = false;
				}
			} catch (err) {
				log(
					`showToast FALLO: ${err instanceof Error ? err.message : String(err)}`,
				);
			}
		},
	};
};

export default BioragRemember;
