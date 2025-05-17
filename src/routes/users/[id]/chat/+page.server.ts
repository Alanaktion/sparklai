import type { PageLoad } from './$types';
import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

export const load: PageLoad = async ({ params }) => {
	const id = params.id;
	return {
		id,
		user: (await db.select().from(users).where(eq(users.id, id)))[0]
	};
};
