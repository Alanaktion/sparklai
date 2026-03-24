import { beforeEach, describe, expect, it, vi } from 'vitest';
import { schema_completion } from '$lib/server/chat';
import { enqueueImageJob } from '$lib/server/sd/jobs';
import { db } from '$lib/server/db';
import { posts } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';
import { POST as generateRandomPost } from '../routes/(app)/posts/+server';
import { DELETE as deletePost, PATCH as patchPost } from '../routes/(app)/posts/[id]/+server';
import { POST as generateUserPost } from '../routes/(app)/users/[id]/posts/+server';
import {
	cleanDatabase,
	createTestUser,
	createTestPost,
	sampleAIPostResponse,
	sampleAIPostWithImageResponse,
	createEvent
} from './helpers';

describe('Posts API', () => {
	beforeEach(async () => {
		await cleanDatabase();
	});

	describe('POST /posts - generate post for random user', () => {
		it('returns 404 when no users exist', async () => {
			await expect(generateRandomPost()).rejects.toMatchObject({
				status: 404
			});
		});

		it('generates a post for a random AI user', async () => {
			const user = await createTestUser();
			vi.mocked(schema_completion).mockResolvedValueOnce(sampleAIPostResponse);

			const response = await generateRandomPost();

			expect(response.status).toBe(201);
			const body = await response.json();
			expect(body.post).toBeDefined();
			expect(body.post.body).toBe(sampleAIPostResponse.post_text);
			expect(body.post.user_id).toBe(user.id);
			expect(body.image_job).toBeNull();
		});

		it('generates a post with an image job when AI requests one', async () => {
			await createTestUser();
			vi.mocked(schema_completion).mockResolvedValueOnce(sampleAIPostWithImageResponse);

			const response = await generateRandomPost();

			expect(response.status).toBe(201);
			const body = await response.json();
			expect(body.post).toBeDefined();
			expect(body.image_job).not.toBeNull();
			expect(vi.mocked(enqueueImageJob)).toHaveBeenCalledOnce();
		});

		it('does not generate posts for human users', async () => {
			// Only create a human user - no AI users available
			await createTestUser({ is_human: true });

			await expect(generateRandomPost()).rejects.toMatchObject({
				status: 404
			});
		});
	});

	describe('POST /users/[id]/posts - generate post for specific user', () => {
		it('returns 404 for non-existent user', async () => {
			const event = {
				params: { id: '99999' },
				request: new Request('http://localhost/', { method: 'POST' })
			} as Parameters<typeof generateUserPost>[0];

			await expect(generateUserPost(event)).rejects.toMatchObject({
				status: 404
			});
		});

		it('generates a post for a specific user', async () => {
			const user = await createTestUser();
			vi.mocked(schema_completion).mockResolvedValueOnce(sampleAIPostResponse);

			const event = {
				params: { id: String(user.id) },
				request: new Request('http://localhost/', { method: 'POST' })
			} as Parameters<typeof generateUserPost>[0];

			const response = await generateUserPost(event);
			expect(response.status).toBe(200);
			const body = await response.json();
			expect(body.post.body).toBe(sampleAIPostResponse.post_text);
			expect(body.post.user_id).toBe(user.id);
		});

		it('passes a custom prompt when provided as form data', async () => {
			const user = await createTestUser();
			vi.mocked(schema_completion).mockResolvedValueOnce(sampleAIPostResponse);

			const fd = new FormData();
			fd.append('prompt', 'Write about a sunny day');
			const event = {
				params: { id: String(user.id) },
				request: new Request('http://localhost/', {
					method: 'POST',
					body: fd
				})
			} as Parameters<typeof generateUserPost>[0];

			await generateUserPost(event);

			// The generatePost function is called - verify schema_completion was invoked
			expect(vi.mocked(schema_completion)).toHaveBeenCalledOnce();
		});
	});

	describe('DELETE /posts/[id] - delete post', () => {
		it('deletes a post and returns 204', async () => {
			const user = await createTestUser();
			const post = await createTestPost(user.id);

			const event = createEvent({ id: String(post.id) });
			const response = await deletePost(event);

			expect(response.status).toBe(204);

			const remaining = await db.select().from(posts).where(eq(posts.id, post.id));
			expect(remaining).toHaveLength(0);
		});
	});

	describe('PATCH /posts/[id] - update post', () => {
		it('updates a post body', async () => {
			const user = await createTestUser();
			const post = await createTestPost(user.id, 'Original body');

			const event = {
				params: { id: String(post.id) },
				request: new Request('http://localhost/', {
					method: 'PATCH',
					body: JSON.stringify({ body: 'Updated body' }),
					headers: { 'Content-Type': 'application/json' }
				})
			} as Parameters<typeof patchPost>[0];

			const response = await patchPost(event);
			expect(response.status).toBe(200);

			// Verify in DB
			const updated = await db.query.posts.findFirst({ where: eq(posts.id, post.id) });
			expect(updated?.body).toBe('Updated body');
		});
	});
});
