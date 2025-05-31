import { db } from '$lib/server/db';
import { users } from '$lib/server/db/schema';
import { generatePost } from '$lib/server/index.js';
import { error, json } from '@sveltejs/kit';
import { eq } from 'drizzle-orm';

export async function POST({ params, request }) {
	const user = await db.query.users.findFirst({
		where: eq(users.id, Number(params.id))
	});
	if (!user) {
		return error(404, {
			message: 'Not found'
		});
	}

	let prompt = null;
	if (request.headers.get('Content-Type')?.includes('form')) {
		const data = await request.formData();
		if (data.has('prompt')) {
			prompt = data.get('prompt')?.toString();
		}
	}
	const post = await generatePost(user, prompt);

	return json(post);
}
