import { db } from '$lib/server/db';
import {
	chats,
	comments,
	creators,
	imageGenerationJobs,
	images,
	media,
	posts,
	relationships,
	users
} from '$lib/server/db/schema';

/**
 * Deletes all rows from all tables in an order that respects foreign key
 * constraints (most dependent tables first).
 */
export async function cleanDatabase() {
	// Clear image references on users before deleting images (no onDelete cascade)
	await db.update(users).set({ image_id: null });
	await db.delete(chats);
	await db.delete(comments);
	await db.delete(imageGenerationJobs);
	await db.delete(posts);
	await db.delete(media);
	await db.delete(relationships);
	await db.delete(images);
	await db.delete(users);
	await db.delete(creators);
}

/** Sample user data for inserting into the database */
export const sampleUserData = {
	name: 'Test User',
	age: 25,
	pronouns: 'they/them',
	bio: 'A test user bio',
	location: { city: 'Test City', state_province: 'TC', country: 'Testland' },
	occupation: 'Software Tester',
	interests: ['testing', 'coding'],
	personality_traits:
		'Curious and methodical, they approach problems analytically and rarely act impulsively. They are reserved in groups but warm one-on-one, and take their commitments seriously.',
	relationship_status: 'single',
	writing_style:
		'Writes casually in English; uses minimal punctuation in informal messages but proper grammar in professional contexts. Very low emoji use.',
	backstory: 'A test backstory snippet',
	appearance:
		'Average build, around 170 cm. Short brown hair, brown eyes, and light skin. Usually wears plain t-shirts and jeans.'
};

/** Sample AI-generated user response from schema_completion('user') */
export const sampleAIUserResponse = {
	name: 'Alex Chen',
	age: 28,
	pronouns: 'she/her',
	bio: 'A software engineer who loves hiking and coffee',
	location: { city: 'Portland', state_province: 'OR', country: 'USA' },
	occupation: 'Software Engineer',
	interests: ['hiking', 'coffee', 'photography'],
	personality_traits:
		'Warm and outgoing, she makes friends easily and is genuinely curious about people. She is organized at work but spontaneous in her personal life, and handles stress well.',
	relationship_status: 'in a relationship',
	writing_style:
		'Writes in English; casual and conversational with a light use of exclamation points. Low emoji use, mostly in reaction to good news.',
	backstory: 'Grew up in Seattle, moved to Portland for work',
	appearance:
		'Slim build, around 165 cm, with straight black hair worn long. Dark brown almond-shaped eyes and light tan skin. Typically dresses in smart-casual layered outfits.'
};

/** Sample AI-generated post response from schema_completion('post') */
export const sampleAIPostResponse = {
	post_text: 'Just had the most amazing hike today! The views were breathtaking 🏔️',
	image_generation: null
};

/** Sample AI-generated post response with image generation */
export const sampleAIPostWithImageResponse = {
	post_text: 'Check out this beautiful sunset I captured! 📸',
	image_generation: {
		image_keywords: 'sunset, golden hour, mountains, photography',
		image_style: 'photo'
	}
};

/** Sample AI-generated post_image response from schema_completion('post_image') */
export const sampleAIPostImageResponse = {
	keywords: ['sunset', 'golden hour', 'mountains'],
	negative_keywords: null,
	aspect_ratio: 'square',
	image_style: 'photo'
};

/** Creates a test creator in the database and returns it */
export async function createTestCreator(overrides: Record<string, unknown> = {}) {
	const result = await db
		.insert(creators)
		.values({
			name: 'Test Creator',
			pronouns: 'they/them',
			password_hash: 'test:hash',
			...overrides
		})
		.returning();
	return result[0];
}

/** Creates a test user in the database and returns it */
export async function createTestUser(creatorId: number, overrides: Record<string, unknown> = {}) {
	const data = { ...sampleUserData, creator_id: creatorId, ...overrides };
	const result = await db
		.insert(users)
		.values(data as typeof sampleUserData & { creator_id: number })
		.returning();
	return result[0];
}

/** Creates a test post in the database and returns it */
export async function createTestPost(userId: number, body = 'A test post body') {
	const result = await db.insert(posts).values({ user_id: userId, body }).returning();
	return result[0];
}

/** Creates a test image in the database and returns it */
export async function createTestImage(userId: number) {
	const result = await db
		.insert(images)
		.values({
			user_id: userId,
			type: 'image/webp',
			data: Buffer.from('fake-image-data')
		})
		.returning();
	return result[0];
}

/** Creates a test media record in the database and returns it */
export async function createTestMedia(userId: number, type = 'audio/mpeg') {
	const result = await db
		.insert(media)
		.values({
			user_id: userId,
			type,
			data: Buffer.from('fake-media-data')
		})
		.returning();
	return result[0];
}

/** Creates a mock RequestEvent for testing route handlers */
export function createEvent(
	params: Record<string, string> = {},
	options: {
		method?: string;
		body?: string | null;
		headers?: Record<string, string>;
	} = {}
) {
	const request = new Request('http://localhost/', {
		method: options.method || 'GET',
		body: options.body !== undefined ? options.body : null,
		headers: options.headers || {}
	});

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	return { params, request } as any;
}

/** Creates a mock FormData request event */
export function createFormEvent(
	params: Record<string, string> = {},
	formData: Record<string, string> = {}
) {
	const fd = new FormData();
	for (const [key, value] of Object.entries(formData)) {
		fd.append(key, value);
	}
	const request = new Request('http://localhost/', {
		method: 'POST',
		body: fd
	});
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	return { params, request } as any;
}
