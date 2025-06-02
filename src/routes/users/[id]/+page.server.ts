import { db } from '$lib/server/db';
import { images, posts, users } from '$lib/server/db/schema';
import { error } from '@sveltejs/kit';
import { desc, eq } from 'drizzle-orm';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	const id = params.id;
	const user = await db.query.users.findFirst({
		where: eq(users.id, id)
	});
	if (!user) {
		error(404, 'Not Found');
	}
	return {
		id,
		user,
		posts: await db.query.posts.findMany({
			with: {
				image: { columns: { id: true, params: true, blur: true } },
				media: { columns: { id: true, type: true } }
			},
			orderBy: desc(posts.created_at),
			where: eq(posts.user_id, id)
		}),
		images: await db
			.select({ id: images.id, params: images.params, blur: images.blur })
			.from(images)
			.where(eq(images.user_id, id))
	};
};
