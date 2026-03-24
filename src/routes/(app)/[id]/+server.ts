import { ensureImageJobRunning, getImageGenerationJob } from '$lib/server/sd/jobs';
import { error, json } from '@sveltejs/kit';

export async function GET({ params }) {
	const jobId = Number(params.id);
	if (!Number.isFinite(jobId)) {
		return error(400, {
			message: 'Invalid image job id'
		});
	}

	const job = await getImageGenerationJob(jobId);
	if (!job) {
		return error(404, {
			message: 'Image job not found'
		});
	}

	if (job.status === 'queued' || job.status === 'processing') {
		void ensureImageJobRunning(job.id);
	}

	return json(job);
}
