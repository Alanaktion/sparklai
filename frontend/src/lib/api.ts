// Thin fetch wrapper around the FastAPI backend.
//
// In development Vite proxies `/api` to the backend (see vite.config.ts); in
// production FastAPI serves this app and the API from the same origin, so
// relative URLs work unchanged in both cases.
const API_BASE = '/api';

export class ApiError extends Error {
	constructor(
		readonly status: number,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}
}

// Components register a handler here so a 401 from any request can drop the
// stale token; navigation is left to the caller.
let unauthorizedHandler: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
	unauthorizedHandler = handler;
}

function reportUnauthorized(status: number): void {
	if (status === 401) unauthorizedHandler?.();
}

async function errorDetail(response: Response): Promise<string> {
	let detail = response.statusText;
	try {
		const body = (await response.json()) as { detail?: unknown };
		if (typeof body.detail === 'string') detail = body.detail;
	} catch {
		// Non-JSON error body; keep the status text.
	}
	return detail;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
	const response = await fetch(`${API_BASE}${path}`, init);

	if (!response.ok) {
		reportUnauthorized(response.status);
		throw new ApiError(response.status, await errorDetail(response));
	}

	if (response.status === 204) return undefined as T;
	return (await response.json()) as T;
}

function jsonInit(method: string, body: unknown, token?: string): RequestInit {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (token) headers.Authorization = `Bearer ${token}`;
	return { method, headers, body: JSON.stringify(body) };
}

function bearer(token: string): Record<string, string> {
	return { Authorization: `Bearer ${token}` };
}

// --- Auth -----------------------------------------------------------------

export type Health = { status: string };

export type User = {
	id: number;
	email: string;
	is_active: boolean;
	created_at: string;
};

export type Token = { access_token: string; token_type: string };

export function getHealth(): Promise<Health> {
	return apiFetch<Health>('/health');
}

export function login(email: string, password: string): Promise<Token> {
	// The backend uses the OAuth2 password grant, which expects form encoding.
	const body = new URLSearchParams({ username: email, password });
	return apiFetch<Token>('/auth/login', {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body
	});
}

export function register(email: string, password: string): Promise<User> {
	return apiFetch<User>('/auth/register', jsonInit('POST', { email, password }));
}

export function getMe(token: string): Promise<User> {
	return apiFetch<User>('/me', { headers: bearer(token) });
}

export function logout(token: string): Promise<void> {
	return apiFetch<void>('/auth/logout', { method: 'POST', headers: bearer(token) });
}

// --- Settings -------------------------------------------------------------

export type UserSettings = {
	user_id: number;
	display_name: string;
	default_system_prompt: string;
	default_ujb: string;
	default_provider_id: number | null;
};

export type UserSettingsUpdate = {
	display_name?: string;
	default_system_prompt?: string;
	default_ujb?: string;
	default_provider_id?: number | null;
};

export function getSettings(token: string): Promise<UserSettings> {
	return apiFetch<UserSettings>('/settings', { headers: bearer(token) });
}

export function updateSettings(token: string, patch: UserSettingsUpdate): Promise<UserSettings> {
	return apiFetch<UserSettings>('/settings', jsonInit('PATCH', patch, token));
}

// --- Providers ------------------------------------------------------------

export type ProviderType = 'openai' | 'anthropic' | 'ollama' | 'koboldcpp' | 'custom';

export type Provider = {
	id: number;
	name: string;
	provider_type: ProviderType;
	base_url: string;
	model: string;
	temperature: number | null;
	max_tokens: number | null;
	top_p: number | null;
	extra_params: Record<string, unknown>;
	has_api_key: boolean;
	is_default: boolean;
	created_at: string;
	updated_at: string;
};

export type ProviderInput = {
	name: string;
	provider_type: ProviderType;
	base_url?: string | null;
	api_key?: string | null;
	model: string;
	temperature?: number | null;
	max_tokens?: number | null;
	top_p?: number | null;
	extra_params?: Record<string, unknown>;
};

export type ProviderTestResult = { ok: boolean; message: string; reply: string | null };

export function listProviders(token: string): Promise<Provider[]> {
	return apiFetch<Provider[]>('/providers', { headers: bearer(token) });
}

export function createProvider(token: string, input: ProviderInput): Promise<Provider> {
	return apiFetch<Provider>('/providers', jsonInit('POST', input, token));
}

