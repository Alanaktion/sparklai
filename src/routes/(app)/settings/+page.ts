import type { PageLoad } from './$types';

// Universal (client-side) load, replacing `+page.server.ts`'s load — the form action that used to
// live alongside it is gone too; the page now PATCHes `/api/creators/me` directly (see
// +page.svelte), since form actions are a server-only SvelteKit feature this SPA doesn't have.
export const load: PageLoad = async ({ fetch }) => {
	const response = await fetch('/api/creators/me');
	return { creator: response.ok ? await response.json() : null };
};
