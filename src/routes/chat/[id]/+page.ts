import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

// Universal (client-side) load, replacing `+page.server.ts` — only fetches the AI user now (via
// the existing profile-bundle endpoint). The chat history itself moved to a plain client fetch on
// the page component (see its `loadingChats` state), replacing SvelteKit's server-only
// streamed-promise pattern (`{#await data.chats}`), which has no equivalent under the SPA's
// `adapter-static`/client-only load model.
export const load: PageLoad = async ({ params, fetch }) => {
	const response = await fetch(`/api/users/${params.id}`);
	if (response.status === 404) {
		error(404, 'Not Found');
	}
	if (!response.ok) {
		error(response.status, 'Failed to load user');
	}

	const profile = await response.json();
	return { user: profile.user };
};
