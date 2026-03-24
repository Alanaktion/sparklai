import { schema_completion } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { posts, users } from '$lib/server/db/schema';
import { enqueueImageJob } from '$lib/server/sd/jobs.js';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

export async function POST({ params }) {
	const posts_result = await db
		.select()
		.from(posts)
		.where(eq(posts.id, Number(params.id)));
	if (!posts_result.length) {
		return error(404, {
			message: 'Not found'
		});
	}
	const post = posts_result[0];
	const users_result = await db.select().from(users).where(eq(users.id, post.user_id));
	const user = users_result[0];

	let prompt = `Post body:\n${post.body}`;

	prompt += `\nPost author (${user.pronouns}):`;
	if (user.location) {
		prompt += `\nLocation: ${user.location.city}, ${user.location.state_province}, ${user.location.country}`;
	}
	if (user.interests) {
		prompt += `\nInterests: ${user.interests}`;
	}
	if (user.personality_traits) {
		prompt += `\nPersonality traits: ${JSON.stringify(user.personality_traits)}`;
	}
	if (user.appearance) {
		prompt += `\nAppearance: ${JSON.stringify(user.appearance)}`;
	}

	const response = await schema_completion('post_image', prompt);
	let negative_keywords: string | null = null;
	if (response.negative_keywords) {
		negative_keywords = response.negative_keywords.join(',');
	}
	let width = 512;
	let height = 512;
	if (response.aspect_ratio === 'portrait') {
		height = 640;
		width = 480;
	} else if (response.aspect_ratio === 'landscape') {
		height = 480;
		width = 640;
	}

	const image_style = response.image_style || 'photo';
	const job = await enqueueImageJob({
		user_id: user.id,
		post_id: post.id,
		target: 'post_image',
		prompt: response.keywords.join(','),
		negative_prompt: negative_keywords,
		width,
		height,
		include_default_prompt: true,
		image_style
	});

	return json(job, { status: 202 });
}
