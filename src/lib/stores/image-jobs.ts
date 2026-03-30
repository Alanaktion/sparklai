import { browser } from '$app/environment';
import { get, writable } from 'svelte/store';

export type ImageJobStatus = 'queued' | 'processing' | 'completed' | 'failed';

export type ImageGenerationJobResponse = {
	id: number;
	status: ImageJobStatus;
	image_id: number | null;
	error: string | null;
	set_as_user_image: boolean;
	post_id: number | null;
	user_id: number;
	image?: {
		id: number;
		blur?: boolean;
	} | null;
};

export type TrackedImageJob = {
	id: number;
	label: string;
	status: ImageJobStatus;
	image_id: number | null;
	error: string | null;
	set_as_user_image: boolean;
	post_id: number | null;
	user_id: number | null;
	createdAt: number;
	updatedAt: number;
	finishedAt: number | null;
};

const STORAGE_KEY = 'sparklai:image-jobs';
const MAX_STORED_JOBS = 30;
const POLL_INTERVAL_MS = 1500;
const AUTO_DISMISS_MS = 10000;

const activeStatuses = new Set<ImageJobStatus>(['queued', 'processing']);
const imageJobsStore = writable<TrackedImageJob[]>([]);
const activePollers = new Map<number, Promise<ImageGenerationJobResponse>>();
const autoDismissTimers = new Map<number, ReturnType<typeof setTimeout>>();

let initialized = false;

function delay(ms: number) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

function isObject(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null;
}

function normalizeStatus(status: unknown): ImageJobStatus {
	if (
		status === 'queued' ||
		status === 'processing' ||
		status === 'completed' ||
		status === 'failed'
	) {
		return status;
	}
	return 'queued';
}

function normalizeStoredJob(value: unknown): TrackedImageJob | null {
	if (!isObject(value)) {
		return null;
	}

	const id = Number(value.id);
	if (!Number.isFinite(id)) {
		return null;
	}

	const status = normalizeStatus(value.status);
	const now = Date.now();
	return {
		id,
		label: typeof value.label === 'string' && value.label.length ? value.label : 'Image generation',
		status,
		image_id: Number.isFinite(value.image_id) ? Number(value.image_id) : null,
		error: typeof value.error === 'string' ? value.error : null,
		set_as_user_image: Boolean(value.set_as_user_image),
		post_id: Number.isFinite(value.post_id) ? Number(value.post_id) : null,
		user_id: Number.isFinite(value.user_id) ? Number(value.user_id) : null,
		createdAt: Number.isFinite(value.createdAt) ? Number(value.createdAt) : now,
		updatedAt: Number.isFinite(value.updatedAt) ? Number(value.updatedAt) : now,
		finishedAt: Number.isFinite(value.finishedAt) ? Number(value.finishedAt) : null
	};
}

function clearDismissTimer(jobId: number) {
	const timer = autoDismissTimers.get(jobId);
	if (timer) {
		clearTimeout(timer);
		autoDismissTimers.delete(jobId);
	}
}

function scheduleAutoDismiss(jobId: number) {
	if (!browser) {
		return;
	}

	clearDismissTimer(jobId);
	const timer = setTimeout(() => {
		dismissImageJob(jobId);
	}, AUTO_DISMISS_MS);
	autoDismissTimers.set(jobId, timer);
}

function upsertJobFromServer(job: ImageGenerationJobResponse, label?: string) {
	const now = Date.now();

	imageJobsStore.update((jobs) => {
		const index = jobs.findIndex((existing) => existing.id === job.id);
		const existing = index >= 0 ? jobs[index] : null;
		const merged: TrackedImageJob = {
			id: job.id,
			label: label || existing?.label || 'Image generation',
			status: job.status,
			image_id: job.image_id,
			error: job.error,
			set_as_user_image: job.set_as_user_image,
			post_id: job.post_id,
			user_id: job.user_id,
			createdAt: existing?.createdAt || now,
			updatedAt: now,
			finishedAt:
				job.status === 'completed' || job.status === 'failed' ? existing?.finishedAt || now : null
		};

		if (index >= 0) {
			const next = [...jobs];
			next[index] = merged;
			return next;
		}

		return [merged, ...jobs];
	});

	if (activeStatuses.has(job.status)) {
		clearDismissTimer(job.id);
	} else {
		scheduleAutoDismiss(job.id);
	}
}

