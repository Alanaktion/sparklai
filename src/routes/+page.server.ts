import { db } from '$lib/server/db';
import { posts, users } from '$lib/server/db/schema';
import { and, desc, eq } from 'drizzle-orm';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	return {
		posts: await db.query.posts.findMany({
			with: {
				image: { columns: { id: true, params: true, blur: true } }
			},
			orderBy: desc(posts.created_at),
			limit: 30
		}),
		users: await db
			.select()
			.from(users)
			.where(and(eq(users.is_active, true), eq(users.is_human, false)))
	};
};
