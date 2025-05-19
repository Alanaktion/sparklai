import { db } from '$lib/server/db';
import { comments } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

export async function DELETE({ params }) {
	await db.delete(comments).where(eq(comments.id, Number(params.comment_id)));
	return new Response(null, { status: 204 });
}
