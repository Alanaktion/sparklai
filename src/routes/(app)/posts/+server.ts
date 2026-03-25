import { generatePost } from '$lib/server';
import { db } from '$lib/server/db';
import { posts, users } from '$lib/server/db/schema';
import { error, json } from '@sveltejs/kit';
import { and, desc, eq, inArray, like, lt, sql } from 'drizzle-orm';

const DEFAULT_LIMIT = 15;
const MAX_LIMIT = 50;

export async function GET({ url }) {
	const limitParam = Number(url.searchParams.get('limit') ?? DEFAULT_LIMIT);
	const limit = Number.isFinite(limitParam)
		? Math.min(Math.max(Math.floor(limitParam), 1), MAX_LIMIT)
		: DEFAULT_LIMIT;

	const cursorParam = Number(url.searchParams.get('cursor'));
	const cursor = Number.isFinite(cursorParam) && cursorParam > 0 ? cursorParam : null;

	const q = url.searchParams.get('q')?.trim() ?? '';

	const active_user_ids = db
		.select({ id: users.id })
		.from(users)
		.where(and(eq(users.is_active, true), eq(users.is_human, false)));

	const filters = [inArray(posts.user_id, active_user_ids)];
	if (cursor) {
		filters.push(lt(posts.id, cursor));
	}
	if (q.length) {
		filters.push(like(posts.body, `%${q}%`));
	}

	const rows = await db.query.posts.findMany({
		with: {
			image: { columns: { id: true, params: true, blur: true } },
			media: { columns: { id: true, type: true } }
		},
		where: and(...filters),
		orderBy: desc(posts.id),
		limit: limit + 1
	});

	const hasMore = rows.length > limit;
	return json({
		posts: hasMore ? rows.slice(0, limit) : rows,
		hasMore
	});
}

// Generate a post for a random user
export async function POST() {
	const author = await db.query.users.findFirst({
		where: and(eq(users.is_active, true), eq(users.is_human, false)),
		orderBy: sql`random()`
	});
	if (!author) {
		return error(404, 'No Users Found');
	}
	const result = await generatePost(author);
	return json(result, { status: 201 });
}
