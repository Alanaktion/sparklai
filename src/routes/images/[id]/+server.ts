import { db } from '$lib/server/db';
import { images } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

export async function GET({ params }) {
	const image = (await db.select().from(images).where(eq(images.id, params.id)))[0];

	return new Response(image.data, {
		headers: {
			'Content-Type': 'image/webp',
			'Cache-Control': 'public'
		}
	});
}
