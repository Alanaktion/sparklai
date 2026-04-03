import { db } from '$lib/server/db';
import { creators } from '$lib/server/db/schema';
import type { Handle } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

const COOKIE_NAME = 'creator_session';

export const handle: Handle = async ({ event, resolve }) => {
	const creatorIdRaw = event.cookies.get(COOKIE_NAME);
	const creatorId = creatorIdRaw ? Number(creatorIdRaw) : null;

	if (creatorId && Number.isFinite(creatorId)) {
		const creator = await db.query.creators.findFirst({
			where: eq(creators.id, creatorId)
		});
		event.locals.creator = creator ?? null;
	} else {
		event.locals.creator = null;
	}

	return resolve(event);
};
