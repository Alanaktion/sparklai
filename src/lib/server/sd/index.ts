import { env } from '$env/dynamic/private';

if (!env.SD_URL) throw new Error('SD_URL is not set');

const model = env.SD_MODEL;
const prompt_suffix = env.SD_PROMPT;
const negative_prompt_suffix = env.SD_NEGATIVE_PROMPT;
const steps = 20;
const format = 'webp';

export async function init() {
	await fetch(`${env.SD_URL}options`, {
		method: 'POST',
		body: JSON.stringify({
			sd_model_checkpoint: model,
			samples_format: format
		}),
		headers: {
			'Content-Type': 'application/json'
		}
	});
}

export type SDImage = {
	params: object;
	data: Uint8Array;
};

export function base64Decode(str: string) {
	const byteCharacters = atob(str);
	const byteNumbers = new Array(byteCharacters.length);
	for (let i = 0; i < byteCharacters.length; i++) {
		byteNumbers[i] = byteCharacters.charCodeAt(i);
	}
	return new Uint8Array(byteNumbers);
}

export async function txt2img(
	prompt: string,
	negative_prompt: string | null = null,
	width = 512,
	height = 512
) {
	const data = {
		prompt: `${prompt}\n${prompt_suffix}`,
		negative_prompt: negative_prompt
			? `${negative_prompt}\n${negative_prompt_suffix}`
			: negative_prompt_suffix,
		num_inference_steps: steps,
		height: height,
		width: width,
		seed: -1,
		cfg_scale: 7,
		steps,
		restore_faces: true
	};
	const response = await fetch(`${env.SD_URL}txt2img`, {
		method: 'POST',
		body: JSON.stringify(data),
		headers: {
			'Content-Type': 'application/json'
		}
	});
	const body = await response.json();
	return <SDImage>{
		params: body.parameters,
		data: base64Decode(body.images[0])
	};
}

export async function options() {
	const response = await fetch(`${env.SD_URL}options`);
	return await response.json();
}

export async function unload() {
	await fetch(`${env.SD_URL}unload`, { method: 'POST' });
}

export async function reload() {
	await fetch(`${env.SD_URL}reload`, { method: 'POST' });
}
