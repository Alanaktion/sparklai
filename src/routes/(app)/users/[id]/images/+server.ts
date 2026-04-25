import { db } from '$lib/server/db';
import { images, users } from '$lib/server/db/schema';
import { toWebp } from '$lib/server/image-utils.js';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10MB

export async function POST({ params, request }) {
	const user = await db.query.users.findFirst({
		where: eq(users.id, Number(params.id))
	});
	if (!user) {
		return error(404, { message: 'User not found' });
	}

	if (!request.headers.get('Content-Type')?.includes('multipart/form-data')) {
		return error(400, { message: 'Expected multipart/form-data' });
	}

	const data = await request.formData();
	const files = data.getAll('files');

	if (!files.length) {
		return error(400, { message: 'No files uploaded' });
	}

	const insertedImages = [];
	for (const file of files) {
		if (!(file instanceof File)) {
			continue;
		}
		if (file.size > MAX_UPLOAD_BYTES) {
			return error(413, { message: `File "${file.name}" too large (max 10MB)` });
		}
		const arrayBuffer = await file.arrayBuffer();
		let webpData: Buffer;
		try {
			webpData = await toWebp(Buffer.from(arrayBuffer));
		} catch {
			return error(400, { message: `Invalid image file: "${file.name}"` });
		}
		const inserted = await db
			.insert(images)
			.values({ user_id: user.id, data: webpData })
			.returning();
		insertedImages.push(inserted[0]);
	}

	if (!insertedImages.length) {
		return error(400, { message: 'No valid files uploaded' });
	}

	return json({ images: insertedImages }, { status: 201 });
}