export function updateProvider(
	token: string,
	id: number,
	patch: Partial<ProviderInput>
): Promise<Provider> {
	return apiFetch<Provider>(`/providers/${id}`, jsonInit('PATCH', patch, token));
}

export function deleteProvider(token: string, id: number): Promise<void> {
	return apiFetch<void>(`/providers/${id}`, { method: 'DELETE', headers: bearer(token) });
}

export function testProvider(token: string, id: number): Promise<ProviderTestResult> {
	return apiFetch<ProviderTestResult>(`/providers/${id}/test`, {
		method: 'POST',
		headers: bearer(token)
	});
}

// --- Characters -----------------------------------------------------------

export type CharacterSummary = {
	id: number;
	name: string;
	spec_version: string;
	source: string;
	tags: string[];
	creator: string;
	character_version: string;
	has_avatar: boolean;
	created_at: string;
	updated_at: string;
};

export type CharacterCardData = {
	name?: string;
	description?: string;
	personality?: string;
	scenario?: string;
	first_mes?: string;
	mes_example?: string;
	creator_notes?: string;
	system_prompt?: string;
	post_history_instructions?: string;
	alternate_greetings?: string[];
	character_book?: unknown;
	tags?: string[];
	creator?: string;
	character_version?: string;
};

export type CharacterCard = {
	spec?: string;
	spec_version?: string;
	data?: CharacterCardData;
};

export type CharacterDetail = CharacterSummary & { card: CharacterCard };

export type CharacterFilters = {
	q?: string;
	/** Matches any of these tags, ignoring case. */
	tags?: string[];
	creator?: string;
	characterVersion?: string;
	limit?: number;
	offset?: number;
};

export function listCharacters(
	token: string,
	filters: CharacterFilters = {}
): Promise<CharacterSummary[]> {
	const params = new URLSearchParams();
	if (filters.q) params.set('q', filters.q);
	for (const tag of filters.tags ?? []) {
		if (tag.trim()) params.append('tags', tag.trim());
	}
	if (filters.creator) params.set('creator', filters.creator);
	if (filters.characterVersion) params.set('character_version', filters.characterVersion);
	params.set('limit', String(filters.limit ?? 100));
	params.set('offset', String(filters.offset ?? 0));
	return apiFetch<CharacterSummary[]>(`/characters?${params.toString()}`, {
		headers: bearer(token)
	});
}

export function createCharacter(token: string, card: unknown): Promise<CharacterDetail> {
	return apiFetch<CharacterDetail>('/characters', jsonInit('POST', card, token));
}

export function uploadCharacter(token: string, file: File): Promise<CharacterDetail> {
	const body = new FormData();
	body.append('file', file);
	// No Content-Type: the browser sets the multipart boundary.
	return apiFetch<CharacterDetail>('/characters/upload', {
		method: 'POST',
		headers: bearer(token),
		body
	});
}

export function getCharacter(token: string, id: number): Promise<CharacterDetail> {
	return apiFetch<CharacterDetail>(`/characters/${id}`, { headers: bearer(token) });
}

export function updateCharacter(token: string, id: number, card: unknown): Promise<CharacterDetail> {
	return apiFetch<CharacterDetail>(`/characters/${id}`, jsonInit('PATCH', { card }, token));
}

export function deleteCharacter(token: string, id: number): Promise<void> {
	return apiFetch<void>(`/characters/${id}`, { method: 'DELETE', headers: bearer(token) });
}

export type CharacterExportFormat = 'v1' | 'v2' | 'png';
export type ChatExportFormat = 'json' | 'markdown';

/**
 * Both export endpoints require the bearer token, so they cannot be plain links.
 * Fetch the bytes, then hand the browser a blob URL to save.
 */
export async function downloadCharacterCard(
	token: string,
	id: number,
	format: CharacterExportFormat
): Promise<void> {
	return downloadFile(
		`/characters/${id}/export?format=${format}`,
		token,
		`character.${format === 'png' ? 'png' : 'json'}`
	);
}

export async function downloadChatTranscript(
	token: string,
	sessionId: number,
	format: ChatExportFormat
): Promise<void> {
	return downloadFile(
		`/sessions/${sessionId}/export?format=${format}`,
		token,
		`transcript.${format === 'json' ? 'json' : 'md'}`
	);
}

