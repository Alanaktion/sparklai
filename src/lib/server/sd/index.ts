import { env } from '$env/dynamic/private';
import { randomUUID } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type {
	ImageGenerationRequest,
	QueuedGenerationTask,
	SDBackend,
	SDModel,
	SDStyle,
	StableDiffusionParams
} from './types';

if (!env.SD_URL) throw new Error('SD_URL is not set');

type StyleConfig = {
	model: string;
	prompt: string;
	negative_prompt: string;
};

type ComfyWorkflowTemplate = {
	output_node_id: string;
	prompt: Record<string, unknown>;
};

type ComfyHistoryImage = {
	filename: string;
	subfolder: string;
	type: string;
};

type ComfyHistoryEntry = {
	outputs?: Record<string, { images?: ComfyHistoryImage[] }>;
	status?: {
		status_str?: string;
		completed?: boolean;
		messages?: unknown[];
	};
	meta?: Record<string, unknown>;
};

const steps = 20;
const cfg_scale = 7;
const format = 'webp';
const comfyPollIntervalMs = Number(env.SD_COMFY_POLL_INTERVAL_MS || 1500);
const comfyTimeoutMs = Number(env.SD_COMFY_TIMEOUT_MS || 180000);
const workflowCache = new Map<SDStyle, ComfyWorkflowTemplate>();
const workflowDir = join(dirname(fileURLToPath(import.meta.url)), 'workflows');

export const backend: SDBackend = env.SD_BACKEND === 'comfyui' ? 'comfyui' : 'automatic1111';
export let model = env.SD_PHOTO_MODEL || '';
export const styles: Record<SDStyle, StyleConfig> = {
	photo: {
		model: env.SD_PHOTO_MODEL || '',
		prompt: env.SD_PHOTO_PROMPT || '',
		negative_prompt: env.SD_PHOTO_NEGATIVE_PROMPT || ''
	},
	drawing: {
		model: env.SD_DRAWING_MODEL || '',
		prompt: env.SD_DRAWING_PROMPT || '',
		negative_prompt: env.SD_DRAWING_NEGATIVE_PROMPT || ''
	},
	stylized: {
		model: env.SD_STYLIZED_MODEL || '',
		prompt: env.SD_STYLIZED_PROMPT || '',
		negative_prompt: env.SD_STYLIZED_NEGATIVE_PROMPT || ''
	}
};
export let style: SDStyle = 'photo';

function sdUrl(path: string) {
	const base = env.SD_URL!.endsWith('/') ? env.SD_URL! : `${env.SD_URL!}/`;
	return new URL(path.replace(/^\/+/, ''), base).toString();
}

function nowSeed() {
	return Math.floor(Math.random() * 2147483647);
}

function delay(ms: number) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

function jsonHeaders() {
	return {
		'Content-Type': 'application/json'
	};
}

function base64Decode(str: string) {
	return Uint8Array.from(Buffer.from(str, 'base64'));
}

function buildParams(request: ImageGenerationRequest): StableDiffusionParams {
	const imageStyle = request.image_style || style;
	const includeDefaultPrompt = request.include_default_prompt ?? true;
	const positivePrompt = includeDefaultPrompt
		? [request.prompt, styles[imageStyle].prompt].filter(Boolean).join('\n')
		: request.prompt;
	const negativePrompt = request.negative_prompt
		? includeDefaultPrompt
			? [request.negative_prompt, styles[imageStyle].negative_prompt].filter(Boolean).join('\n')
			: request.negative_prompt
		: includeDefaultPrompt
			? styles[imageStyle].negative_prompt
			: '';

	return {
		prompt: positivePrompt,
		negative_prompt: negativePrompt,
		width: request.width,
		height: request.height,
		cfg_scale,
		seed: nowSeed()
	};
}

