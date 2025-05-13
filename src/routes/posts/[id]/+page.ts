import type { PageLoad } from './$types';
import { loadJson } from '$lib/api';

export const load: PageLoad = async ({ params }) => {
	const id = params.id;
	const post = await loadJson(`posts/${id}`);
	const comments = await loadJson(`posts/${id}/comments`);
	const user = await loadJson(`users/${post.user_id}`);
	return { id, post, comments, user };
};
