// Reactive theme preference shared across routes.
//
// The palettes live in app.css: dark is the default, `[data-theme='light']`
// overrides it, and `'system'` follows `prefers-color-scheme`. Rather than
// resolving the preference in JS we only mirror it onto the document root and
// let CSS pick the values, so OS changes apply without extra listeners.
export type ThemePreference = 'dark' | 'light' | 'system';

const THEME_KEY = 'sparklchat.theme';

let theme = $state<ThemePreference>('system');
let loaded = false;

function isPreference(value: string | null): value is ThemePreference {
	return value === 'dark' || value === 'light' || value === 'system';
}

/** Reflect the current preference on the document root. */
function apply(): void {
	if (theme === 'system') document.documentElement.removeAttribute('data-theme');
	else document.documentElement.setAttribute('data-theme', theme);
}

/** Read the stored preference and apply it. Safe to call more than once. */
function load(): void {
	if (loaded) return;
	const stored = localStorage.getItem(THEME_KEY);
	theme = isPreference(stored) ? stored : 'system';
	loaded = true;
	apply();
}

function setTheme(value: ThemePreference): void {
	theme = value;
	localStorage.setItem(THEME_KEY, value);
	apply();
}

export const themeStore = {
	get theme(): ThemePreference {
		return theme;
	},
	get loaded(): boolean {
		return loaded;
	},
	setTheme,
	apply,
	load
};
