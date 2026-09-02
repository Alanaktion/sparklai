import { vi } from 'vitest';

// Mock environment variables - this must run before any server modules are imported.
// The factory reads from process.env, which is set in global-setup.ts.
vi.mock('$env/dynamic/private', () => ({
	env: {
		DATABASE_URL: process.env.DATABASE_URL || 'file:./test.db',
		CHAT_URL: process.env.CHAT_URL || 'http://localhost:11434/v1/',
		CHAT_MODEL: process.env.CHAT_MODEL || 'test-model',
		CHAT_API_KEY: undefined,
		SD_URL: process.env.SD_URL || 'http://localhost:7860/',
		SD_BACKEND: process.env.SD_BACKEND || 'automatic1111',
		SD_PHOTO_MODEL: process.env.SD_PHOTO_MODEL || 'test-photo',
		SD_PHOTO_PROMPT: process.env.SD_PHOTO_PROMPT || '',
		SD_PHOTO_NEGATIVE_PROMPT: process.env.SD_PHOTO_NEGATIVE_PROMPT || '',
		SD_DRAWING_MODEL: process.env.SD_DRAWING_MODEL || 'test-drawing',
		SD_DRAWING_PROMPT: process.env.SD_DRAWING_PROMPT || '',
		SD_DRAWING_NEGATIVE_PROMPT: process.env.SD_DRAWING_NEGATIVE_PROMPT || '',
		SD_STYLIZED_MODEL: process.env.SD_STYLIZED_MODEL || 'test-stylized',
		SD_STYLIZED_PROMPT: process.env.SD_STYLIZED_PROMPT || '',
		SD_STYLIZED_NEGATIVE_PROMPT: process.env.SD_STYLIZED_NEGATIVE_PROMPT || '',
		SD_SDXL_MODEL: process.env.SD_SDXL_MODEL || 'test-sdxl',
		SD_SDXL_PROMPT: process.env.SD_SDXL_PROMPT || '',
		SD_SDXL_NEGATIVE_PROMPT: process.env.SD_SDXL_NEGATIVE_PROMPT || ''
	}
}));

// Mock the chat module - provides fake AI completions without calling an LLM
vi.mock('$lib/server/chat', () => ({
	model: 'test-model',
	schema_completion: vi.fn(),
	completion: vi.fn(),
	fetch_models: vi.fn().mockResolvedValue([{ id: 'test-model' }]),
	get_model: vi.fn().mockResolvedValue('test-model'),
	init: vi.fn()
}));

// Mock the SD module - provides fake image generation settings
vi.mock('$lib/server/sd', () => ({
	backend: 'automatic1111',
	model: 'test-photo',
	style: 'photo',
	styles: {
		photo: { model: 'test-photo', prompt: '', negative_prompt: '' },
		drawing: { model: 'test-drawing', prompt: '', negative_prompt: '' },
		stylized: { model: 'test-stylized', prompt: '', negative_prompt: '' },
		sdxl: { model: 'test-sdxl', prompt: '', negative_prompt: '' }
	},
	fetch_models: vi.fn().mockResolvedValue([]),
	init: vi.fn(),
	init_style: vi.fn(),
	supportsModelSelection: vi.fn().mockReturnValue(true)
}));

// `$lib/server/sd/jobs` (the image-generation job queue) and `$lib/server/image-utils` (toWebp)
// no longer have any SvelteKit-side consumers — both ported to the FastAPI backend (see
// BACKEND_MIGRATION.md) — so their mocks were removed along with the modules themselves.
