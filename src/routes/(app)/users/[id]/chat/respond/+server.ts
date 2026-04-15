import { partitionChatHistory } from '$lib/chat/conversations';
import type { LlamaMessage } from '$lib/server/chat/index.js';
import { completion } from '$lib/server/chat/index.js';
import { formatDate, nowStr } from '$lib';
import { db } from '$lib/server/db';
import { chats, relationships, users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { asc, eq } from 'drizzle-orm';

// Generate a new response to the conversation
export async function POST({ params, locals }) {
	const user = await db.query.users.findFirst({
		where: eq(users.id, Number(params.id))
	});
	if (!user) {
		return error(404, {
			message: 'Not found'
		});
	}

	// Get relationships for context
	const relationshipsData = await db
		.select({
			name: users.name,
			pronouns: users.pronouns,
			relationship_type: relationships.relationship_type,
			description: relationships.description
		})
		.from(relationships)
		.innerJoin(users, eq(relationships.related_user_id, users.id))
		.where(eq(relationships.user_id, Number(params.id)));

	let relationshipContext = '';
	if (relationshipsData.length > 0) {
		const relationshipsText = relationshipsData
			.map((r) => {
				let text = `${r.name} (${r.pronouns})`;
				if (r.relationship_type) {
					text += ` - ${r.relationship_type}`;
				}
				if (r.description) {
					text += `: ${r.description}`;
				}
				return text;
			})
			.join('; ');
		relationshipContext = `\nYour relationships: ${relationshipsText}`;
	}

	const interests = user.interests?.length ? user.interests.join(', ') : 'Unknown';
	const userLocation = user.location
		? [user.location.city, user.location.state_province, user.location.country]
				.filter(Boolean)
				.join(', ')
		: 'Unknown';

	const basePromptLines = [
		`You are ${user.name} (${user.pronouns}) in a private one-on-one chat.`,
		'Write exactly like a real person texting in Messenger or iMessage, not like an assistant.',
		'',
		'Character profile:',
		`- Name: ${user.name}`,
		`- Age: ${user.age}`,
		`- Pronouns: ${user.pronouns}`,
		`- Bio: ${user.bio || 'Unknown'}`,
		`- Backstory: ${user.backstory || 'Unknown'}`,
		`- Occupation: ${user.occupation || 'Unknown'}`,
		`- Location: ${userLocation}`,
		`- Relationship status: ${user.relationship_status || 'Unknown'}`,
		`- Interests: ${interests}`,
		`- Personality: ${user.personality_traits || 'Unknown'}`,
		`- Writing style: ${user.writing_style || 'Unknown'}`,
		relationshipContext ? relationshipContext.trim() : '- Known relationships: none listed',
		'',
		'Texting behavior rules (critical):',
		'- Sound human and in-the-moment. Keep replies grounded in this exact chat context.',
		'- Prefer short natural message lengths (often 1-3 sentences). Use longer replies only when needed.',
		'- Use casual rhythm, contractions, and imperfect phrasing when it fits this character.',
		'- Ask follow-up questions naturally when conversation momentum calls for it.',
		'- Do not over-explain or lecture. Avoid polished essay-like paragraphs.',
		'- Do not narrate actions or emotions in stage directions (no *smiles*, no roleplay tags).',
		'- Never mention being an AI, model, assistant, or following instructions.',
		'- Never include safety-policy meta commentary unless directly required by the user message.',
		'',
		'Output constraints:',
		'- Return only the next outgoing chat message body.',
		'- No prefixes like "Assistant:" and no quoted transcript wrappers.'
	];

	let systemPrompt = basePromptLines.join('\n');

	// Include creator context if available
	const creator = locals.creator;
	if (creator) {
		systemPrompt += `\n\nConversation partner details:`;
		systemPrompt += `\n- Name: ${creator.name}`;
		systemPrompt += `\n- Pronouns: ${creator.pronouns}`;
		if (creator.bio) systemPrompt += `\n- Bio: ${creator.bio}`;
		if (creator.occupation) systemPrompt += `\n- Occupation: ${creator.occupation}`;
		if (creator.interests && creator.interests.length > 0) {
			systemPrompt += `\n- Interests: ${creator.interests.join(', ')}`;
		}
		if (creator.location) {
			const locationParts = [
				creator.location.city,
				creator.location.state_province,
				creator.location.country
			].filter(Boolean);
			if (locationParts.length > 0) {
				systemPrompt += `\n- Location: ${locationParts.join(', ')}`;
			}
		}

		if (user.additional_prompt) {
			systemPrompt += `\n\nAdditional character guidance:\n${user.additional_prompt}`;
		}
	}

	systemPrompt +=
		'\n\nDo not include any roleplay metatext, just write the actual response.' +
		` It is ${nowStr()}.`;

	const history: LlamaMessage[] = [
		{
			role: 'system',
			content: systemPrompt
		}
	];

	const chatHistory = await db
		.select()
		.from(chats)
		.where(eq(chats.user_id, Number(params.id)))
		.orderBy(asc(chats.id));
	const { previousSummaries, activeMessages } = partitionChatHistory(chatHistory);

	if (previousSummaries.length) {
		history.push({
			role: 'system',
			content:
				'This is a new conversation. Earlier live messages are intentionally omitted. ' +
				'You may reference the summaries below for continuity, but respond as part of a fresh exchange unless the human brings up prior context.\n\n' +
				previousSummaries
					.map((summary, index) => `Earlier conversation ${index + 1}: ${summary}`)
					.join('\n\n')
		});
	}

	activeMessages.forEach((chat) => {
		history.push({
			role: chat.role,
			content: chat.body
		});
	});

	if (activeMessages.length) {
		const last = activeMessages[activeMessages.length - 1];
		if (last.created_at) {
			history[0].content += `\nThe last message was received ${formatDate(last.created_at)}.`;
		}
	} else if (previousSummaries.length) {
		history[0].content += '\nNo live messages have been exchanged yet in this new conversation.';
	}

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
