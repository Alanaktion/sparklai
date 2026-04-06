import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

// Get the additional prompt context for this user
export async function GET({ params, locals }) {
	const creator = locals.creator;
	if (!creator) {
		return error(401, { message: 'Unauthorized' });
	}

	const userId = Number(params.id);
	const user = await db.query.users.findFirst({
		where: eq(users.id, userId)
	});
	if (!user) {
		return error(404, { message: 'Not found' });
	}

	return json({ additional_prompt: user.additional_prompt });
}

// Set the additional prompt context for this user
export async function PUT({ params, locals, request }) {
	const creator = locals.creator;
	if (!creator) {
		return error(401, { message: 'Unauthorized' });
	}

	const userId = Number(params.id);
	const user = await db.query.users.findFirst({
		where: eq(users.id, userId)
	});
	if (!user) {
		return error(404, { message: 'Not found' });
	}

	const body = await request.json();
	const additionalPrompt: string = body.additional_prompt ?? '';

	await db.update(users).set({ additional_prompt: additionalPrompt }).where(eq(users.id, userId));

	return json({ additional_prompt: additionalPrompt });
}
