import { db } from '$lib/server/db';
import { comments } from '$lib/server/db/schema';
import { json } from '@sveltejs/kit';

// Add a user comment to the post
export async function POST({ params, request }) {
	const data = await request.formData();
	const result = await db
		.insert(comments)
		.values({
			post_id: Number(params.id),
			user_id: null,
			body: data.get('message')?.toString()
		})
		.returning();
	return json({ user: null, comment: result[0] });
}