async function readWorkflowTemplate(imageStyle: SDStyle) {
	const cached = workflowCache.get(imageStyle);
	if (cached) {
		return cached;
	}

	const filePath = join(workflowDir, `${imageStyle}.json`);
	const raw = await readFile(filePath, 'utf8');
	const parsed = JSON.parse(raw) as ComfyWorkflowTemplate;
	workflowCache.set(imageStyle, parsed);
	return parsed;
}

function applyTemplateValues(
	value: unknown,
	replacements: Record<string, string | number>
): unknown {
	if (typeof value === 'string') {
		return value in replacements ? replacements[value] : value;
	}
	if (Array.isArray(value)) {
		return value.map((item) => applyTemplateValues(item, replacements));
	}
	if (value && typeof value === 'object') {
		return Object.fromEntries(
			Object.entries(value).map(([key, child]) => [key, applyTemplateValues(child, replacements)])
		);
	}
	return value;
}

function extractHistoryEntry(body: unknown, promptId: string): ComfyHistoryEntry {
	if (body && typeof body === 'object' && promptId in body) {
		return (body as Record<string, ComfyHistoryEntry>)[promptId];
	}
	return (body || {}) as ComfyHistoryEntry;
}

function extractOutputImage(entry: ComfyHistoryEntry, outputNodeId: string) {
	const direct = entry.outputs?.[outputNodeId]?.images?.[0];
	if (direct) {
		return direct;
	}

	for (const output of Object.values(entry.outputs || {})) {
		if (output.images?.length) {
			return output.images[0];
		}
	}

	return null;
}

async function startAutomatic1111Generation(
	request: ImageGenerationRequest
): Promise<QueuedGenerationTask> {
	const imageStyle = request.image_style || style;
	if (imageStyle !== style) {
		await init_style(imageStyle);
	}

	const params = buildParams(request);

	return {
		provider: backend,
		providerJobId: null,
		waitForResult: async () => {
			const response = await fetch(sdUrl('txt2img'), {
				method: 'POST',
				body: JSON.stringify({
					prompt: params.prompt,
					negative_prompt: params.negative_prompt,
					num_inference_steps: steps,
					height: params.height,
					width: params.width,
					seed: params.seed,
					cfg_scale: params.cfg_scale,
					steps,
					restore_faces: true
				}),
				headers: jsonHeaders()
			});

			if (!response.ok) {
				throw new Error(`Automatic1111 txt2img failed with ${response.status}`);
			}

			const body = await response.json();
			return {
				params,
				data: base64Decode(body.images[0]),
				providerMetadata: body.info ? { info: body.info } : undefined
			};
		}
	};
}

