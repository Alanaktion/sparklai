import { db } from '$lib/server/db';
import { posts, users } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

export async function DELETE({ params }) {
	await db.delete(posts).where(eq(users.id, Number(params.id)));
	return new Response(null, { status: 204 });
}

export async function PATCH({ params, request }) {
	const body = await request.json();
	await db
		.update(users)
		.set(body)
		.where(eq(users.id, Number(params.id)));

	// Return the updated user
	const updatedUser = await db.query.users.findFirst({
		where: eq(users.id, Number(params.id))
	});

	return new Response(JSON.stringify(updatedUser), {
		headers: {
			'Content-Type': 'application/json'
		}
	});
}
