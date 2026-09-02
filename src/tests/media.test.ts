import { beforeEach, describe, expect, it } from 'vitest';
import { db } from '$lib/server/db';
import { media, posts } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';
import { POST as uploadPostMedia } from '../routes/(app)/posts/[id]/media/+server';
import { cleanDatabase, createTestCreator, createTestPost, createTestUser } from './helpers';

describe('Media API', () => {
	let creatorId: number;

	beforeEach(async () => {
		await cleanDatabase();
		const creator = await createTestCreator();
		creatorId = creator.id;
	});

	// "GET /media/[id]" moved to the FastAPI backend (backend/tests/test_images_media.py) — see
	// BACKEND_MIGRATION.md.

	describe('POST /posts/[id]/media - upload post media', () => {
		it('stores uploaded audio file and sets as post media', async () => {
			const user = await createTestUser(creatorId);
			const post = await createTestPost(user.id, 'A test post');
			const fakeAudioData = Buffer.from('fake-audio-data');
			const formData = new FormData();
			formData.append('file', new File([fakeAudioData], 'sample.mp3', { type: 'audio/mpeg' }));

			const event = {
				params: { id: String(post.id) },
				request: new Request('http://localhost/', {
					method: 'POST',
					body: formData
				})
			} as Parameters<typeof uploadPostMedia>[0];

			const response = await uploadPostMedia(event);
			expect(response.status).toBe(201);

			const body = await response.json();
			expect(body.media).toBeDefined();
			expect(body.media.id).toBeTypeOf('number');
			expect(body.media.type).toBe('audio/mpeg');

			const updatedPost = await db.query.posts.findFirst({ where: eq(posts.id, post.id) });
			expect(updatedPost?.media_id).toBe(body.media.id);

			const storedMedia = await db.query.media.findFirst({
				where: eq(media.id, body.media.id)
			});
			expect(storedMedia).toBeDefined();
			expect(storedMedia?.user_id).toBe(user.id);
			expect(storedMedia?.type).toBe('audio/mpeg');
		});

		it('rejects non-audio/video uploads', async () => {
			const user = await createTestUser(creatorId);
			const post = await createTestPost(user.id, 'A test post');
			const fakeData = Buffer.from('not-media-data');
			const formData = new FormData();
			formData.append('file', new File([fakeData], 'notes.txt', { type: 'text/plain' }));

			const event = {
				params: { id: String(post.id) },
				request: new Request('http://localhost/', {
					method: 'POST',
					body: formData
				})
			} as Parameters<typeof uploadPostMedia>[0];

			await expect(uploadPostMedia(event)).rejects.toMatchObject({
				status: 400
			});
		});
	});
});
