import { beforeEach, describe, expect, it } from 'vitest';
import { db } from '$lib/server/db';
import { posts } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';
import { DELETE as deletePost, PATCH as patchPost } from '../routes/(app)/posts/[id]/+server';
import {
	cleanDatabase,
	createTestCreator,
	createTestUser,
	createTestPost,
	createEvent
} from './helpers';

describe('Posts API', () => {
	let creatorId: number;

	beforeEach(async () => {
		await cleanDatabase();
		const creator = await createTestCreator();
		creatorId = creator.id;
	});

	// "POST /posts - generate post for random user" moved to the FastAPI backend
	// (backend/tests/test_posts.py::test_generate_post_for_random_active_user) — see
	// BACKEND_MIGRATION.md.

	// "POST /users/[id]/posts - generate post for specific user" moved to the FastAPI backend
	// (backend/tests/test_users_profile.py::test_generate_post_for_specific_user) — see
	// BACKEND_MIGRATION.md.

	describe('DELETE /posts/[id] - delete post', () => {
		it('deletes a post and returns 204', async () => {
			const user = await createTestUser(creatorId);
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
			const user = await createTestUser(creatorId);
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
