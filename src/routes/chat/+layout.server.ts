import { db } from '$lib/server/db';
import { chats, users } from '$lib/server/db/schema';
import { and, desc, eq } from 'drizzle-orm';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals }) => {
	if (!locals.creator) {
		return { users: [] };
	}

	const users_result = await db.query.users.findMany({
		columns: { id: true, name: true, image_id: true },
		where: and(eq(users.is_active, true), eq(users.creator_id, locals.creator.id)),
		with: {
			chats: {
				columns: { id: true, body: true },
				orderBy: desc(chats.created_at),
				limit: 1
			}
		}
	});

	users_result.sort((a, b) => (b.chats[0]?.id ?? 0) - (a.chats[0]?.id ?? 0));

	return { users: users_result };
};
