import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { error } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
	const id = params.id;
	const user = await db.query.users.findFirst({ where: eq(users.id, id) });
	if (!user) {
		error(404, 'Not Found');
	}
	return { id, user };
};
