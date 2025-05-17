import type { PageLoad } from './$types';
import { db } from '$lib/server/db';
import { users, posts, comments } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

export const load: PageLoad = async ({ params }) => {
	const { id } = params;
	const _post = (await db.select().from(posts).where(eq(posts.id, id)))[0];
	const _comments = await db
		.select({
			comment: comments,
			user: users
		})
		.from(comments)
		.leftJoin(users, eq(users.id, comments.user_id))
		.where(eq(comments.post_id, id));
	const _users = await db.select().from(users).where(eq(users.id, _post.user_id));
	return {
		id,
		post: _post,
		comments: _comments,
		user: _users[0]
	};
};
