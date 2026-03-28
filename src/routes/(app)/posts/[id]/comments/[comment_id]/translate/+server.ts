import { translateToEnglish } from '$lib/server/chat/translate';
import { db } from '$lib/server/db';
import { comments } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';

export async function POST({ params }) {
	const comment = await db.query.comments.findFirst({
		columns: { id: true, body: true, body_en: true },
		where: and(eq(comments.id, Number(params.comment_id)), eq(comments.post_id, Number(params.id)))
	});

	if (!comment) {
		return error(404, { message: 'Comment not found' });
	}

	if (comment.body_en) {
		return json({ body_en: comment.body_en });
	}

	const body_en = await translateToEnglish(comment.body);

	await db.update(comments).set({ body_en }).where(eq(comments.id, comment.id));

	return json({ body_en });
}
