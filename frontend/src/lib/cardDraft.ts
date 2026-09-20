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

/** A multilingual creator-notes row; `key` is an ISO 639-1 language code. */
export type NotesRow = { key: string; value: string };

/** A card asset (V3), keeping its original JSON so unknown keys survive. */
export type DraftAsset = {
	base: JsonObject;
	type: string;
	uri: string;
	name: string;
	ext: string;
};

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
	useRegex: boolean;
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
	nickname: string;
	description: string;
	personality: string;
	scenario: string;
	firstMes: string;
	alternateGreetings: string[];
	groupOnlyGreetings: string[];
	mesExample: string;
	tags: string[];
	creator: string;
	characterVersion: string;
	creatorNotes: string;
	creatorNotesMultilingual: NotesRow[];
	systemPrompt: string;
	postHistoryInstructions: string;
	source: string[];
	assets: DraftAsset[];
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

/**
 * Deep-copy JSON data.
 *
 * `structuredClone` throws `DataCloneError` when handed a `Proxy`, and a card can
 * reach the editor as Svelte reactive state (which deep-proxies plain objects).
 * Cards are JSON by definition, so a JSON round trip is a faithful fallback.
 */
function cloneJson<T>(value: T): T {
	try {
		return structuredClone(value);
	} catch {
		return JSON.parse(JSON.stringify(value)) as T;
	}
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
		nickname: '',
		description: '',
		personality: '',
		scenario: '',
		firstMes: '',
		alternateGreetings: [],
		groupOnlyGreetings: [],
		mesExample: '',
		tags: [],
		creator: '',
		characterVersion: '',
		creatorNotes: '',
		creatorNotesMultilingual: [],
		systemPrompt: '',
		postHistoryInstructions: '',
		source: [],
		assets: [],
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
		useRegex: false,
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
		base: cloneJson(card),
		name: stringAt(data, 'name'),
		nickname: stringAt(data, 'nickname'),
		description: stringAt(data, 'description'),
		personality: stringAt(data, 'personality'),
		scenario: stringAt(data, 'scenario'),
		firstMes: stringAt(data, 'first_mes'),
		alternateGreetings: stringListAt(data, 'alternate_greetings'),
		groupOnlyGreetings: stringListAt(data, 'group_only_greetings'),
		mesExample: stringAt(data, 'mes_example'),
		tags: stringListAt(data, 'tags'),
		creator: stringAt(data, 'creator'),
		characterVersion: stringAt(data, 'character_version'),
		creatorNotes: stringAt(data, 'creator_notes'),
		creatorNotesMultilingual: notesRowsAt(data, 'creator_notes_multilingual'),
		systemPrompt: stringAt(data, 'system_prompt'),
		postHistoryInstructions: stringAt(data, 'post_history_instructions'),
		source: stringListAt(data, 'source'),
		assets: assetRowsAt(data, 'assets'),
		book: bookJson === null ? null : bookFromJson(bookJson),
		extensions: extensionRows(objectAt(data, 'extensions'))
	};
}

export function cardFromDraft(draft: Draft): JsonObject {
	const card = cloneJson(draft.base);
	// The editor always saves the newest card format it understands. Unknown keys
	// (including the backend-stamped `creation_date`/`modification_date`) stay in
	// `base`, so only the envelope version is stamped here.
	card.spec = 'chara_card_v3';
	card.spec_version = '3.0';

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
	data.group_only_greetings = cleanList(draft.groupOnlyGreetings);
	data.tags = cleanList(draft.tags);
	data.extensions = extensionsFromRows(draft.extensions);

	setOptional(data, 'nickname', draft.nickname);

	const source = cleanList(draft.source);
	if (source.length > 0) data.source = source;
	else delete data.source;

	const notes = notesFromRows(draft.creatorNotesMultilingual);
	if (notes === null) delete data.creator_notes_multilingual;
	else data.creator_notes_multilingual = notes;

	if (draft.assets.length === 0) delete data.assets;
	else data.assets = draft.assets.map(assetFromDraft);

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

	problems.push(...creatorNotesProblems(draft.creatorNotesMultilingual));
	draft.assets.forEach((asset, index) => {
		problems.push(...assetProblems(asset, index));
	});

	if (draft.book !== null) {
		problems.push(...bookProblems(draft.book));
	}

	return problems;
}

/** Problems that would make a lorebook invalid, shared by cards and world books. */
export function bookProblems(book: DraftBook): string[] {
	const problems: string[] = [];

	problems.push(...numberProblems('Scan depth', book.scanDepth));
	problems.push(...numberProblems('Token budget', book.tokenBudget));
	problems.push(...jsonProblems('Character book extensions', book.extensions));

	book.entries.forEach((entry, index) => {
		const label = entry.name.trim() || `Entry ${index + 1}`;
		problems.push(...numberProblems(`${label}: insertion order`, String(entry.insertionOrder)));
		problems.push(...numberProblems(`${label}: priority`, entry.priority));
		problems.push(...jsonProblems(`${label}: extensions`, entry.extensions));
	});

	return problems;
}

