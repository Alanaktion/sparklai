import {
	buildConversationSummaryBody,
	formatConversationTranscript,
	partitionChatHistory
} from '$lib/chat/conversations';
import { completion, type LlamaMessage } from '$lib/server/chat';
import { db } from '$lib/server/db';
import { chats, users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { asc, eq } from 'drizzle-orm';

export async function POST({ params, locals }) {
	const userId = Number(params.id);
	const user = await db.query.users.findFirst({
		where: eq(users.id, userId)
	});

	if (!user) {
		return error(404, {
			message: 'Not found'
		});
	}

	const chatHistory = await db
		.select()
		.from(chats)
		.where(eq(chats.user_id, userId))
		.orderBy(asc(chats.id));

	const { activeMessages } = partitionChatHistory(chatHistory);
	if (activeMessages.length === 0) {
		return error(400, {
			message: 'No active conversation to summarize'
		});
	}

	let systemPrompt =
		`Summarize the completed IM conversation with ${user.name} for future continuity.\n` +
		'Write a concise summary in plain prose that captures personal facts, emotional tone, commitments, requests, and unresolved threads.\n' +
		'Do not write as dialogue, do not include speaker labels, and keep it under 120 words.\n' +
		'This summary will be used as the only context carried into a fresh conversation.';

	const creator = locals.creator;
	if (creator) {
		systemPrompt += `\nThe human chatting with them is ${creator.name}.`;
	}

	const summaryMessages: LlamaMessage[] = [
		{
			role: 'system',
			content: systemPrompt
		}
	];
	const summary = await completion(formatConversationTranscript(activeMessages), summaryMessages);

	const result = await db
		.insert(chats)
		.values({
			user_id: userId,
			role: 'system',
			body: buildConversationSummaryBody(summary)
		})
		.returning();

	return json(result[0]);
}
