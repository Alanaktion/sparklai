import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ parent }) => {
	const data = await parent();
	if (!data.isOwner) {
		error(403, 'Forbidden');
	}
	return {};
};
