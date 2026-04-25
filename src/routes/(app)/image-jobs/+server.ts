import { db } from '$lib/server/db';
import { imageGenerationJobs, users } from '$lib/server/db/schema';
import { ensureImageJobRunning } from '$lib/server/sd/jobs';
import { json } from '@sveltejs/kit';
import { and, eq, inArray, or } from 'drizzle-orm';

export async function GET({ locals }) {
	if (!locals.creator) {
		return json([]);
	}

	const creatorUserIds = db
		.select({ id: users.id })
		.from(users)
		.where(and(eq(users.is_active, true), eq(users.creator_id, locals.creator.id)));

	const jobs = await db.query.imageGenerationJobs.findMany({
		where: and(
			inArray(imageGenerationJobs.user_id, creatorUserIds),
			or(eq(imageGenerationJobs.status, 'queued'), eq(imageGenerationJobs.status, 'processing'))
		),
		with: {
			image: {
				columns: {
					id: true,
					params: true,
					blur: true
				}
			}
		}
	});

	for (const job of jobs) {
		void ensureImageJobRunning(job.id);
	}

	return json(jobs);
}