export function bookFromJson(bookJson: JsonObject): DraftBook {
	const entriesJson = Array.isArray(bookJson.entries) ? bookJson.entries : [];
	return {
		base: cloneJson(bookJson),
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
		base: cloneJson(entry),
		keys: stringListAt(entry, 'keys').join(', '),
		secondaryKeys: stringListAt(entry, 'secondary_keys').join(', '),
		content: stringAt(entry, 'content'),
		enabled: booleanAt(entry, 'enabled', true),
		caseSensitive: booleanAt(entry, 'case_sensitive'),
		selective: booleanAt(entry, 'selective'),
		constant: booleanAt(entry, 'constant'),
		useRegex: booleanAt(entry, 'use_regex'),
		insertionOrder: typeof entry.insertion_order === 'number' ? entry.insertion_order : 0,
		priority: numberTextAt(entry, 'priority'),
		position: position === 'before_char' || position === 'after_char' ? position : '',
		name: stringAt(entry, 'name'),
		comment: stringAt(entry, 'comment'),
		// V3 allows a string id, so numbers are shown as text and written back as-is.
		id: idTextAt(entry, 'id'),
		extensions: JSON.stringify(objectAt(entry, 'extensions'), null, 2)
	};
}

export function bookFromDraft(book: DraftBook): JsonObject {
	const out = cloneJson(book.base);
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
	const out = cloneJson(entry.base);
	out.keys = splitList(entry.keys);
	out.content = entry.content;
	out.extensions = jsonOrRaw(entry.extensions, out.extensions);
	out.enabled = entry.enabled;
	// V3 requires `use_regex` to be present, so it is always written.
	out.use_regex = entry.useRegex;
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
	setIdText(out, 'id', entry.id);
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

/** Build the multilingual notes object, or `null` when no row is usable. */
function notesFromRows(rows: NotesRow[]): JsonObject | null {
	const out: JsonObject = {};
	let written = 0;
	for (const row of rows) {
		const key = row.key.trim();
		if (key === '') continue;
		out[key] = row.value;
		written += 1;
	}
	return written === 0 ? null : out;
}

/** Overlay the edited asset fields onto its original JSON. */
function assetFromDraft(asset: DraftAsset): JsonObject {
	const out = cloneJson(asset.base);
	out.type = asset.type.trim();
	out.uri = asset.uri.trim();
	out.name = asset.name.trim();
	out.ext = asset.ext.trim();
	return out;
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

function creatorNotesProblems(rows: NotesRow[]): string[] {
	const problems: string[] = [];

	const duplicate = firstDuplicate(rows.map((row) => row.key.trim()));
	if (duplicate) problems.push(`Duplicate creator notes language "${duplicate}".`);

	for (const row of rows) {
		const key = row.key.trim();
		if (key === '' || isLanguageCode(key)) continue;
		problems.push(`Creator notes language "${key}" must be a 2-letter ISO 639-1 code.`);
	}

	return problems;
}

/** ISO 639-1 codes are exactly two letters, with no region suffix. */
function isLanguageCode(key: string): boolean {
	return /^[a-z]{2}$/i.test(key);
}

function assetProblems(asset: DraftAsset, index: number): string[] {
	// A valid extension is lowercase alphanumerics: no uppercase, no dot, no
	// whitespace, and not empty. Anything else is reported.
	if (/^[a-z0-9]+$/.test(asset.ext)) return [];
	return [`Asset ${index + 1}: extension must be lowercase without a dot.`];
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

// V3 entry ids may be numbers or strings, so the editor round-trips them as text
// and only re-types them when the user actually edits the value.
function idTextAt(source: JsonObject, key: string): string {
	const value = source[key];
	return typeof value === 'number' || typeof value === 'string' ? String(value) : '';
}

function setIdText(target: JsonObject, key: string, text: string): void {
	const trimmed = text.trim();
	if (trimmed === '') {
		delete target[key];
		return;
	}
	const current = target[key];
	const currentText =
		typeof current === 'number' || typeof current === 'string' ? String(current) : '';
	// Unchanged: leave the original value (and its type) alone.
	if (currentText === trimmed) return;
	target[key] = /^-?\d+$/.test(trimmed) ? Number(trimmed) : trimmed;
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

/** Multilingual notes as ordered rows; non-string values are skipped. */
function notesRowsAt(source: JsonObject, key: string): NotesRow[] {
	const value = source[key];
	if (!isObject(value)) return [];
	const rows: NotesRow[] = [];
	for (const [rowKey, rowValue] of Object.entries(value)) {
		if (typeof rowValue !== 'string') continue;
		rows.push({ key: rowKey, value: rowValue });
	}
	return rows;
}

function assetRowsAt(source: JsonObject, key: string): DraftAsset[] {
	const value = source[key];
	if (!Array.isArray(value)) return [];
	return value.filter(isObject).map((item) => ({
		base: cloneJson(item),
		type: stringAt(item, 'type'),
		uri: stringAt(item, 'uri'),
		name: stringAt(item, 'name'),
		ext: stringAt(item, 'ext')
	}));
}
