import { generatePost } from '$lib/server';
import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { and, eq, sql } from 'drizzle-orm';

// Generate a post for a random user
export async function POST() {
	const author = await db.query.users.findFirst({
		where: and(eq(users.is_active, true), eq(users.is_human, false)),
		orderBy: sql`random()`
	});
	if (!author) {
		return error(404, 'No Users Found');
	}
	const result = await generatePost(author);
	return json(result, { status: 201 });
}
