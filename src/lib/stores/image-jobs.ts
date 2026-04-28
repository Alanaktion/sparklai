import { browser } from '$app/environment';
import { writable } from 'svelte/store';

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
		params?: {
			prompt: string;
			negative_prompt: string;
			width: number;
			height: number;
			cfg_scale: number;
			seed: number;
		} | null;
		blur?: boolean;
	} | null;
};

export type TrackedImageJob = {
	id: number;
	label: string;
	status: ImageJobStatus;
	phase: 'prompt' | 'image';
	temporary: boolean;
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
let nextTemporaryJobId = -1;

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
	const phase = value.phase === 'prompt' ? 'prompt' : 'image';
	const temporary = Boolean(value.temporary);
	if (temporary) {
		return null;
	}

	const now = Date.now();
	return {
		id,
		label: typeof value.label === 'string' && value.label.length ? value.label : 'Image generation',
		status,
		phase,
		temporary,
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

function createTrackedJob(
	id: number,
	status: ImageJobStatus,
	options?: {
		label?: string;
		phase?: 'prompt' | 'image';
		temporary?: boolean;
		image_id?: number | null;
		error?: string | null;
		set_as_user_image?: boolean;
		post_id?: number | null;
		user_id?: number | null;
		createdAt?: number;
		updatedAt?: number;
		finishedAt?: number | null;
	}
): TrackedImageJob {
	const now = Date.now();
	return {
		id,
		label: options?.label || 'Image generation',
		status,
		phase: options?.phase || 'image',
		temporary: options?.temporary ?? false,
		image_id: options?.image_id ?? null,
		error: options?.error ?? null,
		set_as_user_image: options?.set_as_user_image ?? false,
		post_id: options?.post_id ?? null,
		user_id: options?.user_id ?? null,
		createdAt: options?.createdAt ?? now,
		updatedAt: options?.updatedAt ?? now,
		finishedAt: options?.finishedAt ?? null
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
			phase: 'image',
			temporary: false,
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
			createTrackedJob(jobId, 'failed', {
				label: label || 'Image generation',
				error: message,
				updatedAt: now,
				finishedAt: now
			}),
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
					params:
						isObject(value.image.params) &&
						typeof value.image.params.prompt === 'string' &&
						typeof value.image.params.negative_prompt === 'string' &&
						Number.isFinite(value.image.params.width) &&
						Number.isFinite(value.image.params.height) &&
						Number.isFinite(value.image.params.cfg_scale) &&
						Number.isFinite(value.image.params.seed)
							? {
									prompt: value.image.params.prompt,
									negative_prompt: value.image.params.negative_prompt,
									width: Number(value.image.params.width),
									height: Number(value.image.params.height),
									cfg_scale: Number(value.image.params.cfg_scale),
									seed: Number(value.image.params.seed)
								}
							: null,
					blur: typeof value.image.blur === 'boolean' ? value.image.blur : undefined
				}
			: null
	};
}

function assertImageJobListResponse(value: unknown): ImageGenerationJobResponse[] {
	if (!Array.isArray(value)) {
		throw new Error('Invalid image jobs response');
	}

	return value.map((item) => assertImageJobResponse(item));
}

async function syncActiveJobsFromServer() {
	if (!browser) {
		return;
	}

	try {
		const response = await fetch('/image-jobs');
		if (!response.ok) {
			throw new Error(`Unable to load image jobs (${response.status})`);
		}

		const payload = (await response.json()) as unknown;
		const jobs = assertImageJobListResponse(payload);

		for (const job of jobs) {
			upsertJobFromServer(job);
			if (activeStatuses.has(job.status)) {
				void pollImageJob(job.id);
			}
		}
	} catch {
		// Best-effort sync: keep local tracking if the server refresh fails.
	}
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

function trackKnownImageJob(
	job: ImageGenerationJobResponse,
	options?: { label?: string }
): Promise<ImageGenerationJobResponse> {
	initImageJobTracker();
	upsertJobFromServer(job, options?.label);
	if (activeStatuses.has(job.status)) {
		return pollImageJob(job.id, options?.label);
	}
	return Promise.resolve(job);
}

function persistJobs(jobs: TrackedImageJob[]) {
	if (!browser) {
		return;
	}
	const persistedJobs = jobs.filter((job) => !job.temporary).slice(0, MAX_STORED_JOBS);
	localStorage.setItem(STORAGE_KEY, JSON.stringify(persistedJobs));
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

	void syncActiveJobsFromServer();
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

export function trackImageJobResponse(
	job: ImageGenerationJobResponse,
	options?: { label?: string }
) {
	return trackKnownImageJob(job, options);
}

export function startImageJobRequest(options?: { label?: string; phase?: 'prompt' | 'image' }) {
	initImageJobTracker();

	const temporaryJobId = nextTemporaryJobId;
	nextTemporaryJobId -= 1;

	imageJobsStore.update((jobs) => [
		createTrackedJob(temporaryJobId, 'processing', {
			label: options?.label || 'Image generation',
			phase: options?.phase || 'image',
			temporary: true
		}),
		...jobs
	]);

	return temporaryJobId;
}

export function startImageJobPrompt(options?: { label?: string }) {
	return startImageJobRequest({
		label: options?.label,
		phase: 'prompt'
	});
}

export function failImageJobPrompt(
	promptJobId: number,
	message: string,
	options?: { label?: string }
) {
	const now = Date.now();
	imageJobsStore.update((jobs) => {
		const index = jobs.findIndex((job) => job.id === promptJobId);
		if (index < 0) {
			return jobs;
		}

		const next = [...jobs];
		next[index] = {
			...next[index],
			label: options?.label || next[index].label,
			status: 'failed',
			error: message,
			updatedAt: now,
			finishedAt: now
		};
		return next;
	});

	scheduleAutoDismiss(promptJobId);
}

export function failImageJobRequest(jobId: number, message: string, options?: { label?: string }) {
	return failImageJobPrompt(jobId, message, options);
}

export function replaceImageJobPrompt(
	promptJobId: number,
	jobs: ImageGenerationJobResponse[],
	options?: { label?: string }
) {
	dismissImageJob(promptJobId);
	return jobs.map((job) => trackKnownImageJob(job, options));
}

export function replaceImageJobRequest(
	jobId: number,
	jobs: ImageGenerationJobResponse[],
	options?: { label?: string }
) {
	return replaceImageJobPrompt(jobId, jobs, options);
}

export function dismissImageJob(jobId: number) {
	clearDismissTimer(jobId);
	imageJobsStore.update((jobs) => jobs.filter((job) => job.id !== jobId));
}

export const imageJobs = imageJobsStore;
