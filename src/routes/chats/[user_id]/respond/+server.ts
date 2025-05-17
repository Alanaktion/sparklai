import type { LlamaMessage } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { chats, users } from '$lib/server/db/schema';
import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { completion } from '$lib/server/chat/index.js';

// Generate a new response to the conversation
export async function POST({ params }) {
	const user_result = await db
		.select()
		.from(users)
		.where(eq(users.id, Number(params.user_id)));
	if (!user_result.length) {
		return new Response(null, { status: 404 });
	}

	const user = user_result[0];
	const history: LlamaMessage[] = [
		{
			role: 'system',
			content:
				`You are ${user.name} (${user.pronouns}), having an IM conversation.\n` +
				`Your bio: ${user.bio}\n` +
				`Writing style: ${JSON.stringify(user.writing_style)}\n` +
				'Do not include any roleplay metatext, just write the actual response.'
		}
	];

	const chat_result = await db
		.select()
		.from(chats)
		.where(eq(chats.user_id, Number(params.user_id)));
	chat_result.forEach((chat) => {
		history.push({
			role: chat.role,
			content: chat.body
		});
	});

	const response = await completion(null, history);
	const result = await db
		.insert(chats)
		.values({
			user_id: Number(params.user_id),
			role: 'assistant',
			body: response
		})
		.returning();
	return json(result[0]);
}