async function downloadFile(path: string, token: string, fallbackName: string): Promise<void> {
	const response = await fetch(`${API_BASE}${path}`, { headers: bearer(token) });
	if (!response.ok) {
		reportUnauthorized(response.status);
		throw new ApiError(response.status, await errorDetail(response));
	}

	const blob = await response.blob();
	const url = URL.createObjectURL(blob);
	const anchor = document.createElement('a');
	anchor.href = url;
	anchor.download = filenameFrom(response.headers.get('content-disposition')) ?? fallbackName;
	document.body.appendChild(anchor);
	anchor.click();
	anchor.remove();
	URL.revokeObjectURL(url);
}

function filenameFrom(disposition: string | null): string | null {
	return disposition?.match(/filename="([^"]+)"/)?.[1] ?? null;
}

export function fetchAvatar(token: string, id: number): Promise<Blob> {
	return fetch(`${API_BASE}/characters/${id}/avatar`, { headers: bearer(token) }).then(
		async (response) => {
			if (!response.ok) {
				reportUnauthorized(response.status);
				throw new ApiError(response.status, await errorDetail(response));
			}
			return response.blob();
		}
	);
}

// --- Sessions & messages --------------------------------------------------

export type MessageRole = 'system' | 'user' | 'assistant';

export type Message = {
	id: number;
	session_id: number;
	role: MessageRole;
	content: string;
	created_at: string;
	is_greeting: boolean;
	swipe_index: number;
	swipe_count: number;
};

export type SessionSummary = {
	id: number;
	character_id: number;
	title: string;
	provider_id: number | null;
	use_character_book: boolean;
	created_at: string;
	updated_at: string;
};

export type SessionDetail = SessionSummary & {
	system_prompt_override: string | null;
	post_history_override: string | null;
	messages: Message[];
};

export type SessionUpdate = {
	title?: string;
	provider_id?: number | null;
	system_prompt_override?: string | null;
	post_history_override?: string | null;
	use_character_book?: boolean;
};

export type SwipeDirection = 'next' | 'prev';

export function listSessions(token: string, characterId: number): Promise<SessionSummary[]> {
	return apiFetch<SessionSummary[]>(`/characters/${characterId}/sessions`, {
		headers: bearer(token)
	});
}

export function createSession(
	token: string,
	characterId: number,
	body: { title?: string; provider_id?: number | null } = {}
): Promise<SessionDetail> {
	return apiFetch<SessionDetail>(
		`/characters/${characterId}/sessions`,
		jsonInit('POST', body, token)
	);
}

export function getSession(token: string, sessionId: number): Promise<SessionDetail> {
	return apiFetch<SessionDetail>(`/sessions/${sessionId}`, { headers: bearer(token) });
}

export function updateSession(
	token: string,
	sessionId: number,
	patch: SessionUpdate
): Promise<SessionDetail> {
	return apiFetch<SessionDetail>(`/sessions/${sessionId}`, jsonInit('PATCH', patch, token));
}

export function deleteSession(token: string, sessionId: number): Promise<void> {
	return apiFetch<void>(`/sessions/${sessionId}`, { method: 'DELETE', headers: bearer(token) });
}

export function listMessages(token: string, sessionId: number): Promise<Message[]> {
	return apiFetch<Message[]>(`/sessions/${sessionId}/messages`, { headers: bearer(token) });
}

export type MessagePair = { user: Message; assistant: Message };

export function sendMessage(token: string, sessionId: number, content: string): Promise<MessagePair> {
	return apiFetch<MessagePair>(`/sessions/${sessionId}/messages`, jsonInit('POST', { content }, token));
}

export function editMessage(
	token: string,
	sessionId: number,
	messageId: number,
	content: string
): Promise<Message> {
	return apiFetch<Message>(
		`/sessions/${sessionId}/messages/${messageId}`,
		jsonInit('PATCH', { content }, token)
	);
}

export function deleteMessage(token: string, sessionId: number, messageId: number): Promise<void> {
	return apiFetch<void>(`/sessions/${sessionId}/messages/${messageId}`, {
		method: 'DELETE',
		headers: bearer(token)
	});
}

export function swipeMessage(
	token: string,
	sessionId: number,
	messageId: number,
	direction: SwipeDirection
): Promise<Message> {
	return apiFetch<Message>(
		`/sessions/${sessionId}/messages/${messageId}/swipe`,
		jsonInit('POST', { direction }, token)
	);
}

export function regenerate(token: string, sessionId: number): Promise<{ assistant: Message }> {
	return apiFetch<{ assistant: Message }>(`/sessions/${sessionId}/regenerate`, {
		method: 'POST',
		headers: bearer(token)
	});
}

