import type { LlamaMessage } from '$lib/server/chat/index.js';
import { completion } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { chats, users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

// Generate a new response to the conversation
export async function POST({ params }) {
	const user = await db.query.users.findFirst({
		where: eq(users.id, Number(params.id))
	});
	if (!user) {
		return error(404, {
			message: 'Not found'
		});
	}

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
		.where(eq(chats.user_id, Number(params.id)));
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
			user_id: Number(params.id),
			role: 'assistant',
			body: response
		})
		.returning();
	return json(result[0]);
}
