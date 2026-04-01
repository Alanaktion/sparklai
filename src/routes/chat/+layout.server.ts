import { db } from '$lib/server/db';
import { chats, relationships, users } from '$lib/server/db/schema';
import { and, desc, eq, inArray } from 'drizzle-orm';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals }) => {
	if (!locals.humanUser) {
		return { users: [] };
	}

	const followed_user_ids = db
		.select({ id: relationships.related_user_id })
		.from(relationships)
		.where(
			and(
				eq(relationships.user_id, locals.humanUser.id),
				eq(relationships.relationship_type, 'follow')
			)
		);

	const users_result = await db.query.users.findMany({
		columns: { id: true, name: true, image_id: true },
		where: and(
			eq(users.is_human, false),
			eq(users.is_active, true),
			inArray(users.id, followed_user_ids)
		),
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
