import { db } from '$lib/server/db';
import { media } from '$lib/server/db/schema';
import { error } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

export async function GET({ params }) {
	const file = await db.query.media.findFirst({
		where: eq(media.id, Number(params.id))
	});
	if (!file) {
		return error(404, {
			message: 'Not found'
		});
	}

	return new Response(file.data, {
		headers: {
			'Content-Type': file.type,
			'Cache-Control': 'public'
		}
	});
}

export async function PATCH({ params, request }) {
	const body = await request.json();
	await db
		.update(media)
		.set(body)
		.where(eq(media.id, Number(params.id)));
	return new Response();
}

export async function DELETE({ params }) {
	await db.delete(media).where(eq(media.id, Number(params.id)));
	return new Response(null, { status: 204 });
}
