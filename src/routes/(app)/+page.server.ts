import { db } from '$lib/server/db';
import { posts, relationships, users } from '$lib/server/db/schema';
import { and, desc, eq, inArray } from 'drizzle-orm';
import type { PageServerLoad } from './$types';

const INITIAL_POSTS_LIMIT = 15;

export const load: PageServerLoad = async ({ locals }) => {
	if (!locals.humanUser) {
		return { posts: [], hasMorePosts: false, users: [] };
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

	const active_followed_ids = db
		.select({ id: users.id })
		.from(users)
		.where(
			and(
				eq(users.is_active, true),
				eq(users.is_human, false),
				inArray(users.id, followed_user_ids)
			)
		);

	const rows = await db.query.posts.findMany({
		with: {
			image: { columns: { id: true, params: true, blur: true } },
			media: { columns: { id: true, type: true } }
		},
		where: inArray(posts.user_id, active_followed_ids),
		orderBy: desc(posts.id),
		limit: INITIAL_POSTS_LIMIT + 1
	});
	const hasMorePosts = rows.length > INITIAL_POSTS_LIMIT;

	return {
		posts: hasMorePosts ? rows.slice(0, INITIAL_POSTS_LIMIT) : rows,
		hasMorePosts,
		users: await db.select().from(users).where(inArray(users.id, active_followed_ids))
	};
};
