import type { PageLoad } from './$types';
import { loadJson } from '$lib/api';

export const load: PageLoad = async ({ params }) => {
	const id = params.id;
	const user = await loadJson(`users/${id}`);
	const posts = await loadJson(`users/${id}/posts`);
	const images = await loadJson(`users/${id}/images`);
	return { id, user, posts, images };
};
