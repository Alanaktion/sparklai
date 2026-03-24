import { db } from '$lib/server/db';
import { comments } from '$lib/server/db/schema';
import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

// Add a user comment to the post
export async function POST({ params, request }) {
	const data = await request.formData();
	const message = data.get('message');
	if (!message) {
		return new Response(null, { status: 400 });
	}
	const result = await db.insert(comments).values({
		post_id: Number(params.id),
		user_id: null,
		body: message.toString()
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
