// Reactive auth state shared across routes.
//
// Tokens are stateless on the backend, so the token in `localStorage` is the
// whole session. This module keeps that in runes-backed state so components can
// react to sign-in and sign-out.
import {
	ApiError,
	getMe,
	login as apiLogin,
	logout as apiLogout,
	register as apiRegister,
	type User
} from './api';

const TOKEN_KEY = 'sparklchat.token';

let token = $state<string | null>(null);
let user = $state<User | null>(null);
let ready = $state(false);
let bootstrapped: Promise<void> | null = null;

function persist(value: string | null): void {
	if (value === null) localStorage.removeItem(TOKEN_KEY);
	else localStorage.setItem(TOKEN_KEY, value);
}

// The dev backend restarts constantly (auto-reload on every save), and a page
// load that lands in that window fails `getMe` with a network error, not a
// 401/403. That's not a rejected token, so it gets one short retry before we
// give up on reaching the server — only an actual 401/403 counts as "signed
// out".
async function fetchCurrentUser(candidate: string, attempt = 0): Promise<User | 'invalid'> {
	try {
		return await getMe(candidate);
	} catch (err) {
		if (err instanceof ApiError && (err.status === 401 || err.status === 403)) return 'invalid';
		if (attempt > 0) throw err;
		await new Promise((resolve) => setTimeout(resolve, 1500));
		return fetchCurrentUser(candidate, attempt + 1);
	}
}

async function bootstrap(): Promise<void> {
	const stored = localStorage.getItem(TOKEN_KEY);
	if (!stored) {
		ready = true;
		return;
	}

	token = stored;
	try {
		const result = await fetchCurrentUser(stored);
		if (result === 'invalid') {
			// Expired or revoked: drop it and fall back to the signed-out state.
			token = null;
			user = null;
			persist(null);
		} else {
			user = result;
		}
	} catch {
		// Still unreachable after a retry: keep the token. `user` stays unset
		// until a request succeeds; a genuine 401/403 later on still signs the
		// user out via `setUnauthorizedHandler`.
	}
	ready = true;
}

async function login(email: string, password: string): Promise<void> {
	const issued = await apiLogin(email, password);
	token = issued.access_token;
	persist(token);
	user = await getMe(token);
}

async function register(email: string, password: string): Promise<void> {
	await apiRegister(email, password);
	await login(email, password);
}

async function signOut(): Promise<void> {
	const current = token;
	// Clear locally first so a failing logout call can't strand the token.
	token = null;
	user = null;
	persist(null);
	if (current) {
		try {
			await apiLogout(current);
		} catch {
			// The token is already discarded; there is nothing to recover.
		}
	}
}

export const auth = {
	get token(): string | null {
		return token;
	},
	get user(): User | null {
		return user;
	},
	get ready(): boolean {
		return ready;
	},
	get isAuthenticated(): boolean {
		return token !== null;
	},

	// Idempotent: concurrent callers share the initial read from storage.
	load(): Promise<void> {
		if (!bootstrapped) bootstrapped = bootstrap();
		return bootstrapped;
	},

	login,
	register,
	signOut
};
