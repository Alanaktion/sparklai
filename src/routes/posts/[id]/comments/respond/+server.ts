import { db } from '$lib/server/db';
import { comments, posts, users } from '$lib/server/db/schema';
import { generateComment } from '$lib/server/index.js';
import { error, json } from '@sveltejs/kit';
import { and, eq, sql } from 'drizzle-orm';

// Generate a new comment on the post
export async function POST({ params, request }) {
	const post_result = await db
		.select()
		.from(posts)
		.where(eq(posts.id, Number(params.id)));
	if (!post_result.length) {
		return error(404, {
			message: 'Not found'
		});
	}

	const data = await request.json();
	let user;
	if (data && data.user_id) {
		const users_result = await db.select().from(users).where(eq(users.id, data.user_id));
		user = users_result[0];
	} else {
		const users_result = await db
			.select()
			.from(users)
			.where(and(eq(users.is_active, true), eq(users.is_human, false)))
			.orderBy(sql`random()`)
			.limit(1);
		user = users_result[0];
	}

	const comment = await generateComment(user, post_result[0]);

	return json(
		await db.query.comments.findFirst({
			with: {
				user: { columns: { id: true, name: true, image_id: true } }
			},
			where: eq(comments.id, comment.id)
		})
	);
}
