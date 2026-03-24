import { schema_completion } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

export async function POST({ request }) {
	const users_result = await db.select().from(users).where(eq(users.is_human, 0));

	let prompt = 'Create a new user profile. Do not duplicate an existing user!';
	if (users_result.length) {
		const profiles: string[] = users_result.map(
			(user) => `- ${user.name} (${user.pronouns}): ${user.bio}`
		);
		prompt += `\nCurrent users are:\n${profiles.join('\n')}`;
	}

	if (request.headers.get('Content-Type')?.includes('form')) {
		const data = await request.formData();
		if (data.has('prompt')) {
			prompt += '\n\n' + data.get('prompt');
		}
	}

	const response = await schema_completion('user', prompt);
	const insert_result = await db
		.insert(users)
		.values({
			name: response.name,
			age: response.age,
			pronouns: response.pronouns,
			bio: response.bio,
			location: response.location,
			occupation: response.occupation,
			interests: response.interests,
			personality_traits: response.personality_traits,
			relationship_status: response.relationship_status,
			writing_style: response.writing_style,
			appearance: response.appearance,
			backstory_snippet: response.backstory_snippet
		})
		.returning();

	return json(insert_result[0], { status: 201 });
}
