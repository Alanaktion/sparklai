import { db } from '$lib/server/db';
import {
	chats,
	comments,
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
	personality_traits: {
		openness: 0.5,
		conscientiousness: 0.7,
		extraversion: 0.4,
		agreeableness: 0.6,
		neuroticism: 0.3
	},
	relationship_status: 'single',
	writing_style: {
		emoji_frequency: 0.1,
		formality: 'casual',
		punctuation_style: 'standard',
		slang_usage: 'minimal'
	},
	backstory_snippet: 'A test backstory snippet',
	appearance: {
		gender_expression: 'androgynous',
		body_type: 'average',
		hair: { color: 'brown', style: 'short' }
	}
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
	personality_traits: {
		openness: 0.8,
		conscientiousness: 0.7,
		extraversion: 0.5,
		agreeableness: 0.9,
		neuroticism: 0.2
	},
	relationship_status: 'in a relationship',
	writing_style: {
		emoji_frequency: 0.3,
		formality: 'casual',
		punctuation_style: 'standard',
		slang_usage: 'minimal'
	},
	backstory_snippet: 'Grew up in Seattle, moved to Portland for work',
	appearance: {
		gender_expression: 'feminine',
		body_type: 'slim',
		hair: { color: 'black', style: 'long' },
		eyes: { color: 'brown' }
	}
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

/** Creates a test user in the database and returns it */
export async function createTestUser(overrides: Record<string, unknown> = {}) {
	const data = { ...sampleUserData, ...overrides };
	const result = await db
		.insert(users)
		.values(data as typeof sampleUserData)
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
