import { verifyPin } from '$lib/server/auth';
import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';

const COOKIE_NAME = 'human_user_id';

export async function POST({ params, request, cookies }) {
	const id = Number(params.id);
	if (!Number.isFinite(id)) {
		error(400, 'Invalid user id');
	}

	const user = await db.query.users.findFirst({
		where: and(eq(users.id, id), eq(users.is_human, true))
	});
	if (!user) {
		error(404, 'User not found');
	}

	const data = await request.json().catch(() => ({}));
	const pin = typeof data.pin === 'string' ? data.pin : '';

	if (user.password_hash) {
		const valid = await verifyPin(pin, user.password_hash);
		if (!valid) {
			error(401, 'Invalid PIN');
		}
	}
	// If no password_hash set, any PIN (including empty) is accepted

	cookies.set(COOKIE_NAME, String(user.id), {
		path: '/',
		httpOnly: true,
		sameSite: 'strict',
		maxAge: 60 * 60 * 24 * 365
	});

	return json(user);
}
