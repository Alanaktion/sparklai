import { db } from '$lib/server/db';
import { images, users } from '$lib/server/db/schema';
import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { txt2img } from '$lib/server/sd/index.js';
import { completion } from '$lib/server/chat/index.js';

export async function POST({ params }) {
	const users_result = await db
		.select()
		.from(users)
		.where(eq(users.id, Number(params.id)));
	if (!users_result.length) {
		return new Response(null, { status: 404 });
	}
	const user = users_result[0];

	let prompt =
		"Write a brief list of keywords used to generate a profile image for the given user. Include generic keywords like 'brown hair', 'tall woman', etc.";
	if (user.location) {
		prompt += `\nLocation: ${user.location.city}, ${user.location.state_province}, ${user.location.country}`;
	}
	if (user.occupation) {
		prompt += `\nOccupation: ${user.occupation}`;
	}
	if (user.interests) {
		prompt += `\nInterests: ${user.interests}`;
	}
	if (user.personality_traits) {
		prompt += `\nPersonality traits: ${JSON.stringify(user.personality_traits)}`;
	}
	if (user.backstory_snippet) {
		prompt += `\nBackstory: ${user.backstory_snippet}`;
	}
	if (user.appearance) {
		prompt += `\nAppearance: ${JSON.stringify(user.appearance)}`;
	}

	prompt +=
		'\n\nSeparate keywords with commas. Ensure most important identifying traits are included. *Do not write any other content apart from a list of keywords for image generation!*';

	const response = await completion(prompt);

	const pic = await txt2img(response);
	const img_result = await db.insert(images).values({
		user_id: user.id,
		params: pic.params,
		data: pic.data
	});
	const img_id = img_result.lastInsertRowid;

	await db.update(users).set({ image_id: img_id }).where(eq(users.id, user.id));

	return json(img_id, { status: 201 });
}
