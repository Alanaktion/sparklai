import type { LlamaMessage } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { comments, posts, users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { and, eq, sql } from 'drizzle-orm';
import { completion } from '$lib/server/chat/index.js';

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

	// Load post info
	const post = post_result[0];
	const author_result = await db.select().from(users).where(eq(users.id, post.user_id));
	const author = author_result[0];

	// Load a random user to write the new comment
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

	const is_own_post = user.id === author.id;
	const history: LlamaMessage[] = [
		{
			role: 'system',
			content:
				`You are ${user.name} (${user.pronouns}), writing a comment on the given social media post. It can be a reply to other comments (if any), or directly responding to the post itself. *Do not include any meta-text, only the comment body.*\n` +
				`Your bio: ${user.bio}\n` +
				`Writing style: ${JSON.stringify(user.writing_style)}\n` +
				"Write a new comment. Do not include any roleplay or metatext, just write the actual response. If you don't know the language the original post is in, you can use your preferred language."
		},
		{
			role: 'user',
			content: is_own_post
				? `This is your own post that you wrote: ${post.body}`
				: `Post by ${author.name} (${author.pronouns}): ${post.body}`
		}
	];

	const comments_result = await db
		.select({ id: comments.id, body: comments.body, name: users.name })
		.from(comments)
		.leftJoin(users, eq(users.id, comments.user_id))
		.where(eq(comments.post_id, post.id));
	comments_result.forEach((comment) => {
		history.push({
			role: 'user',
			content: `Comment by ${comment.name}: ${comment.body}`
		});
	});

	const response = await completion(null, history);
	const result = await db.insert(comments).values({
		post_id: post.id,
		user_id: user.id,
		body: response
	});
	return json(
		await db.query.comments.findFirst({
			with: {
				user: { columns: { id: true, name: true, image_id: true } }
			},
			where: eq(comments.id, result.lastInsertRowid)
		})
	);
}
