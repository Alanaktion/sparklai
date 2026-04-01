import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals }) => {
	const humanUsers = await db.select().from(users).where(eq(users.is_human, true));
	return {
		humanUsers,
		activeHumanUser: locals.humanUser ?? null
	};
};
