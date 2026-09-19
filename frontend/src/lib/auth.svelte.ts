// Reactive auth state shared across routes.
//
// Tokens are stateless on the backend, so the token in `localStorage` is the
// whole session. This module keeps that in runes-backed state so components can
// react to sign-in and sign-out.
import {
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

async function bootstrap(): Promise<void> {
	const stored = localStorage.getItem(TOKEN_KEY);
	if (!stored) {
		ready = true;
		return;
	}

	token = stored;
	try {
		user = await getMe(stored);
	} catch {
		// Expired or revoked: drop it and fall back to the signed-out state.
		token = null;
		user = null;
		persist(null);
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