function markPollingError(jobId: number, message: string, label?: string) {
	const now = Date.now();
	imageJobsStore.update((jobs) => {
		const index = jobs.findIndex((job) => job.id === jobId);
		if (index >= 0) {
			const next = [...jobs];
			next[index] = {
				...next[index],
				label: label || next[index].label,
				status: 'failed',
				error: message,
				updatedAt: now,
				finishedAt: next[index].finishedAt || now
			};
			return next;
		}

		return [
			{
				id: jobId,
				label: label || 'Image generation',
				status: 'failed',
				image_id: null,
				error: message,
				set_as_user_image: false,
				post_id: null,
				user_id: null,
				createdAt: now,
				updatedAt: now,
				finishedAt: now
			},
			...jobs
		];
	});

	scheduleAutoDismiss(jobId);
}

function assertImageJobResponse(value: unknown): ImageGenerationJobResponse {
	if (!isObject(value)) {
		throw new Error('Invalid image job response');
	}

	const id = Number(value.id);
	if (!Number.isFinite(id)) {
		throw new Error('Invalid image job id');
	}

	const status = normalizeStatus(value.status);
	if (value.status !== status) {
		throw new Error('Invalid image job status');
	}

	return {
		id,
		status,
		image_id: Number.isFinite(value.image_id) ? Number(value.image_id) : null,
		error: typeof value.error === 'string' ? value.error : null,
		set_as_user_image: Boolean(value.set_as_user_image),
		post_id: Number.isFinite(value.post_id) ? Number(value.post_id) : null,
		user_id: Number.isFinite(value.user_id) ? Number(value.user_id) : 0,
		image: isObject(value.image)
			? {
					id: Number(value.image.id),
					blur: typeof value.image.blur === 'boolean' ? value.image.blur : undefined
				}
			: null
	};
}

async function pollImageJob(jobId: number, label?: string): Promise<ImageGenerationJobResponse> {
	const existing = activePollers.get(jobId);
	if (existing) {
		return existing;
	}

	const task = (async () => {
		while (true) {
			const response = await fetch(`/image-jobs/${jobId}`);
			if (!response.ok) {
				throw new Error(`Unable to check image generation status (${response.status})`);
			}

			const payload = (await response.json()) as unknown;
			const job = assertImageJobResponse(payload);
			upsertJobFromServer(job, label);

			if (!activeStatuses.has(job.status)) {
				return job;
			}

			await delay(POLL_INTERVAL_MS);
		}
	})();

	const guarded = task.catch((error) => {
		const message = error instanceof Error ? error.message : 'Image generation failed';
		markPollingError(jobId, message, label);
		throw error;
	});

	activePollers.set(jobId, guarded);
	return guarded.finally(() => {
		activePollers.delete(jobId);
	});
}

function persistJobs(jobs: TrackedImageJob[]) {
	if (!browser) {
		return;
	}
	localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs.slice(0, MAX_STORED_JOBS)));
}

function hydrateJobs() {
	if (!browser) {
		return;
	}

	let parsed: unknown = [];
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw) {
			parsed = JSON.parse(raw) as unknown;
		}
	} catch {
		parsed = [];
	}

	const restored = Array.isArray(parsed)
		? parsed.map(normalizeStoredJob).filter((job): job is TrackedImageJob => job !== null)
		: [];
	imageJobsStore.set(restored);

	for (const job of restored) {
		if (activeStatuses.has(job.status)) {
			void pollImageJob(job.id, job.label);
		} else {
			scheduleAutoDismiss(job.id);
		}
	}
}

if (browser) {
	imageJobsStore.subscribe((jobs) => {
		persistJobs(jobs);
	});
}

export function initImageJobTracker() {
	if (!browser || initialized) {
		return;
	}
	initialized = true;
	hydrateJobs();
}

export function trackImageJob(jobId: number, options?: { label?: string }) {
	initImageJobTracker();

	const existing = get(imageJobsStore).find((job) => job.id === jobId);
	if (!existing) {
		const now = Date.now();
		imageJobsStore.update((jobs) => [
			{
				id: jobId,
				label: options?.label || 'Image generation',
				status: 'queued',
				image_id: null,
				error: null,
				set_as_user_image: false,
				post_id: null,
				user_id: null,
				createdAt: now,
				updatedAt: now,
				finishedAt: null
			},
			...jobs
		]);
	}

	return pollImageJob(jobId, options?.label);
}

export function dismissImageJob(jobId: number) {
	clearDismissTimer(jobId);
	imageJobsStore.update((jobs) => jobs.filter((job) => job.id !== jobId));
}

export const imageJobs = imageJobsStore;
