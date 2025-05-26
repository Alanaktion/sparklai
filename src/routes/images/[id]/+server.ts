import { db } from '$lib/server/db';
import { images } from '$lib/server/db/schema';
import { error } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

export async function GET({ params }) {
	const image = await db.query.images.findFirst({
		where: eq(images.id, Number(params.id))
	});
	if (!image) {
		return error(404, {
			message: 'Not found'
		});
	}

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
