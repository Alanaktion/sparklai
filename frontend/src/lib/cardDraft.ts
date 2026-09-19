// Conversion between a stored character card and the editor's form state.
//
// The spec forbids destroying unknown key-value pairs, so every draft keeps the
// original JSON as `base` — the whole card, the character book, and each entry —
// and `cardFromDraft` overlays the edited fields onto it. Keys the editor does
// not understand therefore survive a load/edit/save cycle untouched.
//
// Optional fields are only written when they carry a value (non-empty string,
// `true` for a flag that defaults to false), so loading a card and saving it
// without changes does not add noise to it.

export type JsonObject = Record<string, unknown>;

export type ExtensionRow = { key: string; value: string };

export type DraftEntry = {
	/** Original entry JSON, kept so unknown keys survive. */
	base: JsonObject;
	keys: string;
	secondaryKeys: string;
	content: string;
	enabled: boolean;
	caseSensitive: boolean;
	selective: boolean;
	constant: boolean;
	insertionOrder: number;
	priority: string;
	position: '' | 'before_char' | 'after_char';
	name: string;
	comment: string;
	id: string;
	extensions: string;
};

export type DraftBook = {
	base: JsonObject;
	name: string;
	description: string;
	scanDepth: string;
	tokenBudget: string;
	recursiveScanning: boolean;
	extensions: string;
	entries: DraftEntry[];
};

export type Draft = {
	base: JsonObject;
	name: string;
	description: string;
	personality: string;
	scenario: string;
	firstMes: string;
	alternateGreetings: string[];
	mesExample: string;
	tags: string[];
	creator: string;
	characterVersion: string;
	creatorNotes: string;
	systemPrompt: string;
	postHistoryInstructions: string;
	book: DraftBook | null;
	extensions: ExtensionRow[];
};

export type JsonResult =
	| { ok: true; value: unknown }
	| { ok: false; error: string };

export type JsonObjectResult =
	| { ok: true; value: JsonObject }
	| { ok: false; error: string };

