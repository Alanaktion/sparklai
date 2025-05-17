import type { PageLoad } from './$types';
import { db } from '$lib/server/db';
import { users, posts } from '$lib/server/db/schema';
import { and, desc, eq } from 'drizzle-orm';

export const load: PageLoad = async () => {
	return {
		posts: await db.select().from(posts).orderBy(desc(posts.created_at)).limit(20),
		users: await db
			.select()
			.from(users)
			.where(and(eq(users.is_active, 1), eq(users.is_human, 0)))
	};
};
