import { eq, or } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { imageGenerationJobs, images, posts, users } from '$lib/server/db/schema';
import { toWebp } from '$lib/server/image-utils';
import { backend, startGeneration } from './index';
import type {
	ImageGenerationRequest,
	ImageGenerationJobTarget,
	ImageGenerationJobStatus,
	SDStyle
} from './types';

type EnqueueImageJobInput = ImageGenerationRequest & {
	user_id: number;
	post_id?: number | null;
	target: ImageGenerationJobTarget;
	set_as_user_image?: boolean;
};

const activeJobs = new Map<number, Promise<void>>();
let queueBootstrapped = false;

function now() {
	return new Date().toISOString();
}

function normalizeDimension(value: number | undefined, fallback = 512) {
	if (!Number.isFinite(value) || typeof value === 'undefined' || value <= 0) {
		return fallback;
	}
	return Math.floor(value);
}

export async function getImageGenerationJob(jobId: number) {
	return db.query.imageGenerationJobs.findFirst({
		where: eq(imageGenerationJobs.id, jobId),
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
}

export async function enqueueImageJob(input: EnqueueImageJobInput) {
	await ensureImageQueueStarted();
	const timestamp = now();

	const created = await db
		.insert(imageGenerationJobs)
		.values({
			user_id: input.user_id,
			post_id: input.post_id || null,
			provider: backend,
			status: 'queued',
			target: input.target,
			image_style: input.image_style || 'photo',
			prompt: input.prompt,
			negative_prompt: input.negative_prompt || null,
			width: normalizeDimension(input.width),
			height: normalizeDimension(input.height),
			include_default_prompt: input.include_default_prompt ?? true,
			set_as_user_image: input.set_as_user_image ?? false,
			created_at: timestamp,
			updated_at: timestamp
		})
		.returning();

	const job = created[0];
	void ensureImageJobRunning(job.id);
	return getImageGenerationJob(job.id);
}

export async function ensureImageJobRunning(jobId: number) {
	const existing = activeJobs.get(jobId);
	if (existing) {
		return existing;
	}

	const task = runImageJob(jobId).finally(() => {
		activeJobs.delete(jobId);
	});
	activeJobs.set(jobId, task);
	return task;
}

async function ensureImageQueueStarted() {
	if (queueBootstrapped) {
		return;
	}
	queueBootstrapped = true;

	const pendingJobs = await db.query.imageGenerationJobs.findMany({
		where: or(
			eq(imageGenerationJobs.status, 'queued' satisfies ImageGenerationJobStatus),
			eq(imageGenerationJobs.status, 'processing' satisfies ImageGenerationJobStatus)
		)
	});

	for (const job of pendingJobs) {
		void ensureImageJobRunning(job.id);
	}
}

async function runImageJob(jobId: number) {
	const job = await db.query.imageGenerationJobs.findFirst({
		where: eq(imageGenerationJobs.id, jobId)
	});

	if (!job || job.status === 'completed' || job.status === 'failed') {
		return;
	}

	try {
		const task = await startGeneration({
			prompt: job.prompt,
			negative_prompt: job.negative_prompt,
			width: job.width,
			height: job.height,
			include_default_prompt: job.include_default_prompt,
			image_style: job.image_style as SDStyle
		});

		await db
			.update(imageGenerationJobs)
			.set({
				status: 'processing',
				provider_job_id: task.providerJobId,
				provider_metadata: task.providerMetadata,
				started_at: job.started_at || now(),
				updated_at: now(),
				error: null
			})
			.where(eq(imageGenerationJobs.id, jobId));

		const result = await task.waitForResult();
		const webpData = await toWebp(Buffer.from(result.data));
		const inserted = await db
			.insert(images)
			.values({
				user_id: job.user_id,
				params: result.params,
				data: webpData
			})
			.returning();
		const image = inserted[0];

		if (job.set_as_user_image) {
			await db.update(users).set({ image_id: image.id }).where(eq(users.id, job.user_id));
		}

		if (job.post_id !== null) {
			await db.update(posts).set({ image_id: image.id }).where(eq(posts.id, job.post_id));
		}

		await db
			.update(imageGenerationJobs)
			.set({
				status: 'completed',
				image_id: image.id,
				provider_metadata: {
					...(task.providerMetadata || {}),
					...(result.providerMetadata || {})
				},
				completed_at: now(),
				updated_at: now(),
				error: null
			})
			.where(eq(imageGenerationJobs.id, jobId));
	} catch (error) {
		const message = error instanceof Error ? error.message : 'Image generation failed';
		await db
			.update(imageGenerationJobs)
			.set({
				status: 'failed',
				error: message,
				completed_at: now(),
				updated_at: now()
			})
			.where(eq(imageGenerationJobs.id, jobId));
	}
}
