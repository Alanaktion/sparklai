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

	return unique.slice(0, 8).join(', ');
}

function inferGenderExpressionFromPronouns(pronouns: string | null | undefined) {
	if (!pronouns) {
		return '';
	}

	const normalized = pronouns.trim().toLowerCase();
	if (normalized.startsWith('he/')) {
		return 'masculine, male';
	}
	if (normalized.startsWith('she/')) {
		return 'feminine, female';
	}
	if (normalized.startsWith('they/')) {
		return 'nonbinary';
	}

	return '';
}

function buildAppearanceTags(appearance: unknown, pronouns?: string | null) {
	if (!appearance || typeof appearance !== 'object') {
		return '';
	}

	const data = appearance as Record<string, unknown>;
	const tags: string[] = [];
	if (typeof data.gender_expression === 'string' && data.gender_expression.trim()) {
		tags.push(data.gender_expression.trim());
	} else {
		const inferredGenderExpression = inferGenderExpressionFromPronouns(pronouns);
		if (inferredGenderExpression) {
			tags.push(inferredGenderExpression);
		}
	}
	if (typeof data.body_type === 'string' && data.body_type.trim()) {
		tags.push(data.body_type.trim());
	}
	if (typeof data.skin_tone === 'string' && data.skin_tone.trim()) {
		tags.push(`${data.skin_tone.trim()} skin`);
	}
	if (typeof data.height === 'string' && data.height.trim()) {
		tags.push(data.height.trim());
	}
	if (data.hair && typeof data.hair === 'object') {
		const hair = data.hair as Record<string, unknown>;
		const hairColor = typeof hair.color === 'string' ? hair.color.trim() : '';
		const hairStyle = typeof hair.style === 'string' ? hair.style.trim() : '';
		if (hairColor || hairStyle) {
			tags.push(`${hairColor} ${hairStyle} hair`.trim());
		}
	}
	if (data.eyes && typeof data.eyes === 'object') {
		const eyes = data.eyes as Record<string, unknown>;
		if (typeof eyes.color === 'string' && eyes.color.trim()) {
			tags.push(`${eyes.color.trim()} eyes`);
		}
	}
	if (typeof data.clothing_style === 'string' && data.clothing_style.trim()) {
		tags.push(`wearing ${data.clothing_style.trim()} clothing`);
	} else {
		tags.push('fully clothed');
	}

	return normalizeGeneratedPrompt(tags.join(', '));
}

async function getScenarioContexts(user: {
	bio?: string | null;
	occupation?: string | null;
	interests?: string[] | string | null;
	location?: { city: string; state_province: string; country: string } | null;
}) {
	if (!user.bio || !user.bio.trim()) {
		return SCENARIO_CONTEXTS;
	}

	let scenarioPrompt = 'Generate 8 short profile photo scenario ideas for this person.';
	scenarioPrompt +=
		' Each line should be one concise scenario phrase like "at a weekend farmers market".';
	scenarioPrompt += " Keep them realistic and aligned to the person's bio and interests.";
	scenarioPrompt += `\nBio: ${user.bio}`;
	if (user.occupation) {
		scenarioPrompt += `\nOccupation: ${user.occupation}`;
	}
	if (user.interests) {
		const interests = Array.isArray(user.interests) ? user.interests.join(', ') : user.interests;
		scenarioPrompt += `\nInterests: ${interests}`;
	}
	if (user.location) {
		scenarioPrompt += `\nLocation: ${user.location.city}, ${user.location.state_province}, ${user.location.country}`;
	}
	scenarioPrompt += `\nExample scenario styles: ${SCENARIO_CONTEXTS.join('; ')}`;
	scenarioPrompt += '\n\nReturn only 8 lines, one scenario per line, no numbering.';

	const raw = await completion(scenarioPrompt);
	const scenarios = raw
		.split('\n')
		.map((line) => line.replace(/^[-*\d.)\s]+/, '').trim())
		.filter(Boolean)
		.slice(0, 8);

	return scenarios.length ? scenarios : SCENARIO_CONTEXTS;
}

