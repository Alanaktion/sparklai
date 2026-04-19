import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
	completion,
	fetch_models as fetchChatModels,
	get_model as getChatModel,
	schema_completion
} from '$lib/server/chat';
import { enqueueImageJob } from '$lib/server/sd/jobs';
import {
	fetch_models as fetchSdModels,
	init as initSdModel,
	init_style as initSdStyle
} from '$lib/server/sd';
import { toWebp } from '$lib/server/image-utils';
import { db } from '$lib/server/db';
import { images, posts, users } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';
import {
	GET as getImage,
	PATCH as patchImage,
	DELETE as deleteImage
} from '../routes/(app)/images/[id]/+server';
import { POST as generateUserImage } from '../routes/(app)/users/[id]/image/+server';
import { POST as generatePostImage } from '../routes/(app)/posts/[id]/image/+server';
import { GET as getModels, POST as setModels } from '../routes/(app)/models/+server';
import {
	cleanDatabase,
	createTestCreator,
	createTestUser,
	createTestPost,
	createTestImage,
	sampleAIPostImageResponse
} from './helpers';

function createCookieJar(initial: Record<string, string> = {}) {
	const jar = new Map(Object.entries(initial));

	return {
		get: vi.fn((name: string) => jar.get(name)),
		set: vi.fn((name: string, value: string) => {
			jar.set(name, value);
		}),
		delete: vi.fn((name: string) => {
			jar.delete(name);
		})
	};
}

