export type ConversationHistoryMessage = {
	role: 'user' | 'assistant' | 'system';
	body: string;
	created_at?: string | null;
};

export type ActiveConversationMessage = ConversationHistoryMessage & {
	role: 'user' | 'assistant';
};

export const CONVERSATION_SUMMARY_PREFIX = 'Previous conversation summary:\n';

export function isConversationSummaryMessage(
	chat: Pick<ConversationHistoryMessage, 'role' | 'body'>
) {
	return chat.role === 'system' && chat.body.startsWith(CONVERSATION_SUMMARY_PREFIX);
}

export function buildConversationSummaryBody(summary: string) {
	return `${CONVERSATION_SUMMARY_PREFIX}${summary.trim()}`;
}

export function extractConversationSummary(body: string) {
	if (!body.startsWith(CONVERSATION_SUMMARY_PREFIX)) {
		return body.trim();
	}

	return body.slice(CONVERSATION_SUMMARY_PREFIX.length).trim();
}

export function partitionChatHistory(chatHistory: ConversationHistoryMessage[]) {
	const previousSummaries: string[] = [];
	let activeMessages: ActiveConversationMessage[] = [];

	for (const chat of chatHistory) {
		if (isConversationSummaryMessage(chat)) {
			previousSummaries.push(extractConversationSummary(chat.body));
			activeMessages = [];
			continue;
		}

		if (chat.role === 'user' || chat.role === 'assistant') {
			activeMessages.push({
				...chat,
				role: chat.role
			});
		}
	}

	return { previousSummaries, activeMessages };
}

export function hasActiveConversation(chatHistory: ConversationHistoryMessage[]) {
	return partitionChatHistory(chatHistory).activeMessages.length > 0;
}

export function formatConversationTranscript(chatHistory: ConversationHistoryMessage[]) {
	return chatHistory
		.filter(
			(chat): chat is ActiveConversationMessage => chat.role === 'user' || chat.role === 'assistant'
		)
		.map((chat) => `${chat.role === 'user' ? 'Human' : 'Assistant'}: ${chat.body}`)
		.join('\n');
}
