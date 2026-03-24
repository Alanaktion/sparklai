import { schema_completion } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { images, posts, users } from '$lib/server/db/schema';
import { toWebp } from '$lib/server/image-utils.js';
import { enqueueImageJob } from '$lib/server/sd/jobs.js';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10MB

export async function POST({ params, request }) {
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

	if (request.headers.get('Content-Type')?.includes('multipart/form-data')) {
		const data = await request.formData();
		const file = data.get('file');
		if (file instanceof File) {
			if (file.size > MAX_UPLOAD_BYTES) {
				return error(413, { message: 'File too large (max 10MB)' });
			}
			const arrayBuffer = await file.arrayBuffer();
			let webpData: Buffer;
			try {
				webpData = await toWebp(Buffer.from(arrayBuffer));
			} catch {
				return error(400, { message: 'Invalid image file' });
			}
			const inserted = await db
				.insert(images)
				.values({ user_id: user.id, data: webpData })
				.returning();
			const image = inserted[0];
			await db.update(posts).set({ image_id: image.id }).where(eq(posts.id, post.id));
			return json({ image }, { status: 201 });
		}
	}

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