describe('Images API', () => {
	let creatorId: number;

	beforeEach(async () => {
		await cleanDatabase();
		const creator = await createTestCreator();
		creatorId = creator.id;
	});

	describe('GET /images/[id] - retrieve image', () => {
		it('returns 404 for non-existent image', async () => {
			const event = {
				params: { id: '99999' }
			} as Parameters<typeof getImage>[0];

			await expect(getImage(event)).rejects.toMatchObject({
				status: 404
			});
		});

		it('returns image data with correct content type', async () => {
			const user = await createTestUser(creatorId);
			const image = await createTestImage(user.id);

			const event = {
				params: { id: String(image.id) }
			} as Parameters<typeof getImage>[0];

			const response = await getImage(event);
			expect(response.status).toBe(200);
			expect(response.headers.get('Content-Type')).toBe('image/webp');

			const data = await response.arrayBuffer();
			expect(data.byteLength).toBeGreaterThan(0);
		});
	});

	describe('PATCH /images/[id] - update image metadata', () => {
		it('updates image blur field', async () => {
			const user = await createTestUser(creatorId);
			const image = await createTestImage(user.id);

			const event = {
				params: { id: String(image.id) },
				request: new Request('http://localhost/', {
					method: 'PATCH',
					body: JSON.stringify({ blur: true }),
					headers: { 'Content-Type': 'application/json' }
				})
			} as Parameters<typeof patchImage>[0];

			const response = await patchImage(event);
			expect(response.status).toBe(200);

			const updated = await db.query.images.findFirst({ where: eq(images.id, image.id) });
			expect(updated?.blur).toBe(true);
		});
	});

	describe('DELETE /images/[id] - delete image', () => {
		it('deletes an image and returns 204', async () => {
			const user = await createTestUser(creatorId);
			const image = await createTestImage(user.id);

			const event = {
				params: { id: String(image.id) }
			} as Parameters<typeof deleteImage>[0];

			const response = await deleteImage(event);
			expect(response.status).toBe(204);

			const remaining = await db.select().from(images).where(eq(images.id, image.id));
			expect(remaining).toHaveLength(0);
		});
	});

	describe('POST /users/[id]/image - generate user profile image', () => {
		it('returns 404 for non-existent user', async () => {
			const event = {
				params: { id: '99999' },
				request: new Request('http://localhost/', { method: 'POST' })
			} as Parameters<typeof generateUserImage>[0];

			await expect(generateUserImage(event)).rejects.toMatchObject({
				status: 404
			});
		});

		it('enqueues an image generation job when no prompt given', async () => {
			const user = await createTestUser(creatorId);
			vi.mocked(completion).mockResolvedValueOnce('brown hair, tall woman');

			const event = {
				params: { id: String(user.id) },
				request: new Request('http://localhost/', { method: 'POST' })
			} as Parameters<typeof generateUserImage>[0];

			const response = await generateUserImage(event);
			expect(response.status).toBe(202);
			expect(vi.mocked(enqueueImageJob)).toHaveBeenCalledOnce();
		});
	});

	describe('POST /posts/[id]/image - generate post image', () => {
		it('returns 404 for non-existent post', async () => {
			const event = {
				params: { id: '99999' },
				request: new Request('http://localhost/', { method: 'POST' })
			} as Parameters<typeof generatePostImage>[0];

			await expect(generatePostImage(event)).rejects.toMatchObject({
				status: 404
			});
		});

		it('enqueues an image generation job for the post', async () => {
			const user = await createTestUser(creatorId);
			const post = await createTestPost(user.id, 'A beautiful sunset photo');
			vi.mocked(schema_completion).mockResolvedValueOnce(sampleAIPostImageResponse);

			const event = {
				params: { id: String(post.id) },
				request: new Request('http://localhost/', { method: 'POST' })
			} as Parameters<typeof generatePostImage>[0];

			const response = await generatePostImage(event);
			expect(response.status).toBe(202);
			expect(vi.mocked(enqueueImageJob)).toHaveBeenCalledOnce();

			const jobArgs = vi.mocked(enqueueImageJob).mock.calls[0][0];
			expect(jobArgs.post_id).toBe(post.id);
			expect(jobArgs.target).toBe('post_image');
		});
	});

	describe('POST /users/[id]/image - upload user profile image', () => {
		it('stores uploaded file as WebP and sets as user profile image', async () => {
			const user = await createTestUser(creatorId);
			const fakeImageData = Buffer.from('fake-image-data');
			const formData = new FormData();
			formData.append('file', new File([fakeImageData], 'photo.jpg', { type: 'image/jpeg' }));

			const event = {
				params: { id: String(user.id) },
				request: new Request('http://localhost/', {
					method: 'POST',
					body: formData
				})
			} as Parameters<typeof generateUserImage>[0];

			const response = await generateUserImage(event);
			expect(response.status).toBe(201);
			expect(vi.mocked(toWebp)).toHaveBeenCalledOnce();

			const body = await response.json();
			expect(body.image).toBeDefined();
			expect(body.image.id).toBeTypeOf('number');

			const updatedUser = await db.query.users.findFirst({ where: eq(users.id, user.id) });
			expect(updatedUser?.image_id).toBe(body.image.id);

			const storedImage = await db.query.images.findFirst({
				where: eq(images.id, body.image.id)
			});
			expect(storedImage).toBeDefined();
			expect(storedImage?.user_id).toBe(user.id);
		});
	});

	describe('POST /posts/[id]/image - upload post image', () => {
		it('stores uploaded file as WebP and sets as post image', async () => {
			const user = await createTestUser(creatorId);
			const post = await createTestPost(user.id, 'A test post');
			const fakeImageData = Buffer.from('fake-image-data');
			const formData = new FormData();
			formData.append('file', new File([fakeImageData], 'photo.jpg', { type: 'image/jpeg' }));

			const event = {
				params: { id: String(post.id) },
				request: new Request('http://localhost/', {
					method: 'POST',
					body: formData
				})
			} as Parameters<typeof generatePostImage>[0];

			const response = await generatePostImage(event);
			expect(response.status).toBe(201);
			expect(vi.mocked(toWebp)).toHaveBeenCalledOnce();

			const body = await response.json();
			expect(body.image).toBeDefined();
			expect(body.image.id).toBeTypeOf('number');

			const updatedPost = await db.query.posts.findFirst({ where: eq(posts.id, post.id) });
			expect(updatedPost?.image_id).toBe(body.image.id);

			const storedImage = await db.query.images.findFirst({
				where: eq(images.id, body.image.id)
			});
			expect(storedImage).toBeDefined();
			expect(storedImage?.user_id).toBe(user.id);
		});
	});
});

