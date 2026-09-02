import { error } from '@sveltejs/kit';
import type { LayoutLoad } from './$types';

// Universal (client-side) load, replacing `+layout.server.ts` — hits the FastAPI profile-bundle
// endpoint (`GET /api/users/{id}`) instead of querying the DB directly.
export const load: LayoutLoad = async ({ params, fetch }) => {
	const response = await fetch(`/api/users/${params.id}`);
	if (response.status === 404) {
		error(404, 'Not Found');
	}
	if (!response.ok) {
		error(response.status, 'Failed to load user');
	}

	const body = await response.json();
	return {
		id: body.id,
		user: body.user,
		isOwner: body.isOwner,
		posts: body.posts,
		images: body.images,
		relationships: body.relationships
	};
};
