import { beforeEach, describe, expect, it, vi } from 'vitest';
import { schema_completion, completion } from '$lib/server/chat';
import { enqueueImageJob } from '$lib/server/sd/jobs';
import { db } from '$lib/server/db';
import { images } from '$lib/server/db/schema';
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
	createTestUser,
	createTestPost,
	createTestImage,
	sampleAIPostImageResponse
} from './helpers';

describe('Images API', () => {
	beforeEach(async () => {
		await cleanDatabase();
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
			const user = await createTestUser();
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
			const user = await createTestUser();
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
			const user = await createTestUser();
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
			const user = await createTestUser();
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
				params: { id: '99999' }
			} as Parameters<typeof generatePostImage>[0];

			await expect(generatePostImage(event)).rejects.toMatchObject({
				status: 404
			});
		});

		it('enqueues an image generation job for the post', async () => {
			const user = await createTestUser();
			const post = await createTestPost(user.id, 'A beautiful sunset photo');
			vi.mocked(schema_completion).mockResolvedValueOnce(sampleAIPostImageResponse);

			const event = {
				params: { id: String(post.id) }
			} as Parameters<typeof generatePostImage>[0];

			const response = await generatePostImage(event);
			expect(response.status).toBe(202);
			expect(vi.mocked(enqueueImageJob)).toHaveBeenCalledOnce();

			const jobArgs = vi.mocked(enqueueImageJob).mock.calls[0][0];
			expect(jobArgs.post_id).toBe(post.id);
			expect(jobArgs.target).toBe('post_image');
		});
	});
});

describe('Models API', () => {
	beforeEach(async () => {
		await cleanDatabase();
	});

	describe('GET /models - list available models', () => {
		it('returns model listing including chat models', async () => {
			const response = await getModels();

			expect(response.status).toBe(200);
			const body = await response.json();
			expect(body).toHaveProperty('chat_models');
			expect(body).toHaveProperty('chat_model');
			expect(body).toHaveProperty('sd_backend');
			expect(body.chat_models).toEqual([{ id: 'test-model' }]);
			expect(body.chat_model).toBe('test-model');
		});
	});

	describe('POST /models - update model settings', () => {
		it('updates the chat model', async () => {
			const event = {
				request: new Request('http://localhost/', {
					method: 'POST',
					body: JSON.stringify({ chat_model: 'new-model' }),
					headers: { 'Content-Type': 'application/json' }
				})
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
			} as any;

			const response = await setModels(event);
			expect(response.status).toBe(200);
		});
	});
});
