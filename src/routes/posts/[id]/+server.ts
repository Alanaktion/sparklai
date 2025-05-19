import { db } from '$lib/server/db';
import { posts } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

export async function DELETE({ params }) {
	await db.delete(posts).where(eq(posts.id, Number(params.id)));
	return new Response(null, { status: 204 });
}

export async function PATCH({ params, request }) {
	const body = await request.json();
	await db
		.update(posts)
		.set(body)
		.where(eq(posts.id, Number(params.id)));
	return new Response(null);
}
