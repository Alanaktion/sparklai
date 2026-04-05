import { db } from '$lib/server/db';
import { images, posts, users } from '$lib/server/db/schema';
import { error } from '@sveltejs/kit';
import { and, eq, inArray } from 'drizzle-orm';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, locals }) => {
	const { id } = params;
	const post = await db.query.posts.findFirst({
		where: eq(posts.id, Number(id)),
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

	if (!locals.creator) {
		return { id, post, images: [], users: [] };
	}

	const creator_user_ids = db
		.select({ id: users.id })
		.from(users)
		.where(and(eq(users.is_active, true), eq(users.creator_id, locals.creator.id)));

	return {
		id,
		post,
		images: await db
			.select({ id: images.id, blur: images.blur, params: images.params })
			.from(images)
			.where(eq(images.user_id, post.user_id)),
		users: await db.select().from(users).where(inArray(users.id, creator_user_ids))
	};
};
