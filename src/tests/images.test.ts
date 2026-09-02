import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetch_models as fetchChatModels, get_model as getChatModel } from '$lib/server/chat';
import {
	fetch_models as fetchSdModels,
	init as initSdModel,
	init_style as initSdStyle
} from '$lib/server/sd';
import { GET as getModels, POST as setModels } from '../routes/(app)/models/+server';
import { cleanDatabase } from './helpers';

// "POST /users/[id]/image", "POST /posts/[id]/image" (generate + upload), and the image-jobs
// queue moved to the FastAPI backend (backend/tests/test_image_jobs.py,
// backend/tests/test_image_generation_endpoints.py) — see BACKEND_MIGRATION.md. "GET/PATCH/DELETE
// /images/[id]" moved earlier still (backend/tests/test_images_media.py).

function createCookieJar(initial: Record<string, string> = {}) {
	const jar = new Map(Object.entries(initial));

	return {
		get: vi.fn((name: string) => jar.get(name)),
		set: vi.fn((name: string, value: string) => {
			jar.set(name, value);
		}),
		delete: vi.fn((name: string) => {
			jar.delete(name);
		})
	};
}

describe('Models API', () => {
	beforeEach(async () => {
		await cleanDatabase();
	});

	describe('GET /models - list available models', () => {
		it('returns model listing including chat models', async () => {
			const response = await getModels({
				cookies: createCookieJar()
			} as unknown as Parameters<typeof getModels>[0]);

			expect(response.status).toBe(200);
			const body = await response.json();
			expect(body).toHaveProperty('chat_models');
			expect(body).toHaveProperty('chat_model');
			expect(body).toHaveProperty('sd_backend');
			expect(body).toHaveProperty('sd_styles');
			expect(body.chat_models).toEqual([{ id: 'test-model' }]);
			expect(body.chat_model).toBe('test-model');
			expect(body.sd_styles).toContain('sdxl');
		});

		it('prefers valid cookie selections for the active session', async () => {
			vi.mocked(fetchChatModels).mockResolvedValueOnce([{ id: 'test-model' }, { id: 'alt-model' }]);
			vi.mocked(getChatModel).mockResolvedValueOnce('test-model');
			vi.mocked(fetchSdModels).mockResolvedValueOnce([
				{ model_name: 'test-photo', title: 'Test Photo' },
				{ model_name: 'test-sdxl', title: 'Test SDXL' }
			]);

			const response = await getModels({
				cookies: createCookieJar({
					chat_model: 'alt-model',
					sd_style: 'sdxl',
					sd_model: 'test-sdxl'
				})
			} as unknown as Parameters<typeof getModels>[0]);

			const body = await response.json();
			expect(body.chat_model).toBe('alt-model');
			expect(body.sd_style).toBe('sdxl');
			expect(body.sd_model).toBe('test-sdxl');
		});
	});

	describe('POST /models - update model settings', () => {
		it('stores selections in session cookies and updates the backend state', async () => {
			vi.mocked(fetchChatModels).mockResolvedValueOnce([{ id: 'test-model' }, { id: 'new-model' }]);
			vi.mocked(getChatModel).mockResolvedValueOnce('new-model');
			vi.mocked(fetchSdModels).mockResolvedValueOnce([
				{ model_name: 'test-photo', title: 'Test Photo' },
				{ model_name: 'test-sdxl', title: 'Test SDXL' }
			]);
			const cookies = createCookieJar();
			const event = {
				cookies,
				request: new Request('http://localhost/', {
					method: 'POST',
					body: JSON.stringify({ chat_model: 'new-model', sd_style: 'sdxl' }),
					headers: { 'Content-Type': 'application/json' }
				})
			} as unknown as Parameters<typeof setModels>[0];

			const response = await setModels(event);
			expect(response.status).toBe(200);
			expect(cookies.set).toHaveBeenCalledWith(
				'chat_model',
				'new-model',
				expect.objectContaining({ path: '/' })
			);
			expect(cookies.set).toHaveBeenCalledWith(
				'sd_style',
				'sdxl',
				expect.objectContaining({ path: '/' })
			);
			expect(cookies.delete).toHaveBeenCalledWith('sd_model', { path: '/' });
			expect(vi.mocked(initSdStyle)).toHaveBeenCalledWith('sdxl');
		});

		it('stores manual model overrides separately from style selection', async () => {
			vi.mocked(fetchSdModels).mockResolvedValueOnce([
				{ model_name: 'test-photo', title: 'Test Photo' },
				{ model_name: 'custom-xl', title: 'Custom XL' }
			]);
			const cookies = createCookieJar({ chat_model: 'test-model', sd_style: 'sdxl' });

			const response = await setModels({
				cookies,
				request: new Request('http://localhost/', {
					method: 'POST',
					body: JSON.stringify({ chat_model: 'test-model', sd_model: 'custom-xl' }),
					headers: { 'Content-Type': 'application/json' }
				})
			} as unknown as Parameters<typeof setModels>[0]);

			expect(response.status).toBe(200);
			expect(cookies.set).toHaveBeenCalledWith(
				'sd_model',
				'custom-xl',
				expect.objectContaining({ path: '/' })
			);
			expect(vi.mocked(initSdModel)).toHaveBeenCalledWith('custom-xl');
		});
	});
});
