import { db } from '$lib/server/db';
import { creators } from '$lib/server/db/schema';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals }) => {
	const allCreators = await db.select().from(creators);
	return {
		creators: allCreators,
		activeCreator: locals.creator ?? null
	};
};
