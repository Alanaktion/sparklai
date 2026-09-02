import type { LayoutLoad } from './$types';

// Universal (client-side) load, replacing `+layout.server.ts` — hits the FastAPI conversation-list
// endpoint (`GET /api/chats`) instead of querying the DB directly. That endpoint itself resolves
// the active creator from the session cookie and returns `[]` when logged out, so there's nothing
// else to check here.
export const load: LayoutLoad = async ({ fetch }) => {
	const response = await fetch('/api/chats');
	const users = response.ok ? await response.json() : [];
	return { users };
};
