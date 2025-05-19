import { db } from '$lib/server/db';
import { images } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

export async function GET({ params }) {
	const image_result = await db
		.select()
		.from(images)
		.where(eq(images.id, Number(params.id)));
	if (!image_result.length) {
		return new Response(null, { status: 404 });
	}
	const image = image_result[0];

	return new Response(image.data, {
		headers: {
			'Content-Type': 'image/webp',
			'Cache-Control': 'public'
		}
	});
}

export async function DELETE({ params }) {
	await db.delete(images).where(eq(images.id, Number(params.id)));
	return new Response(null, { status: 204 });
}
