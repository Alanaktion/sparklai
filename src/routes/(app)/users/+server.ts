import { schema_completion } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { relationships, users } from '$lib/server/db/schema';
import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

export async function POST({ request, locals }) {
	let prompt = 'Create a new user profile.';

	if (request.headers.get('Content-Type')?.includes('form')) {
		const data = await request.formData();
		if (data.has('prompt')) {
			prompt += '\n\n' + data.get('prompt');
		}
	} else {
		prompt += ' Do not duplicate an existing user!';
		const users_result = await db.select().from(users).where(eq(users.is_human, false));
		if (users_result.length) {
			const profiles: string[] = users_result.map(
				(user) => `- ${user.name} (${user.pronouns}): ${user.bio}`
			);
			prompt += `\nCurrent users are:\n${profiles.join('\n')}`;
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

	const newUser = insert_result[0];

	if (locals.humanUser && newUser) {
		await db.insert(relationships).values({
			user_id: locals.humanUser.id,
			related_user_id: newUser.id,
			relationship_type: 'follow'
		});
	}

	return json(newUser, { status: 201 });
}
