import { beforeEach, describe, expect, it, vi } from 'vitest';
import { completion } from '$lib/server/chat';
import { db } from '$lib/server/db';
import { chats } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';
import {
	GET as getChatMessages,
	POST as addChatMessage
} from '../routes/(app)/users/[id]/chat/messages/+server';
import { DELETE as deleteChatMessage } from '../routes/(app)/users/[id]/chat/messages/[message_id]/+server';
import { POST as generateChatResponse } from '../routes/(app)/users/[id]/chat/respond/+server';
import { cleanDatabase, createTestUser } from './helpers';

describe('Chat API', () => {
	beforeEach(async () => {
		await cleanDatabase();
	});

	describe('GET /users/[id]/chat/messages - get chat history', () => {
		it('returns empty array when no messages exist', async () => {
			const user = await createTestUser();

			const event = {
				params: { id: String(user.id) }
			} as Parameters<typeof getChatMessages>[0];

			const response = await getChatMessages(event);
			expect(response.status).toBe(200);
			const body = await response.json();
			expect(body).toEqual([]);
		});

		it('returns chat messages for the user', async () => {
			const user = await createTestUser();

			// Insert messages
			await db.insert(chats).values([
				{ user_id: user.id, role: 'user', body: 'Hello!' },
				{ user_id: user.id, role: 'assistant', body: 'Hi there!' }
			]);

			const event = {
				params: { id: String(user.id) }
			} as Parameters<typeof getChatMessages>[0];

			const response = await getChatMessages(event);
			const body = await response.json();
			expect(body).toHaveLength(2);
			expect(body[0].body).toBe('Hello!');
			expect(body[0].role).toBe('user');
			expect(body[1].body).toBe('Hi there!');
			expect(body[1].role).toBe('assistant');
		});
	});

	describe('POST /users/[id]/chat/messages - add user message', () => {
		it('returns 400 when message is missing', async () => {
			const user = await createTestUser();

			const fd = new FormData(); // no 'message' field
			const event = {
				params: { id: String(user.id) },
				request: new Request('http://localhost/', { method: 'POST', body: fd })
			} as Parameters<typeof addChatMessage>[0];

			const response = await addChatMessage(event);
			expect(response.status).toBe(400);
		});

		it('adds a user message to the chat', async () => {
			const user = await createTestUser();

			const fd = new FormData();
			fd.append('message', 'Hello, how are you?');
			const event = {
				params: { id: String(user.id) },
				request: new Request('http://localhost/', { method: 'POST', body: fd })
			} as Parameters<typeof addChatMessage>[0];

			const response = await addChatMessage(event);
			expect(response.status).toBe(200);
			const body = await response.json();
			expect(body.body).toBe('Hello, how are you?');
			expect(body.role).toBe('user');
			expect(body.user_id).toBe(user.id);
		});

		it('accepts an empty string message', async () => {
			const user = await createTestUser();

			const fd = new FormData();
			fd.append('message', '');
			const event = {
				params: { id: String(user.id) },
				request: new Request('http://localhost/', { method: 'POST', body: fd })
			} as Parameters<typeof addChatMessage>[0];

			const response = await addChatMessage(event);
			expect(response.status).toBe(200);
		});
	});

	describe('POST /users/[id]/chat/respond - generate AI response', () => {
		it('returns 404 when user does not exist', async () => {
			const event = {
				params: { id: '99999' }
			} as Parameters<typeof generateChatResponse>[0];

			await expect(generateChatResponse(event)).rejects.toMatchObject({
				status: 404
			});
		});

		it('generates an AI response and saves it', async () => {
			const user = await createTestUser();

			// Add a user message first
			await db.insert(chats).values({
				user_id: user.id,
				role: 'user',
				body: 'What do you enjoy doing?'
			});

			vi.mocked(completion).mockResolvedValueOnce('I love hiking and photography!');

			const event = {
				params: { id: String(user.id) }
			} as Parameters<typeof generateChatResponse>[0];

			const response = await generateChatResponse(event);
			expect(response.status).toBe(200);
			const body = await response.json();
			expect(body.body).toBe('I love hiking and photography!');
			expect(body.role).toBe('assistant');
			expect(body.user_id).toBe(user.id);
		});

		it('includes conversation history in the completion call', async () => {
			const user = await createTestUser();

			await db.insert(chats).values([
				{ user_id: user.id, role: 'user', body: 'First message' },
				{ user_id: user.id, role: 'assistant', body: 'First response' },
				{ user_id: user.id, role: 'user', body: 'Second message' }
			]);

			vi.mocked(completion).mockResolvedValueOnce('Second response');

			const event = {
				params: { id: String(user.id) }
			} as Parameters<typeof generateChatResponse>[0];

			await generateChatResponse(event);

			// completion should be called with message history
			expect(vi.mocked(completion)).toHaveBeenCalledOnce();
			const callArgs = vi.mocked(completion).mock.calls[0];
			const messages = callArgs[1];
			// System prompt + 3 chat messages
			expect(messages).toHaveLength(4);
		});
	});

	describe('DELETE /users/[id]/chat/messages/[message_id] - delete message', () => {
		it('deletes a chat message and returns 204', async () => {
			const user = await createTestUser();

			const insertResult = await db.insert(chats).values({
				user_id: user.id,
				role: 'user',
				body: 'Message to delete'
			});
			const messageId = Number(insertResult.lastInsertRowid);

			const event = {
				params: { id: String(user.id), message_id: String(messageId) }
			} as Parameters<typeof deleteChatMessage>[0];

			const response = await deleteChatMessage(event);
			expect(response.status).toBe(204);

			// Verify deletion
			const remaining = await db.select().from(chats).where(eq(chats.id, messageId));
			expect(remaining).toHaveLength(0);
		});
	});
});
