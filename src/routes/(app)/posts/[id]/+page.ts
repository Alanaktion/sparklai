import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

// Universal (client-side) load, replacing `+page.server.ts` — hits the FastAPI post-bundle
// endpoint (`GET /api/posts/{id}`) instead of querying the DB directly.
export const load: PageLoad = async ({ params, fetch }) => {
	const response = await fetch(`/api/posts/${params.id}`);
	if (response.status === 404) {
		error(404, 'Not Found');
	}
	if (!response.ok) {
		error(response.status, 'Failed to load post');
	}

	const body = await response.json();
	return {
		id: body.id,
		post: body.post,
		images: body.images,
		media: body.media,
		users: body.users
	};
};
