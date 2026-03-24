import { beforeEach, describe, expect, it, vi } from 'vitest';
import { completion } from '$lib/server/chat';
import { db } from '$lib/server/db';
import { comments } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';
import { POST as addUserComment } from '../routes/(app)/posts/[id]/comments/+server';
import { POST as generateAIComment } from '../routes/(app)/posts/[id]/comments/respond/+server';
import { DELETE as deleteComment } from '../routes/(app)/posts/[id]/comments/[comment_id]/+server';
import { cleanDatabase, createTestUser, createTestPost } from './helpers';

describe('Comments API', () => {
	beforeEach(async () => {
		await cleanDatabase();
	});

	describe('POST /posts/[id]/comments - add human comment', () => {
		it('returns 400 when message is missing', async () => {
			const user = await createTestUser();
			const post = await createTestPost(user.id);

			const fd = new FormData(); // no 'message' field
			const event = {
				params: { id: String(post.id) },
				request: new Request('http://localhost/', { method: 'POST', body: fd })
			} as Parameters<typeof addUserComment>[0];

			const response = await addUserComment(event);
			expect(response.status).toBe(400);
		});

		it('creates a comment with the given message', async () => {
			const user = await createTestUser();
			const post = await createTestPost(user.id);

			const fd = new FormData();
			fd.append('message', 'This is my comment!');
			const event = {
				params: { id: String(post.id) },
				request: new Request('http://localhost/', { method: 'POST', body: fd })
			} as Parameters<typeof addUserComment>[0];

			const response = await addUserComment(event);
			expect(response.status).toBe(200);
			const body = await response.json();
			expect(body.body).toBe('This is my comment!');
			expect(body.post_id).toBe(post.id);
			expect(body.user_id).toBeNull(); // human comments have no user_id
		});

		it('returns the comment with user relation', async () => {
			const user = await createTestUser();
			const post = await createTestPost(user.id);

			const fd = new FormData();
			fd.append('message', 'Hello world');
			const event = {
				params: { id: String(post.id) },
				request: new Request('http://localhost/', { method: 'POST', body: fd })
			} as Parameters<typeof addUserComment>[0];

			const response = await addUserComment(event);
			const body = await response.json();
			expect(body).toHaveProperty('user');
			expect(body.user).toBeNull(); // no user for human comments
		});
	});

	describe('POST /posts/[id]/comments/respond - generate AI comment', () => {
		it('returns 404 when post does not exist', async () => {
			const event = {
				params: { id: '99999' },
				request: new Request('http://localhost/', {
					method: 'POST',
					body: JSON.stringify({}),
					headers: { 'Content-Type': 'application/json' }
				})
			} as Parameters<typeof generateAIComment>[0];

			await expect(generateAIComment(event)).rejects.toMatchObject({
				status: 404
			});
		});

		it('generates an AI comment on the post', async () => {
			const user = await createTestUser();
			const post = await createTestPost(user.id);
			vi.mocked(completion).mockResolvedValueOnce('Great post! I love it!');

			const event = {
				params: { id: String(post.id) },
				request: new Request('http://localhost/', {
					method: 'POST',
					body: JSON.stringify({}),
					headers: { 'Content-Type': 'application/json' }
				})
			} as Parameters<typeof generateAIComment>[0];

			const response = await generateAIComment(event);
			expect(response.status).toBe(200);
			const body = await response.json();
			expect(body.body).toBe('Great post! I love it!');
			expect(body.post_id).toBe(post.id);
			expect(body.user_id).toBe(user.id);
		});

		it('allows specifying a specific user for the comment', async () => {
			const author = await createTestUser({ name: 'Post Author' });
			const commenter = await createTestUser({ name: 'Commenter' });
			const post = await createTestPost(author.id);
			vi.mocked(completion).mockResolvedValueOnce('Nice one!');

			const event = {
				params: { id: String(post.id) },
				request: new Request('http://localhost/', {
					method: 'POST',
					body: JSON.stringify({ user_id: commenter.id }),
					headers: { 'Content-Type': 'application/json' }
				})
			} as Parameters<typeof generateAIComment>[0];

			const response = await generateAIComment(event);
			const body = await response.json();
			expect(body.user_id).toBe(commenter.id);
		});
	});

	describe('DELETE /posts/[id]/comments/[comment_id] - delete comment', () => {
		it('deletes a comment and returns 204', async () => {
			const user = await createTestUser();
			const post = await createTestPost(user.id);

			// Insert a comment directly
			const insertResult = await db.insert(comments).values({
				post_id: post.id,
				user_id: user.id,
				body: 'Comment to delete'
			});
			const commentId = Number(insertResult.lastInsertRowid);

			const event = {
				params: { id: String(post.id), comment_id: String(commentId) }
			} as Parameters<typeof deleteComment>[0];

			const response = await deleteComment(event);
			expect(response.status).toBe(204);

			// Verify deletion
			const remaining = await db.select().from(comments).where(eq(comments.id, commentId));
			expect(remaining).toHaveLength(0);
		});
	});
});
