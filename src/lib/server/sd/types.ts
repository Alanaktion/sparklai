export const sdStyleNames = ['photo', 'drawing', 'stylized'] as const;

export type SDStyle = (typeof sdStyleNames)[number];
export type SDBackend = 'automatic1111' | 'comfyui';
export type ImageGenerationJobStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type ImageGenerationJobTarget = 'user_image' | 'post_image' | 'post_generation';

export type StableDiffusionParams = {
	prompt: string;
	negative_prompt: string;
	width: number;
	height: number;
	cfg_scale: number;
	seed: number;
};

export type SDModel = {
	title: string;
	model_name: string;
	hash?: string;
};

export type SDImage = {
	params: StableDiffusionParams;
	data: Uint8Array;
	providerMetadata?: Record<string, unknown>;
};

export type ImageGenerationRequest = {
	prompt: string;
	negative_prompt?: string | null;
	width: number;
	height: number;
	include_default_prompt?: boolean;
	image_style?: SDStyle;
};

export type QueuedGenerationTask = {
	provider: SDBackend;
	providerJobId: string | null;
	providerMetadata?: Record<string, unknown>;
	waitForResult: () => Promise<SDImage>;
};
