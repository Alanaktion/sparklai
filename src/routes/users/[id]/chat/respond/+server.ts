import type { LlamaMessage } from '$lib/server/chat/index.js';
import { completion } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { chats, relationships, users } from '$lib/server/db/schema';
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

	// Fetch the human user's profile to provide context
	const humanProfile = await db.query.users.findFirst({
		where: eq(users.is_human, true)
	});

	let systemPrompt =
		`You are ${user.name} (${user.pronouns}), having an IM conversation.\n` +
		`Your bio: ${user.bio}\n` +
		`Writing style: ${JSON.stringify(user.writing_style)}\n` +
		relationshipContext;

	// Include human user context if available
	if (humanProfile) {
		systemPrompt += `\nYou're chatting with ${humanProfile.name} (${humanProfile.pronouns})`;
		if (humanProfile.bio) systemPrompt += `\nAbout them: ${humanProfile.bio}`;
		if (humanProfile.occupation) systemPrompt += `\nTheir occupation: ${humanProfile.occupation}`;
		if (humanProfile.interests && humanProfile.interests.length > 0) {
			systemPrompt += `\nTheir interests: ${humanProfile.interests.join(', ')}`;
		}
		if (humanProfile.location) {
			const locationParts = [
				humanProfile.location.city,
				humanProfile.location.state_province,
				humanProfile.location.country
			].filter(Boolean);
			if (locationParts.length > 0) {
				systemPrompt += `\nTheir location: ${locationParts.join(', ')}`;
			}
		}
	}

	systemPrompt += '\nDo not include any roleplay metatext, just write the actual response.';

	const history: LlamaMessage[] = [
		{
			role: 'system',
			content: systemPrompt
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
