import type { CreatorType } from '$lib/server/db/schema';
import type { LayoutLoad } from './$types';

// Universal (client-side) load, replacing the old `+layout.server.ts` — it now hits the FastAPI
// backend over `fetch` instead of querying the DB directly. Runs in the browser under
// adapter-static's SPA mode, same as everywhere else; `invalidateAll()` (used by
// CreatorSwitcher.svelte after login/logout/create) still works exactly as it did before.
export const load: LayoutLoad = async ({ fetch }) => {
	const [creatorsRes, meRes] = await Promise.all([
		fetch('/api/creators'),
		fetch('/api/creators/me')
	]);

	const creators: CreatorType[] = creatorsRes.ok ? await creatorsRes.json() : [];
	const activeCreator: CreatorType | null = meRes.ok ? await meRes.json() : null;

	return { creators, activeCreator };
};
