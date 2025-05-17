import type { PageLoad } from './$types';
import { db } from '$lib/server/db';
import { users, posts, images } from '$lib/server/db/schema';
import { desc, eq } from 'drizzle-orm';

export const load: PageLoad = async ({ params }) => {
	const id = params.id;
	return {
		id,
		user: (await db.select().from(users).where(eq(users.id, id)))[0],
		posts: await db
			.select()
			.from(posts)
			.where(eq(posts.user_id, id))
			.orderBy(desc(posts.created_at)),
		images: await db
			.select({ id: images.id, params: images.params })
			.from(images)
			.where(eq(images.user_id, id))
	};
};
