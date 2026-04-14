import { db } from '$lib/server/db';
import { media, posts, users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

const MAX_UPLOAD_BYTES = 100 * 1024 * 1024; // 100MB

export async function POST({ params, request }) {
	const postRecord = await db.query.posts.findFirst({
		where: eq(posts.id, Number(params.id))
	});
	if (!postRecord) {
		return error(404, {
			message: 'Not found'
		});
	}

	const user = await db.query.users.findFirst({
		where: eq(users.id, postRecord.user_id)
	});
	if (!user) {
		return error(404, {
			message: 'Not found'
		});
	}

	if (!request.headers.get('Content-Type')?.includes('multipart/form-data')) {
		return error(400, { message: 'Expected multipart/form-data' });
	}

	const data = await request.formData();
	const file = data.get('file');
	if (!(file instanceof File)) {
		return error(400, { message: 'No file uploaded' });
	}

	if (file.size > MAX_UPLOAD_BYTES) {
		return error(413, { message: 'File too large (max 100MB)' });
	}

	if (!(file.type.startsWith('audio/') || file.type.startsWith('video/'))) {
		return error(400, { message: 'Only audio and video uploads are supported' });
	}

	const inserted = await db
		.insert(media)
		.values({
			user_id: user.id,
			type: file.type,
			data: Buffer.from(await file.arrayBuffer())
		})
		.returning({ id: media.id, type: media.type });

	const uploadedMedia = inserted[0];
	await db.update(posts).set({ media_id: uploadedMedia.id }).where(eq(posts.id, postRecord.id));

	return json({ media: uploadedMedia }, { status: 201 });
}