// --- Server-Sent Events over POST -----------------------------------------

export type SseEvent = { event: string; data: unknown };

function parseEventBlock(block: string): SseEvent | null {
	let event = 'message';
	const dataLines: string[] = [];

	for (const line of block.split('\n')) {
		if (!line || line.startsWith(':')) continue;
		const colon = line.indexOf(':');
		const field = colon === -1 ? line : line.slice(0, colon);
		let value = colon === -1 ? '' : line.slice(colon + 1);
		if (value.startsWith(' ')) value = value.slice(1);
		if (field === 'event') event = value;
		else if (field === 'data') dataLines.push(value);
	}

	if (dataLines.length === 0) return null;
	const raw = dataLines.join('\n');
	try {
		return { event, data: JSON.parse(raw) as unknown };
	} catch {
		return { event, data: raw };
	}
}

// `EventSource` can't send headers or a POST body, so the event stream is read
// off the fetch response body and framed by hand.
async function readEventStream(
	stream: ReadableStream<Uint8Array>,
	onEvent: (event: SseEvent) => void
): Promise<void> {
	const reader = stream.getReader();
	const decoder = new TextDecoder();
	let buffer = '';

	try {
		for (;;) {
			const { done, value } = await reader.read();
			if (done) break;
			buffer += decoder.decode(value, { stream: true });
			buffer = buffer.replace(/\r\n/g, '\n');

			let boundary = buffer.indexOf('\n\n');
			while (boundary !== -1) {
				const block = buffer.slice(0, boundary);
				buffer = buffer.slice(boundary + 2);
				const parsed = parseEventBlock(block);
				if (parsed) onEvent(parsed);
				boundary = buffer.indexOf('\n\n');
			}
		}

		buffer += decoder.decode();
		const parsed = parseEventBlock(buffer);
		if (parsed) onEvent(parsed);
	} finally {
		reader.releaseLock();
	}
}

async function openEventStream(
	path: string,
	token: string,
	body: unknown,
	signal: AbortSignal | undefined,
	onEvent: (event: SseEvent) => void
): Promise<void> {
	const response = await fetch(`${API_BASE}${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...bearer(token) },
		body: JSON.stringify(body),
		signal
	});

	if (!response.ok) {
		reportUnauthorized(response.status);
		throw new ApiError(response.status, await errorDetail(response));
	}
	if (!response.body) throw new ApiError(response.status, 'The response has no body');

	await readEventStream(response.body, onEvent);
}

export type ChatStreamHandlers = {
	onUser?: (message: Message) => void;
	onDelta?: (delta: string) => void;
	onMessage?: (message: Message) => void;
	onError?: (detail: string) => void;
	onDone?: () => void;
};

function payloadOf(event: SseEvent): Record<string, unknown> {
	return typeof event.data === 'object' && event.data !== null
		? (event.data as Record<string, unknown>)
		: {};
}

function dispatchChatEvent(event: SseEvent, handlers: ChatStreamHandlers): void {
	switch (event.event) {
		case 'user': {
			const message = payloadOf(event).message as Message | undefined;
			if (message) handlers.onUser?.(message);
			break;
		}
		case 'delta': {
			const delta = payloadOf(event).delta;
			if (typeof delta === 'string') handlers.onDelta?.(delta);
			break;
		}
		case 'message': {
			const message = payloadOf(event).message as Message | undefined;
			if (message) handlers.onMessage?.(message);
			break;
		}
		case 'error': {
			const detail = payloadOf(event).detail;
			handlers.onError?.(typeof detail === 'string' ? detail : 'Stream failed');
			break;
		}
		case 'done':
			handlers.onDone?.();
			break;
	}
}

export function streamMessage(
	token: string,
	sessionId: number,
	content: string,
	handlers: ChatStreamHandlers,
	signal?: AbortSignal
): Promise<void> {
	return openEventStream(
		`/sessions/${sessionId}/messages/stream`,
		token,
		{ content },
		signal,
		(event) => dispatchChatEvent(event, handlers)
	);
}

export function streamRegenerate(
	token: string,
	sessionId: number,
	handlers: ChatStreamHandlers,
	signal?: AbortSignal
): Promise<void> {
	return openEventStream(
		`/sessions/${sessionId}/regenerate/stream`,
		token,
		{},
		signal,
		(event) => dispatchChatEvent(event, handlers)
	);
}
