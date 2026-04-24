import { dream } from '$lib/server/dream';
import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

export async function POST({ params, locals }) {
	if (!locals.creator) {
		error(401, 'Unauthorized');
	}

	const userId = Number(params.id);
	if (!Number.isFinite(userId)) {
		error(400, 'Invalid user id');
	}

	const user = await db.query.users.findFirst({
		where: eq(users.id, userId)
	});
	if (!user) {
		error(404, 'User not found');
	}
	if (user.creator_id !== locals.creator.id) {
		error(403, 'Forbidden');
	}

	const memory = await dream(userId);

	return json({ memory });
}
