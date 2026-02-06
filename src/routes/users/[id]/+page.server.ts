import { db } from '$lib/server/db';
import { images, posts, relationships, users } from '$lib/server/db/schema';
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

	// Get followers (users who follow this user)
	const followersData = await db
		.select({
			id: users.id,
			name: users.name,
			pronouns: users.pronouns,
			image_id: users.image_id
		})
		.from(relationships)
		.innerJoin(users, eq(relationships.follower_id, users.id))
		.where(eq(relationships.following_id, id));

	// Get following (users this user follows)
	const followingData = await db
		.select({
			id: users.id,
			name: users.name,
			pronouns: users.pronouns,
			image_id: users.image_id
		})
		.from(relationships)
		.innerJoin(users, eq(relationships.following_id, users.id))
		.where(eq(relationships.follower_id, id));

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
			.where(eq(images.user_id, id)),
		followers: followersData,
		following: followingData
	};
};
