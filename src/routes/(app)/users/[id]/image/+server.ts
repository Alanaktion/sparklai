import { completion } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { images, users } from '$lib/server/db/schema';
import { toWebp } from '$lib/server/image-utils.js';
import { enqueueImageJob } from '$lib/server/sd/jobs.js';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10MB

export async function POST({ params, request }) {
	const user = await db.query.users.findFirst({
		where: eq(users.id, Number(params.id))
	});
	if (!user) {
		return error(404, {
			message: 'User not found'
		});
	}

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
			await db.update(users).set({ image_id: image.id }).where(eq(users.id, user.id));
			return json({ image }, { status: 201 });
		}
	}

	let aspect_ratio: string | undefined = 'square';
	let image_prompt: string | undefined = '';
	let set_user_image = false;
	if (request.headers.get('Content-Type')?.includes('form')) {
		const data = await request.formData();
		if (data.has('prompt')) {
			image_prompt = data.get('prompt')?.toString();
		}
		if (data.has('aspect')) {
			aspect_ratio = data.get('aspect')?.toString();
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
		if (user.backstory) {
			prompt += `\nBackstory: ${user.backstory}`;
		}
		if (user.appearance) {
			prompt += `\nAppearance: ${JSON.stringify(user.appearance)}`;
		}

		prompt +=
			'\n\nSeparate keywords with commas. Ensure most important identifying traits are included. *Do not write any other content apart from a list of keywords for image generation!*';

		image_prompt = await completion(prompt);
		set_user_image = true;
	}

	let width = 512;
	let height = 512;
	if (aspect_ratio === 'portrait') {
		height = 640;
		width = 480;
	} else if (aspect_ratio === 'landscape') {
		height = 480;
		width = 640;
	}

	const job = await enqueueImageJob({
		user_id: user.id,
		target: 'user_image',
		prompt: image_prompt,
		negative_prompt: null,
		width,
		height,
		include_default_prompt: true,
		image_style: 'photo',
		set_as_user_image: set_user_image
	});

	return json(job, { status: 202 });
}
