import { db } from '$lib/server/db';
import { chats } from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

export async function DELETE({ params }) {
	await db.delete(chats).where(eq(chats.id, Number(params.message_id)));
	return new Response(null, { status: 204 });
}
