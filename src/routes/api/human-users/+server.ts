import { hashPin } from '$lib/server/auth';
import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';

export async function POST({ request }) {
	const data = await request.json().catch(() => null);
	if (!data || typeof data.name !== 'string' || !data.name.trim()) {
		error(400, 'name is required');
	}

	const name = data.name.trim();
	const pronouns = typeof data.pronouns === 'string' ? data.pronouns.trim() : 'they/them';
	const pin = typeof data.pin === 'string' ? data.pin : '';

	const password_hash = pin.length > 0 ? await hashPin(pin) : null;

	const result = await db
		.insert(users)
		.values({
			name,
			age: 25,
			pronouns,
			is_human: true,
			password_hash
		})
		.returning();

	return json(result[0], { status: 201 });
}
