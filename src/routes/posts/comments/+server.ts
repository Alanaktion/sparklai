import { generateComment } from '$lib/server';
import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { and, eq, sql } from 'drizzle-orm';

// Generate a comment on a random recent post
export async function POST({ params }) {
	const author = await db.query.users.findFirst({
		where: and(eq(users.is_active, true), eq(users.is_human, false)),
		orderBy: sql`random()`
	});
	if (!author) {
		return error(404, 'No Users Found');
	}

	const posts = await db.query.posts.findMany({
		limit: 10
	});
	const post = posts[Math.floor(Math.random() * posts.length)];

	const comment = await generateComment(author, post);
	return json(comment, { status: 201 });
}
