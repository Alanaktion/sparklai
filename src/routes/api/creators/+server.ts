import { hashPin } from '$lib/server/auth';
import { db } from '$lib/server/db';
import { creators } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';

export async function POST({ request }) {
	const data = await request.json().catch(() => null);
	if (!data || typeof data.name !== 'string' || !data.name.trim()) {
		error(400, 'name is required');
	}

	const pin = typeof data.pin === 'string' ? data.pin.trim() : '';
	if (!pin) {
		error(400, 'pin is required');
	}

	const name = data.name.trim();
	const pronouns = typeof data.pronouns === 'string' ? data.pronouns.trim() : 'they/them';
	const password_hash = await hashPin(pin);

	const result = await db
		.insert(creators)
		.values({
			name,
			pronouns,
			password_hash
		})
		.returning();

	return json(result[0], { status: 201 });
}
