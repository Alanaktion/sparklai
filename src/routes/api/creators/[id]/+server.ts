import { verifyPin } from '$lib/server/auth';
import { db } from '$lib/server/db';
import { creators } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

const COOKIE_NAME = 'creator_session';

export async function POST({ params, request, cookies }) {
	const id = Number(params.id);
	if (!Number.isFinite(id)) {
		error(400, 'Invalid creator id');
	}

	const creator = await db.query.creators.findFirst({
		where: eq(creators.id, id)
	});
	if (!creator) {
		error(404, 'Creator not found');
	}

	const data = await request.json().catch(() => ({}));
	const pin = typeof data.pin === 'string' ? data.pin : '';

	const valid = await verifyPin(pin, creator.password_hash);
	if (!valid) {
		error(401, 'Invalid PIN');
	}

	cookies.set(COOKIE_NAME, String(creator.id), {
		path: '/',
		httpOnly: true,
		sameSite: 'strict',
		maxAge: 60 * 60 * 24 * 365
	});

	return json(creator);
}
