import { env } from '$env/dynamic/private';

if (!env.SD_URL) throw new Error('SD_URL is not set');

export let model = env.SD_PHOTO_MODEL;
const steps = 20;
const format = 'webp';

export const styles = {
	photo: {
		model: env.SD_PHOTO_MODEL,
		prompt: env.SD_PHOTO_PROMPT,
		negative_prompt: env.SD_PHOTO_NEGATIVE_PROMPT
	},
	drawing: {
		model: env.SD_DRAWING_MODEL,
		prompt: env.SD_DRAWING_PROMPT,
		negative_prompt: env.SD_DRAWING_NEGATIVE_PROMPT
	},
	stylized: {
		model: env.SD_STYLIZED_MODEL,
		prompt: env.SD_STYLIZED_PROMPT,
		negative_prompt: env.SD_STYLIZED_NEGATIVE_PROMPT
	}
};
export let style: keyof typeof styles = 'photo';

// Only properties we actually care about will be defined here:
export type StableDiffusionParams = {
	prompt: string;
	negative_prompt: string;
	width: number;
	height: number;
	cfg_scale: number;
	seed: number;
};

export async function init(new_model: string | null = null) {
	await fetch(`${env.SD_URL}options`, {
		method: 'POST',
		body: JSON.stringify({
			sd_model_checkpoint: new_model || model,
			samples_format: format
		}),
		headers: {
			'Content-Type': 'application/json'
		}
	});
	model = new_model || model;
}

export async function init_style(new_style: typeof style) {
	style = new_style;
	await init(styles[style].model);
}

type SDModel = {
	title: string;
	model_name: string;
	hash: string;
};
export async function fetch_models(): Promise<SDModel[]> {
	try {
		const response = await fetch(`${env.SD_URL}sd-models`);
		return await response.json();
	} catch {
		return [];
	}
}

export type SDImage = {
	params: StableDiffusionParams;
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
	height = 512,
	include_default_prompt = true
) {
	const data = {
		prompt: include_default_prompt ? `${prompt}\n${styles[style].prompt}` : prompt,
		negative_prompt: negative_prompt
			? include_default_prompt
				? `${negative_prompt}\n${styles[style].negative_prompt}`
				: negative_prompt
			: include_default_prompt
				? styles[style].negative_prompt
				: '',
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
