import { db } from '$lib/server/db';
import { posts, users } from '$lib/server/db/schema';
import { and, desc, eq, inArray } from 'drizzle-orm';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	const active_user_ids = db
		.select({ id: users.id })
		.from(users)
		.where(and(eq(users.is_active, true), eq(users.is_human, false)));
	return {
		posts: await db.query.posts.findMany({
			with: {
				image: { columns: { id: true, params: true, blur: true } },
				media: { columns: { id: true, type: true } }
			},
			where: inArray(posts.user_id, active_user_ids),
			orderBy: desc(posts.created_at),
			limit: 30
		}),
		users: await db.select().from(users).where(inArray(users.id, active_user_ids))
	};
};
