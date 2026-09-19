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

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
	const response = await fetch(`${API_BASE}${path}`, init);

	if (!response.ok) {
		let detail = response.statusText;
		try {
			const body = (await response.json()) as { detail?: unknown };
			if (typeof body.detail === 'string') detail = body.detail;
		} catch {
			// Non-JSON error body; keep the status text.
		}
		throw new ApiError(response.status, detail);
	}

	if (response.status === 204) return undefined as T;
	return (await response.json()) as T;
}

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

export function getMe(token: string): Promise<User> {
	return apiFetch<User>('/me', { headers: { Authorization: `Bearer ${token}` } });
}
