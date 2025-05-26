import { db } from '$lib/server/db';
import { chats } from '$lib/server/db/schema';
import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

// Get the current chat history
export async function GET({ params }) {
	return json(
		await db
			.select()
			.from(chats)
			.where(eq(chats.user_id, Number(params.id)))
	);
}

// Add a user message to the chat history
export async function POST({ params, request }) {
	const data = await request.formData();
	const message = data.get('message');
	if (message === null) {
		return new Response(null, { status: 400 });
	}
	const result = await db
		.insert(chats)
		.values({
			user_id: Number(params.id),
			role: 'user',
			body: message.toString()
		})
		.returning();
	return json(result[0]);
}
