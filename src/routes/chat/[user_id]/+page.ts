import type { PageLoad } from './$types';
import { loadJson } from '$lib/api';

export const load: PageLoad = async ({ params }) => {
	const user_id = params.user_id;
	const user = await loadJson(`users/${user_id}`);
	return { user_id, user };
};