async function startComfyGeneration(
	request: ImageGenerationRequest
): Promise<QueuedGenerationTask> {
	const imageStyle = request.image_style || style;
	const params = buildParams(request);
	const template = await readWorkflowTemplate(imageStyle);
	const filenamePrefix = `sparklai-${imageStyle}-${Date.now()}`;
	const replacements = {
		__MODEL__: styles[imageStyle].model,
		__POSITIVE_PROMPT__: params.prompt,
		__NEGATIVE_PROMPT__: params.negative_prompt,
		__WIDTH__: params.width,
		__HEIGHT__: params.height,
		__SEED__: params.seed,
		__STEPS__: steps,
		__CFG_SCALE__: params.cfg_scale,
		__FILENAME_PREFIX__: filenamePrefix
	};
	const promptGraph = applyTemplateValues(template.prompt, replacements);
	const clientId = randomUUID();
	const response = await fetch(sdUrl('prompt'), {
		method: 'POST',
		body: JSON.stringify({
			prompt: promptGraph,
			client_id: clientId
		}),
		headers: jsonHeaders()
	});

	if (!response.ok) {
		throw new Error(`ComfyUI prompt submission failed with ${response.status}`);
	}

	const body = await response.json();
	const promptId = body.prompt_id as string | undefined;
	if (!promptId) {
		throw new Error('ComfyUI did not return a prompt_id');
	}

	return {
		provider: backend,
		providerJobId: promptId,
		providerMetadata: {
			clientId,
			outputNodeId: template.output_node_id,
			filenamePrefix
		},
		waitForResult: async () => {
			const deadline = Date.now() + comfyTimeoutMs;

			while (Date.now() < deadline) {
				const historyResponse = await fetch(sdUrl(`history/${promptId}`));
				if (!historyResponse.ok) {
					throw new Error(`ComfyUI history lookup failed with ${historyResponse.status}`);
				}

				const historyBody = await historyResponse.json();
				const entry = extractHistoryEntry(historyBody, promptId);
				if (entry.status?.status_str === 'error') {
					throw new Error('ComfyUI workflow execution failed');
				}

				const image = extractOutputImage(entry, template.output_node_id);
				if (image) {
					const imageUrl = new URL(sdUrl('view'));
					imageUrl.searchParams.set('filename', image.filename);
					imageUrl.searchParams.set('subfolder', image.subfolder || '');
					imageUrl.searchParams.set('type', image.type || 'output');
					const imageResponse = await fetch(imageUrl);
					if (!imageResponse.ok) {
						throw new Error(`ComfyUI image fetch failed with ${imageResponse.status}`);
					}

					return {
						params,
						data: new Uint8Array(await imageResponse.arrayBuffer()),
						providerMetadata: {
							promptId,
							outputNodeId: template.output_node_id,
							image,
							status: entry.status,
							meta: entry.meta
						}
					};
				}

				await delay(comfyPollIntervalMs);
			}

			throw new Error(`ComfyUI workflow timed out after ${comfyTimeoutMs}ms`);
		}
	};
}

export async function init(new_model: string | null = null) {
	model = new_model || model;
	if (backend !== 'automatic1111') {
		return;
	}

	await fetch(sdUrl('options'), {
		method: 'POST',
		body: JSON.stringify({
			sd_model_checkpoint: model,
			samples_format: format
		}),
		headers: jsonHeaders()
	});
}

export async function init_style(new_style: SDStyle) {
	style = new_style;
	if (backend === 'automatic1111') {
		await init(styles[style].model || null);
	}
}

export function supportsModelSelection() {
	return backend === 'automatic1111';
}

export async function fetch_models(): Promise<SDModel[]> {
	if (backend !== 'automatic1111') {
		return [];
	}

	try {
		const response = await fetch(sdUrl('sd-models'));
		if (!response.ok) {
			throw new Error(`Stable Diffusion model fetch failed with ${response.status}`);
		}
		return await response.json();
	} catch {
		return [];
	}
}

export async function startGeneration(
	request: ImageGenerationRequest
): Promise<QueuedGenerationTask> {
	if (backend === 'comfyui') {
		return startComfyGeneration(request);
	}

	return startAutomatic1111Generation(request);
}

export async function txt2img(
	prompt: string,
	negative_prompt: string | null = null,
	width = 512,
	height = 512,
	include_default_prompt = true,
	image_style: SDStyle = 'photo'
) {
	const task = await startGeneration({
		prompt,
		negative_prompt,
		width,
		height,
		include_default_prompt,
		image_style
	});
	return task.waitForResult();
}

export async function options() {
	if (backend !== 'automatic1111') {
		return {
			backend,
			style,
			model,
			supports_model_selection: supportsModelSelection()
		};
	}

	const response = await fetch(sdUrl('options'));
	return await response.json();
}

export async function unload() {
	if (backend === 'automatic1111') {
		await fetch(sdUrl('unload'), { method: 'POST' });
	}
}

export async function reload() {
	if (backend === 'automatic1111') {
		await fetch(sdUrl('reload'), { method: 'POST' });
	}
}

export type {
	ImageGenerationRequest,
	QueuedGenerationTask,
	SDBackend,
	SDModel,
	SDStyle,
	StableDiffusionParams
} from './types';
