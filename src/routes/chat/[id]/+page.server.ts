import { db } from '$lib/server/db';
import { chats, users } from '$lib/server/db/schema';
import { error } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
	const user = await db.query.users.findFirst({
		where: eq(users.id, Number(params.id))
	});

	if (!user) {
		error(404, 'Not Found');
	}

	return {
		user,
		chats: db.query.chats.findMany({
			with: {
				image: {
					columns: { id: true, blur: true }
				}
			},
			where: eq(chats.user_id, Number(params.id)),
			orderBy: (chats, { asc }) => [asc(chats.id)]
		})
	};
};
