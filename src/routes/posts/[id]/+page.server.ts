import { db } from '$lib/server/db';
import { images, posts, users } from '$lib/server/db/schema';
import { error } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	const { id } = params;
	const post = await db.query.posts.findFirst({
		where: eq(posts.id, id),
		with: {
			image: { columns: { id: true, params: true, blur: true } },
			media: { columns: { id: true, type: true } },
			comments: {
				with: { user: true }
			},
			user: true
		}
	});
	if (!post) {
		error(404, 'Not Found');
	}
	return {
		id,
		post,
		images: await db
			.select({ id: images.id, blur: images.blur })
			.from(images)
			.where(eq(images.user_id, post.user_id)),
		users: await db
			.select()
			.from(users)
			.where(and(eq(users.is_active, true), eq(users.is_human, false)))
	};
};