export function isObject(value: unknown): value is JsonObject {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Parse a JSON text produced by `JSON.stringify`, for the form fields. */
export function parseJsonText(text: string): JsonResult {
	const trimmed = text.trim();
	if (trimmed === '') return { ok: true, value: '' };
	try {
		return { ok: true, value: JSON.parse(trimmed) };
	} catch (cause) {
		return { ok: false, error: cause instanceof Error ? cause.message : 'Invalid JSON' };
	}
}

/** Parse text that must be a JSON object, for the raw JSON tab. */
export function readJsonObject(text: string): JsonObjectResult {
	const parsed = parseJsonText(text);
	if (!parsed.ok) return parsed;
	if (!isObject(parsed.value)) return { ok: false, error: 'The card must be a JSON object' };
	return { ok: true, value: parsed.value };
}

export function emptyDraft(): Draft {
	return {
		base: {},
		name: '',
		description: '',
		personality: '',
		scenario: '',
		firstMes: '',
		alternateGreetings: [],
		mesExample: '',
		tags: [],
		creator: '',
		characterVersion: '',
		creatorNotes: '',
		systemPrompt: '',
		postHistoryInstructions: '',
		book: null,
		extensions: []
	};
}

export function emptyEntry(): DraftEntry {
	return {
		base: {},
		keys: '',
		secondaryKeys: '',
		content: '',
		enabled: true,
		caseSensitive: false,
		selective: false,
		constant: false,
		insertionOrder: 0,
		priority: '',
		position: '',
		name: '',
		comment: '',
		id: '',
		extensions: '{}'
	};
}

export function emptyBook(): DraftBook {
	return {
		base: {},
		name: '',
		description: '',
		scanDepth: '',
		tokenBudget: '',
		recursiveScanning: false,
		extensions: '{}',
		entries: []
	};
}

export function draftFromCard(card: JsonObject): Draft {
	const data = objectAt(card, 'data');
	const bookJson = isObject(data.character_book) ? data.character_book : null;

	return {
		base: structuredClone(card),
		name: stringAt(data, 'name'),
		description: stringAt(data, 'description'),
		personality: stringAt(data, 'personality'),
		scenario: stringAt(data, 'scenario'),
		firstMes: stringAt(data, 'first_mes'),
		alternateGreetings: stringListAt(data, 'alternate_greetings'),
		mesExample: stringAt(data, 'mes_example'),
		tags: stringListAt(data, 'tags'),
		creator: stringAt(data, 'creator'),
		characterVersion: stringAt(data, 'character_version'),
		creatorNotes: stringAt(data, 'creator_notes'),
		systemPrompt: stringAt(data, 'system_prompt'),
		postHistoryInstructions: stringAt(data, 'post_history_instructions'),
		book: bookJson === null ? null : bookFromJson(bookJson),
		extensions: extensionRows(objectAt(data, 'extensions'))
	};
}

export function cardFromDraft(draft: Draft): JsonObject {
	const card = structuredClone(draft.base);
	card.spec = 'chara_card_v2';
	card.spec_version = '2.0';

	const data = objectAt(card, 'data');
	// The six shared fields must always be present as strings.
	data.name = draft.name;
	data.description = draft.description;
	data.personality = draft.personality;
	data.scenario = draft.scenario;
	data.first_mes = draft.firstMes;
	data.mes_example = draft.mesExample;
	data.creator_notes = draft.creatorNotes;
	data.system_prompt = draft.systemPrompt;
	data.post_history_instructions = draft.postHistoryInstructions;
	data.creator = draft.creator;
	data.character_version = draft.characterVersion;
	data.alternate_greetings = cleanList(draft.alternateGreetings);
	data.tags = cleanList(draft.tags);
	data.extensions = extensionsFromRows(draft.extensions);

	if (draft.book === null) {
		delete data.character_book;
	} else {
		data.character_book = bookFromDraft(draft.book);
	}

	card.data = data;
	return card;
}

/** Problems that would make the card invalid, shown before saving. */
export function draftProblems(draft: Draft): string[] {
	const problems: string[] = [];

	if (draft.name.trim() === '') problems.push('Name is required.');

	const duplicate = firstDuplicate(draft.extensions.map((row) => row.key.trim()));
	if (duplicate) problems.push(`Duplicate extension key "${duplicate}".`);

	for (const row of draft.extensions) {
		if (row.key.trim() === '') continue;
		problems.push(...jsonProblems(`Extension "${row.key.trim()}"`, row.value));
	}

	if (draft.book !== null) {
		const book = draft.book;
		problems.push(...numberProblems('Scan depth', book.scanDepth));
		problems.push(...numberProblems('Token budget', book.tokenBudget));
		problems.push(...jsonProblems('Character book extensions', book.extensions));

		book.entries.forEach((entry, index) => {
			const label = entry.name.trim() || `Entry ${index + 1}`;
			problems.push(...numberProblems(`${label}: insertion order`, String(entry.insertionOrder)));
			problems.push(...numberProblems(`${label}: priority`, entry.priority));
			problems.push(...numberProblems(`${label}: id`, entry.id));
			problems.push(...jsonProblems(`${label}: extensions`, entry.extensions));
		});
	}

	return problems;
}

function bookFromJson(bookJson: JsonObject): DraftBook {
	const entriesJson = Array.isArray(bookJson.entries) ? bookJson.entries : [];
	return {
		base: structuredClone(bookJson),
		name: stringAt(bookJson, 'name'),
		description: stringAt(bookJson, 'description'),
		scanDepth: numberTextAt(bookJson, 'scan_depth'),
		tokenBudget: numberTextAt(bookJson, 'token_budget'),
		recursiveScanning: booleanAt(bookJson, 'recursive_scanning'),
		extensions: JSON.stringify(objectAt(bookJson, 'extensions'), null, 2),
		entries: entriesJson.filter(isObject).map(entryFromJson)
	};
}

function entryFromJson(entry: JsonObject): DraftEntry {
	const position = entry.position;
	return {
		base: structuredClone(entry),
		keys: stringListAt(entry, 'keys').join(', '),
		secondaryKeys: stringListAt(entry, 'secondary_keys').join(', '),
		content: stringAt(entry, 'content'),
		enabled: booleanAt(entry, 'enabled', true),
		caseSensitive: booleanAt(entry, 'case_sensitive'),
		selective: booleanAt(entry, 'selective'),
		constant: booleanAt(entry, 'constant'),
		insertionOrder: typeof entry.insertion_order === 'number' ? entry.insertion_order : 0,
		priority: numberTextAt(entry, 'priority'),
		position: position === 'before_char' || position === 'after_char' ? position : '',
		name: stringAt(entry, 'name'),
		comment: stringAt(entry, 'comment'),
		id: numberTextAt(entry, 'id'),
		extensions: JSON.stringify(objectAt(entry, 'extensions'), null, 2)
	};
}

function bookFromDraft(book: DraftBook): JsonObject {
	const out = structuredClone(book.base);
	setOptional(out, 'name', book.name);
	setOptional(out, 'description', book.description);
	setNumberText(out, 'scan_depth', book.scanDepth);
	setNumberText(out, 'token_budget', book.tokenBudget);
	setFlag(out, 'recursive_scanning', book.recursiveScanning);
	out.extensions = jsonOrRaw(book.extensions, out.extensions);
	out.entries = book.entries.map(entryFromDraft);
	return out;
}

function entryFromDraft(entry: DraftEntry): JsonObject {
	const out = structuredClone(entry.base);
	out.keys = splitList(entry.keys);
	out.content = entry.content;
	out.extensions = jsonOrRaw(entry.extensions, out.extensions);
	out.enabled = entry.enabled;
	out.insertion_order = entry.insertionOrder;

	const secondary = splitList(entry.secondaryKeys);
	if (secondary.length > 0) out.secondary_keys = secondary;
	else delete out.secondary_keys;

	setFlag(out, 'case_sensitive', entry.caseSensitive);
	setFlag(out, 'selective', entry.selective);
	setFlag(out, 'constant', entry.constant);
	setOptional(out, 'position', entry.position);
	setOptional(out, 'name', entry.name);
	setOptional(out, 'comment', entry.comment);
	setNumberText(out, 'priority', entry.priority);
	setNumberText(out, 'id', entry.id);
	return out;
}

function setOptional(target: JsonObject, key: string, value: string): void {
	const trimmed = value.trim();
	if (trimmed === '') delete target[key];
	else target[key] = trimmed;
}

function setFlag(target: JsonObject, key: string, value: boolean): void {
	// Absent means false for these, so only write it when it is set.
	if (value) target[key] = true;
	else delete target[key];
}

function setNumberText(target: JsonObject, key: string, text: string): void {
	const trimmed = text.trim();
	if (trimmed === '') {
		delete target[key];
		return;
	}
	const value = Number(trimmed);
	// Leave unparseable input alone so the server reports it rather than the
	// editor silently discarding it.
	target[key] = Number.isFinite(value) ? value : trimmed;
}

function jsonOrRaw(text: string, fallback: unknown): unknown {
	const parsed = parseJsonText(text);
	if (!parsed.ok) return fallback;
	if (typeof parsed.value === 'string') return fallback;
	return parsed.value;
}

function extensionsFromRows(rows: ExtensionRow[]): JsonObject {
	const out: JsonObject = {};
	for (const row of rows) {
		const key = row.key.trim();
		if (key === '') continue;
		out[key] = jsonOrRaw(row.value, '');
	}
	return out;
}

function extensionRows(source: JsonObject): ExtensionRow[] {
	return Object.entries(source).map(([key, value]) => ({
		key,
		value: JSON.stringify(value, null, 2) ?? ''
	}));
}

function splitList(text: string): string[] {
	return text
		.split(',')
		.map((item) => item.trim())
		.filter((item) => item !== '');
}

function cleanList(items: string[]): string[] {
	return items.map((item) => item.trim()).filter((item) => item !== '');
}

function numberProblems(label: string, text: string): string[] {
	const trimmed = text.trim();
	if (trimmed === '') return [];
	return Number.isFinite(Number(trimmed)) ? [] : [`${label} must be a number.`];
}

function jsonProblems(label: string, text: string): string[] {
	const trimmed = text.trim();
	if (trimmed === '') return [];
	return parseJsonText(text).ok ? [] : [`${label} is not valid JSON.`];
}

function firstDuplicate(values: string[]): string | null {
	const seen = new Set<string>();
	for (const value of values) {
		if (value === '') continue;
		if (seen.has(value)) return value;
		seen.add(value);
	}
	return null;
}

function objectAt(source: JsonObject, key: string): JsonObject {
	const value = source[key];
	return isObject(value) ? { ...value } : {};
}

function stringAt(source: JsonObject, key: string): string {
	const value = source[key];
	return typeof value === 'string' ? value : '';
}

function numberTextAt(source: JsonObject, key: string): string {
	const value = source[key];
	return typeof value === 'number' ? String(value) : '';
}

function booleanAt(source: JsonObject, key: string, fallback = false): boolean {
	const value = source[key];
	return typeof value === 'boolean' ? value : fallback;
}

function stringListAt(source: JsonObject, key: string): string[] {
	const value = source[key];
	if (!Array.isArray(value)) return [];
	return value.filter((item): item is string => typeof item === 'string');
}
