import { db } from '$lib/server/db';
import { images, users } from '$lib/server/db/schema';
import { json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';
import { txt2img } from '$lib/server/sd/index.js';
import { completion } from '$lib/server/chat/index.js';

export async function POST({ params, request }) {
	const users_result = await db
		.select()
		.from(users)
		.where(eq(users.id, Number(params.id)));
	if (!users_result.length) {
		return new Response(null, { status: 404 });
	}
	const user = users_result[0];

	let image_prompt: string | undefined = '';
	let set_user_image = false;
	if (request.headers.get('Content-Type')?.includes('form')) {
		const data = await request.formData();
		if (data.has('prompt')) {
			image_prompt = data.get('prompt')?.toString();
		}
	}
	if (image_prompt === '' || typeof image_prompt === 'undefined') {
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

		image_prompt = await completion(prompt);
		set_user_image = true;
	}

	const pic = await txt2img(image_prompt);
	const image_result = await db
		.insert(images)
		.values({
			user_id: user.id,
			params: pic.params,
			data: pic.data
		})
		.returning();
	const img = image_result[0];

	if (set_user_image) {
		await db.update(users).set({ image_id: img.id }).where(eq(users.id, user.id));
	}

	return json(img, { status: 201 });
}