describe('Models API', () => {
	beforeEach(async () => {
		await cleanDatabase();
	});

	describe('GET /models - list available models', () => {
		it('returns model listing including chat models', async () => {
			const response = await getModels({
				cookies: createCookieJar()
			} as unknown as Parameters<typeof getModels>[0]);

			expect(response.status).toBe(200);
			const body = await response.json();
			expect(body).toHaveProperty('chat_models');
			expect(body).toHaveProperty('chat_model');
			expect(body).toHaveProperty('sd_backend');
			expect(body).toHaveProperty('sd_styles');
			expect(body.chat_models).toEqual([{ id: 'test-model' }]);
			expect(body.chat_model).toBe('test-model');
			expect(body.sd_styles).toContain('sdxl');
		});

		it('prefers valid cookie selections for the active session', async () => {
			vi.mocked(fetchChatModels).mockResolvedValueOnce([{ id: 'test-model' }, { id: 'alt-model' }]);
			vi.mocked(getChatModel).mockResolvedValueOnce('test-model');
			vi.mocked(fetchSdModels).mockResolvedValueOnce([
				{ model_name: 'test-photo', title: 'Test Photo' },
				{ model_name: 'test-sdxl', title: 'Test SDXL' }
			]);

			const response = await getModels({
				cookies: createCookieJar({
					chat_model: 'alt-model',
					sd_style: 'sdxl',
					sd_model: 'test-sdxl'
				})
			} as unknown as Parameters<typeof getModels>[0]);

			const body = await response.json();
			expect(body.chat_model).toBe('alt-model');
			expect(body.sd_style).toBe('sdxl');
			expect(body.sd_model).toBe('test-sdxl');
		});
	});

	describe('POST /models - update model settings', () => {
		it('stores selections in session cookies and updates the backend state', async () => {
			vi.mocked(fetchChatModels).mockResolvedValueOnce([{ id: 'test-model' }, { id: 'new-model' }]);
			vi.mocked(getChatModel).mockResolvedValueOnce('new-model');
			vi.mocked(fetchSdModels).mockResolvedValueOnce([
				{ model_name: 'test-photo', title: 'Test Photo' },
				{ model_name: 'test-sdxl', title: 'Test SDXL' }
			]);
			const cookies = createCookieJar();
			const event = {
				cookies,
				request: new Request('http://localhost/', {
					method: 'POST',
					body: JSON.stringify({ chat_model: 'new-model', sd_style: 'sdxl' }),
					headers: { 'Content-Type': 'application/json' }
				})
			} as unknown as Parameters<typeof setModels>[0];

			const response = await setModels(event);
			expect(response.status).toBe(200);
			expect(cookies.set).toHaveBeenCalledWith(
				'chat_model',
				'new-model',
				expect.objectContaining({ path: '/' })
			);
			expect(cookies.set).toHaveBeenCalledWith(
				'sd_style',
				'sdxl',
				expect.objectContaining({ path: '/' })
			);
			expect(cookies.delete).toHaveBeenCalledWith('sd_model', { path: '/' });
			expect(vi.mocked(initSdStyle)).toHaveBeenCalledWith('sdxl');
		});

		it('stores manual model overrides separately from style selection', async () => {
			vi.mocked(fetchSdModels).mockResolvedValueOnce([
				{ model_name: 'test-photo', title: 'Test Photo' },
				{ model_name: 'custom-xl', title: 'Custom XL' }
			]);
			const cookies = createCookieJar({ chat_model: 'test-model', sd_style: 'sdxl' });

			const response = await setModels({
				cookies,
				request: new Request('http://localhost/', {
					method: 'POST',
					body: JSON.stringify({ chat_model: 'test-model', sd_model: 'custom-xl' }),
					headers: { 'Content-Type': 'application/json' }
				})
			} as unknown as Parameters<typeof setModels>[0]);

			expect(response.status).toBe(200);
			expect(cookies.set).toHaveBeenCalledWith(
				'sd_model',
				'custom-xl',
				expect.objectContaining({ path: '/' })
			);
			expect(vi.mocked(initSdModel)).toHaveBeenCalledWith('custom-xl');
		});
	});
});
