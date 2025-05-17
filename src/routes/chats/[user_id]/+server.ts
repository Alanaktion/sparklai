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
			.where(eq(chats.user_id, Number(params.user_id)))
	);
}

// Add a user message to the chat history
export async function POST({ params, request }) {
	const data = await request.formData();
	const result = await db
		.insert(chats)
		.values({
			user_id: Number(params.user_id),
			role: 'user',
			body: data.get('message')?.toString()
		})
		.returning();
	return json(result[0]);
}
