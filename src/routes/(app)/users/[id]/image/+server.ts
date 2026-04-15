import { completion } from '$lib/server/chat/index.js';
import { db } from '$lib/server/db';
import { images, users } from '$lib/server/db/schema';
import { toWebp } from '$lib/server/image-utils.js';
import { enqueueImageJob } from '$lib/server/sd/jobs.js';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10MB

function splitPromptKeywords(raw: string) {
	return raw
		.replace(/[\n|;]+/g, ',')
		.split(',')
		.map((part) => part.trim())
		.filter((part) => part.length > 0);
}

function normalizeGeneratedPrompt(raw: string) {
	const normalized = splitPromptKeywords(raw);

	const seen = new Set<string>();
	const unique: string[] = [];
	for (const part of normalized) {
		const key = part.toLowerCase();
		if (seen.has(key)) {
			continue;
		}
		seen.add(key);
		unique.push(part);
	}

	if (!unique.length) {
		return raw.trim();
	}

	return unique.slice(0, 12).join(', ');
}

function buildUserProfile(user: {
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
}): string {
	const lines: string[] = [`Name: ${user.name}, age ${user.age} (${user.pronouns})`];
	if (user.bio) lines.push(`Bio: ${user.bio}`);
	if (user.backstory) lines.push(`Backstory: ${user.backstory}`);
	if (user.occupation) lines.push(`Occupation: ${user.occupation}`);
	if (user.location) {
		const loc = [user.location.city, user.location.state_province, user.location.country]
			.filter(Boolean)
			.join(', ');
		lines.push(`Location: ${loc}`);
	}
	if (user.interests) {
		const interests = Array.isArray(user.interests) ? user.interests.join(', ') : user.interests;
		lines.push(`Interests: ${interests}`);
	}
	if (user.personality_traits) lines.push(`Personality: ${user.personality_traits}`);
	if (user.appearance) lines.push(`Appearance: ${user.appearance}`);
	return lines.join('\n');
}

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

	let aspect_ratio = 'square';
	let image_prompt = '';
	let count = 1;
	if (request.headers.get('Content-Type')?.includes('form')) {
		const data = await request.formData();
		image_prompt = data.get('prompt')?.toString() ?? '';
		aspect_ratio = data.get('aspect')?.toString() ?? 'square';
		count = Math.min(5, Math.max(1, parseInt(data.get('count')?.toString() ?? '1', 10) || 1));
	}

	const set_user_image = image_prompt === '';
	let prompts: string[];

	if (image_prompt === '') {
		const profile = buildUserProfile(user);
		if (count === 1) {
			const llmPrompt =
				'Generate a Stable Diffusion image prompt for a natural-looking profile photo of this person.\n' +
				'Choose an authentic setting and activity that genuinely reflects their personality, interests, and lifestyle.\n' +
				'Extract the specific appearance details from their description — hair color and style, eye color, skin tone, body type, clothing style, distinctive features — and include them as the first keywords so the generated image accurately depicts how this person actually looks.\n' +
				'Return a comma-separated keyword list of 8-12 items ordered: appearance details first, then setting and activity, then mood and lighting.\n' +
				'No prose, no numbering — just the keyword list.\n\n' +
				profile;
			prompts = [normalizeGeneratedPrompt(await completion(llmPrompt))];
		} else {
			const llmPrompt =
				`Generate exactly ${count} distinct Stable Diffusion image prompts for profile photos of this person.\n` +
				'Each should depict a completely different setting, activity, and mood — draw from a variety of real moments in their life.\n' +
				'Every prompt must include the same core appearance keywords (hair, eye color, skin tone, body type) so the person looks consistent across all photos — vary only the setting, activity, and mood.\n' +
				'Format: one comma-separated keyword list per line, numbered "1.", "2.", etc. Each list: 8-12 keywords. No prose beyond the numbered format.\n\n' +
				profile;
			const raw = await completion(llmPrompt);
			prompts = raw
				.split('\n')
				.map((line) => line.replace(/^\d+[.)]\s*/, '').trim())
				.filter(Boolean)
				.map((line) => normalizeGeneratedPrompt(line))
				.filter(Boolean)
				.slice(0, count);
			while (prompts.length < count) {
				prompts.push(prompts[0] ?? 'portrait photo');
			}
		}
	} else {
		prompts = Array.from({ length: count }, () => image_prompt);
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

	const jobs = await Promise.all(
		prompts.map((p) =>
			enqueueImageJob({
				user_id: user.id,
				target: 'user_image',
				prompt: p,
				negative_prompt: null,
				width,
				height,
				include_default_prompt: true,
				image_style: 'photo',
				set_as_user_image: set_user_image
			})
		)
	);

	return json(jobs, { status: 202 });
}
