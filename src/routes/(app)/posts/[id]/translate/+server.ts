import { translateToEnglish } from '$lib/server/chat/translate';
import { db } from '$lib/server/db';
import { posts } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

export async function POST({ params }) {
	const post = await db.query.posts.findFirst({
		columns: { id: true, body: true, body_en: true },
		where: eq(posts.id, Number(params.id))
	});

	if (!post) {
		return error(404, { message: 'Post not found' });
	}

	if (post.body_en) {
		return json({ body_en: post.body_en });
	}

	const body_en = await translateToEnglish(post.body);

	await db.update(posts).set({ body_en }).where(eq(posts.id, post.id));

	return json({ body_en });
}
