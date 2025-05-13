import type { PageLoad } from './$types';
import { loadJson } from '$lib/api';

export const load: PageLoad = async () => {
	const posts = await loadJson(`posts`);
	const users = await loadJson(`users`);
	return { posts, users };
};