const SCENARIO_CONTEXTS = [
	'at their workplace or during a professional activity',
	'outdoors pursuing a hobby or sport',
	'in a social setting with friends',
	'in a quiet personal moment at home or in a café',
	'traveling or exploring somewhere new',
	'during a creative or artistic pursuit',
	'on a city street or in an urban environment',
	'in nature — a forest, beach, or mountain setting'
];

function buildUserContext(user: {
	location?: { city: string; state_province: string; country: string } | null;
	occupation?: string | null;
	interests?: string | string[] | null;
	personality_traits?: unknown;
	backstory?: string | null;
	appearance?: unknown;
}) {
	let context = '';
	if (user.location) {
		context += `\nLocation: ${user.location.city}, ${user.location.state_province}, ${user.location.country}`;
	}
	if (user.occupation) {
		context += `\nOccupation: ${user.occupation}`;
	}
	if (user.interests) {
		const interests = Array.isArray(user.interests) ? user.interests.join(', ') : user.interests;
		context += `\nInterests: ${interests}`;
	}
	if (user.personality_traits) {
		context += `\nPersonality traits: ${JSON.stringify(user.personality_traits)}`;
	}
	if (user.backstory) {
		context += `\nBackstory: ${user.backstory}`;
	}
	if (user.appearance) {
		context += `\nAppearance: ${JSON.stringify(user.appearance)}`;
	}
	return context;
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
		const context = buildUserContext(user);
		const appearanceTags = buildAppearanceTags(user.appearance, user.pronouns);
		const scenarioContexts = await getScenarioContexts(user);
		const appearanceRequirement = appearanceTags
			? `\nAlways include these appearance traits in every prompt: ${appearanceTags}.`
			: '';

		if (count === 1) {
			const facet = scenarioContexts[Math.floor(Math.random() * scenarioContexts.length)];
			let llmPrompt = 'Generate a focused profile-image prompt as comma-separated keywords.';
			llmPrompt +=
				' Choose exactly one subject, one setting, and one activity that best represent this user.';
			llmPrompt +=
				' Do not include multiple alternatives. Keep it to 5-8 short keywords total, ordered:';
			llmPrompt +=
				' subject, setting, activity, 2-5 supporting visual details (appearance or style).';
			llmPrompt += `\nScenario focus: Show the person ${facet}.`;
			llmPrompt += appearanceRequirement;
			llmPrompt += context;
			llmPrompt += '\n\nReturn only the comma-separated keyword list. No prose.';

			const generated = normalizeGeneratedPrompt(await completion(llmPrompt));
			prompts = [
				appearanceTags ? normalizeGeneratedPrompt(`${appearanceTags}, ${generated}`) : generated
			];
		} else {
			const scenarioList = scenarioContexts.slice(0, Math.max(count + 2, 4)).join('; ');
			let llmPrompt = `Generate exactly ${count} distinct image prompts for the following person.`;
			llmPrompt += ` Each prompt is a comma-separated keyword list of 5-8 keywords.`;
			llmPrompt += ` Return them on separate lines, numbered "1.", "2.", etc.`;
			llmPrompt += ` Each prompt MUST depict a completely different setting, time of day, and activity — cover a variety of scenarios such as: ${scenarioList}.`;
			llmPrompt += ` Do not repeat settings, lighting conditions, or activities across prompts.`;
			llmPrompt += appearanceRequirement;
			llmPrompt += context;
			llmPrompt += `\n\nReturn only the numbered list of ${count} keyword prompts. No prose.`;

			const raw = await completion(llmPrompt);
			prompts = raw
				.split('\n')
				.map((line) => line.replace(/^\d+[.)]\s*/, '').trim())
				.filter(Boolean)
				.map((line) => normalizeGeneratedPrompt(line))
				.map((line) =>
					appearanceTags ? normalizeGeneratedPrompt(`${appearanceTags}, ${line}`) : line
				)
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
