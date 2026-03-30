import { beforeEach, describe, expect, it, vi } from 'vitest';

const fetchMock = vi.fn<typeof fetch>();

type MockResponseInit = {
	status?: number;
	headers?: Record<string, string>;
};

function jsonResponse(body: unknown, init: MockResponseInit = {}) {
	return new Response(JSON.stringify(body), {
		status: init.status ?? 200,
		headers: {
			'Content-Type': 'application/json',
			...(init.headers || {})
		}
	});
}

function binaryResponse(data: Uint8Array, init: MockResponseInit = {}) {
	return new Response(Buffer.from(data), {
		status: init.status ?? 200,
		headers: {
			'Content-Type': 'image/png',
			...(init.headers || {})
		}
	});
}

async function loadComfyModule() {
	vi.resetModules();
	vi.doMock('$env/dynamic/private', () => ({
		env: {
			SD_URL: 'http://localhost:8188/',
			SD_BACKEND: 'comfyui',
			SD_PHOTO_MODEL: 'test-photo-model.safetensors',
			SD_PHOTO_PROMPT: 'photo default prompt',
			SD_PHOTO_NEGATIVE_PROMPT: 'photo default negative prompt',
			SD_DRAWING_MODEL: 'test-drawing-model.safetensors',
			SD_DRAWING_PROMPT: 'drawing default prompt',
			SD_DRAWING_NEGATIVE_PROMPT: 'drawing default negative prompt',
			SD_STYLIZED_MODEL: 'test-stylized-model.safetensors',
			SD_STYLIZED_PROMPT: 'stylized default prompt',
			SD_STYLIZED_NEGATIVE_PROMPT: 'stylized default negative prompt',
			SD_COMFY_POLL_INTERVAL_MS: '1',
			SD_COMFY_TIMEOUT_MS: '50'
		}
	}));
	vi.doMock('$lib/server/sd', async () => {
		const actual = await import('../lib/server/sd/index');
		return actual;
	});

	globalThis.fetch = fetchMock;
	return import('$lib/server/sd');
}

describe('ComfyUI SD backend request/response flow', () => {
	beforeEach(() => {
		fetchMock.mockReset();
	});

	it('submits prompt, polls history, and fetches output image', async () => {
		fetchMock
			.mockResolvedValueOnce(jsonResponse({ prompt_id: 'prompt-123' }))
			.mockResolvedValueOnce(
				jsonResponse({
					'prompt-123': {
						outputs: {
							'51': {
								images: [
									{
										filename: 'image_0001.png',
										subfolder: 'sparklai',
										type: 'output'
									}
								]
							}
						},
						status: { status_str: 'success', completed: true }
					}
				})
			)
			.mockResolvedValueOnce(binaryResponse(new Uint8Array([1, 2, 3, 4])));

		const sd = await loadComfyModule();
		const result = await sd.txt2img('test prompt', 'test negative', 640, 768, true, 'photo');

		expect(result.data.byteLength).toBe(4);
		expect(result.providerMetadata).toMatchObject({
			promptId: 'prompt-123',
			outputNodeId: '51'
		});

		expect(fetchMock).toHaveBeenCalledTimes(3);
		expect(fetchMock.mock.calls[0]?.[0]).toBe('http://localhost:8188/prompt');
		expect(fetchMock.mock.calls[1]?.[0]).toBe('http://localhost:8188/history/prompt-123');

		const promptRequest = fetchMock.mock.calls[0]?.[1] as RequestInit;
		expect(promptRequest.method).toBe('POST');
		expect(promptRequest.headers).toMatchObject({ 'Content-Type': 'application/json' });

		const parsedBody = JSON.parse(promptRequest.body as string) as {
			prompt?: Record<string, unknown>;
			client_id?: string;
		};
		expect(parsedBody.prompt).toBeDefined();
		expect(Object.keys(parsedBody.prompt || {}).length).toBeGreaterThan(0);
		expect(typeof parsedBody.client_id).toBe('string');

		const imageFetchUrl = fetchMock.mock.calls[2]?.[0] as URL;
		expect(imageFetchUrl.pathname).toBe('/view');
		expect(imageFetchUrl.searchParams.get('filename')).toBe('image_0001.png');
		expect(imageFetchUrl.searchParams.get('subfolder')).toBe('sparklai');
		expect(imageFetchUrl.searchParams.get('type')).toBe('output');
	});

	it('supports direct history entry format (non-keyed body)', async () => {
		fetchMock
			.mockResolvedValueOnce(jsonResponse({ prompt_id: 'prompt-direct' }))
			.mockResolvedValueOnce(
				jsonResponse({
					outputs: {
						other_node: {
							images: [
								{
									filename: 'direct.png',
									subfolder: '',
									type: 'output'
								}
							]
						}
					}
				})
			)
			.mockResolvedValueOnce(binaryResponse(new Uint8Array([9, 9, 9])));

		const sd = await loadComfyModule();
		const result = await sd.txt2img('direct entry prompt', null, 512, 512, true, 'photo');

		expect(result.data.byteLength).toBe(3);
		expect(fetchMock).toHaveBeenCalledTimes(3);
	});

	it('throws when prompt submission fails', async () => {
		fetchMock.mockResolvedValueOnce(jsonResponse({ error: 'bad request' }, { status: 400 }));

		const sd = await loadComfyModule();
		await expect(sd.txt2img('test prompt')).rejects.toThrow(
			'ComfyUI prompt submission failed with 400'
		);
	});

	it('throws when prompt submission does not return prompt_id', async () => {
		fetchMock.mockResolvedValueOnce(jsonResponse({ number: 12 }));

		const sd = await loadComfyModule();
		await expect(sd.txt2img('test prompt')).rejects.toThrow('ComfyUI did not return a prompt_id');
	});

	it('throws when history reports error status', async () => {
		fetchMock
			.mockResolvedValueOnce(jsonResponse({ prompt_id: 'prompt-error' }))
			.mockResolvedValueOnce(
				jsonResponse({
					'prompt-error': {
						status: { status_str: 'error' }
					}
				})
			);

		const sd = await loadComfyModule();
		await expect(sd.txt2img('test prompt')).rejects.toThrow('ComfyUI workflow execution failed');
	});

	it('throws when history never yields an image before timeout', async () => {
		fetchMock
			.mockResolvedValueOnce(jsonResponse({ prompt_id: 'prompt-timeout' }))
			.mockImplementation(async () =>
				jsonResponse({
					'prompt-timeout': {
						status: { status_str: 'running', completed: false },
						outputs: {}
					}
				})
			);

		const sd = await loadComfyModule();
		await expect(sd.txt2img('timeout prompt')).rejects.toThrow(
			'ComfyUI workflow timed out after 50ms'
		);
		expect(
			fetchMock.mock.calls.some((call) => String(call[0]).includes('/history/prompt-timeout'))
		).toBe(true);
	});
});
