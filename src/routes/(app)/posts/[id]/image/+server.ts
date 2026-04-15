import { schema_completion } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { images, posts, users } from '$lib/server/db/schema';
import { toWebp } from '$lib/server/image-utils.js';
import { enqueueImageJob } from '$lib/server/sd/jobs.js';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10MB

function buildPostImagePrompt(
	postBody: string,
	user: {
		name: string;
		age: number;
		pronouns: string;
		bio?: string | null;
		backstory?: string | null;
		occupation?: string | null;
		interests?: string[] | string | null;
		location?: { city: string; state_province: string; country: string } | null;
		personality_traits?: string | null;
		appearance?: string | null;
	}
) {
	const lines: string[] = [
		'Generate an image concept for a social media post.',
		'Be creative, but keep it believable for this person and this post.',
		'Choose a specific moment (setting + activity + mood + lighting) that feels naturally implied by the post text.',
		'Avoid generic stock-photo compositions unless the post itself suggests one.',
		'If the image features the post author, extract the relevant physical descriptors from their appearance description and include them as keywords — hair color and style, eye color, skin tone, body type, clothing style, etc.',
		'',
		`Post body: ${postBody}`,
		'',
		'Author profile:'
	];

	lines.push(`- Name: ${user.name}, age ${user.age} (${user.pronouns})`);
	if (user.bio) lines.push(`- Bio: ${user.bio}`);
	if (user.backstory) lines.push(`- Backstory: ${user.backstory}`);
	if (user.occupation) lines.push(`- Occupation: ${user.occupation}`);
	if (user.location) {
		const location = [user.location.city, user.location.state_province, user.location.country]
			.filter(Boolean)
			.join(', ');
		lines.push(`- Location: ${location}`);
	}
	if (user.interests) {
		const interests = Array.isArray(user.interests) ? user.interests.join(', ') : user.interests;
		lines.push(`- Interests: ${interests}`);
	}
	if (user.personality_traits) lines.push(`- Personality: ${user.personality_traits}`);
	if (user.appearance) lines.push(`- Appearance: ${user.appearance}`);

	lines.push('');
	lines.push('Return data that best fits this specific character, not a generic influencer style.');

	return lines.join('\n');
}

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

	const prompt = buildPostImagePrompt(post.body, user);

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
