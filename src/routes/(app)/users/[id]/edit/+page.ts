import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

// Universal (client-side) load, replacing `+page.server.ts` — same ownership gate, now checked
// against data the layout already fetched from FastAPI instead of a server-only `parent()` call.
export const load: PageLoad = async ({ parent }) => {
	const data = await parent();
	if (!data.isOwner) {
		error(403, 'Forbidden');
	}
	return {};
};
