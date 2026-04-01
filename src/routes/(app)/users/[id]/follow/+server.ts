import { db } from '$lib/server/db';
import { relationships, users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { and, eq } from 'drizzle-orm';

export async function POST({ params, locals }) {
	if (!locals.humanUser) {
		error(401, 'No active human user');
	}

	const aiUserId = Number(params.id);
	if (!Number.isFinite(aiUserId)) {
		error(400, 'Invalid user id');
	}

	const aiUser = await db.query.users.findFirst({
		where: and(eq(users.id, aiUserId), eq(users.is_human, false))
	});
	if (!aiUser) {
		error(404, 'AI user not found');
	}

	const existing = await db.query.relationships.findFirst({
		where: and(
			eq(relationships.user_id, locals.humanUser.id),
			eq(relationships.related_user_id, aiUserId),
			eq(relationships.relationship_type, 'follow')
		)
	});
	if (existing) {
		return json({ already: true });
	}

	await db.insert(relationships).values({
		user_id: locals.humanUser.id,
		related_user_id: aiUserId,
		relationship_type: 'follow'
	});

	return json({ success: true }, { status: 201 });
}

export async function DELETE({ params, locals }) {
	if (!locals.humanUser) {
		error(401, 'No active human user');
	}

	const aiUserId = Number(params.id);
	if (!Number.isFinite(aiUserId)) {
		error(400, 'Invalid user id');
	}

	await db
		.delete(relationships)
		.where(
			and(
				eq(relationships.user_id, locals.humanUser.id),
				eq(relationships.related_user_id, aiUserId),
				eq(relationships.relationship_type, 'follow')
			)
		);

	return json({ success: true });
}
