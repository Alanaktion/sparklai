import { beforeEach, describe, expect, it, vi } from 'vitest';
import { schema_completion } from '$lib/server/chat';
import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';
import { POST as createUser } from '../routes/(app)/users/+server';
import { DELETE as deleteUser, PATCH as patchUser } from '../routes/(app)/users/[id]/+server';
import {
	cleanDatabase,
	createTestCreator,
	createTestUser,
	sampleAIUserResponse,
	createFormEvent,
	createEvent
} from './helpers';

describe('Users API', () => {
	let creatorId: number;

	beforeEach(async () => {
		await cleanDatabase();
		const creator = await createTestCreator();
		creatorId = creator.id;
	});

	describe('POST /users - create AI user', () => {
		it('creates a new user with AI-generated profile', async () => {
			vi.mocked(schema_completion).mockResolvedValueOnce(sampleAIUserResponse);

			const event = { ...createFormEvent(), locals: { creator: { id: creatorId } } } as Parameters<
				typeof createUser
			>[0];
			const response = await createUser(event);

			expect(response.status).toBe(201);
			const body = await response.json();
			expect(body.name).toBe(sampleAIUserResponse.name);
			expect(body.age).toBe(sampleAIUserResponse.age);
			expect(body.pronouns).toBe(sampleAIUserResponse.pronouns);
			expect(body.bio).toBe(sampleAIUserResponse.bio);
			expect(body.id).toBeDefined();
			expect(body.creator_id).toBe(creatorId);
		});

		it('includes existing user names when no custom prompt is provided', async () => {
			// Create an existing user first
			await createTestUser(creatorId, { name: 'Existing User' });

			vi.mocked(schema_completion).mockResolvedValueOnce(sampleAIUserResponse);

			const event = {
				...createEvent({}, { method: 'POST' }),
				locals: { creator: { id: creatorId } }
			} as Parameters<typeof createUser>[0];
			await createUser(event);

			// Verify schema_completion was called with a prompt mentioning existing users
			const callArgs = vi.mocked(schema_completion).mock.calls[0];
			expect(callArgs[1]).toContain('Existing User');
			expect(callArgs[1]).toContain('Current users are:');
		});

		it('uses custom prompt directly without existing user exclusion info', async () => {
			await createTestUser(creatorId, { name: 'Existing User' });

			vi.mocked(schema_completion).mockResolvedValueOnce(sampleAIUserResponse);

			const event = {
				...createFormEvent({}, { prompt: 'Make the user a teacher' }),
				locals: { creator: { id: creatorId } }
			} as Parameters<typeof createUser>[0];
			await createUser(event);

			const callArgs = vi.mocked(schema_completion).mock.calls[0];
			expect(callArgs[1]).toContain('Make the user a teacher');
			expect(callArgs[1]).not.toContain('Existing User');
			expect(callArgs[1]).not.toContain('Current users are:');
		});
	});

	describe('PATCH /users/[id] - update user', () => {
		it('updates user fields', async () => {
			const user = await createTestUser(creatorId);

			const event = {
				params: { id: String(user.id) },
				request: new Request('http://localhost/', {
					method: 'PATCH',
					body: JSON.stringify({ bio: 'Updated bio' }),
					headers: { 'Content-Type': 'application/json' }
				})
			} as Parameters<typeof patchUser>[0];

			const response = await patchUser(event);
			expect(response.status).toBe(200);
			const updated = await response.json();
			expect(updated.bio).toBe('Updated bio');
		});

		it('returns the updated user', async () => {
			const user = await createTestUser(creatorId);

			const event = {
				params: { id: String(user.id) },
				request: new Request('http://localhost/', {
					method: 'PATCH',
					body: JSON.stringify({ name: 'New Name', age: 30 }),
					headers: { 'Content-Type': 'application/json' }
				})
			} as Parameters<typeof patchUser>[0];

			const response = await patchUser(event);
			const updated = await response.json();
			expect(updated.name).toBe('New Name');
			expect(updated.age).toBe(30);
		});
	});

	describe('DELETE /users/[id] - delete user', () => {
		it('deletes the user and returns 204', async () => {
			const user = await createTestUser(creatorId);

			// Verify user exists
			const before = await db.select().from(users).where(eq(users.id, user.id));
			expect(before).toHaveLength(1);

			const event = createEvent({ id: String(user.id) });
			const response = await deleteUser(event);

			expect(response.status).toBe(204);

			// Verify user is deleted
			const after = await db.select().from(users).where(eq(users.id, user.id));
			expect(after).toHaveLength(0);
		});

		it('deletes the correct user (not other users)', async () => {
			const user1 = await createTestUser(creatorId, { name: 'User One' });
			const user2 = await createTestUser(creatorId, { name: 'User Two' });

			const event = createEvent({ id: String(user1.id) });
			await deleteUser(event);

			// user1 should be deleted
			const user1After = await db.select().from(users).where(eq(users.id, user1.id));
			expect(user1After).toHaveLength(0);

			// user2 should still exist
			const user2After = await db.select().from(users).where(eq(users.id, user2.id));
			expect(user2After).toHaveLength(1);
		});
	});
});
