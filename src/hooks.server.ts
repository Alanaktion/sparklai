import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import type { Handle } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

const COOKIE_NAME = 'human_user_id';

export const handle: Handle = async ({ event, resolve }) => {
	const userIdRaw = event.cookies.get(COOKIE_NAME);
	const userId = userIdRaw ? Number(userIdRaw) : null;

	if (userId && Number.isFinite(userId)) {
		const user = await db.query.users.findFirst({
			where: eq(users.id, userId)
		});
		event.locals.humanUser = (user?.is_human ? user : null) ?? null;
	} else {
		event.locals.humanUser = null;
	}

	return resolve(event);
};
