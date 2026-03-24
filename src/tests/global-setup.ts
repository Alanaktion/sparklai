import { execFileSync } from 'child_process';
import { existsSync, unlinkSync } from 'fs';
import { resolve } from 'path';

const TEST_DB_PATH = resolve('./test.db');
export const TEST_DATABASE_URL = `file:${TEST_DB_PATH}`;

export function setup() {
	// Set environment variables so worker processes inherit them
	process.env.DATABASE_URL = TEST_DATABASE_URL;
	process.env.CHAT_URL = 'http://localhost:11434/v1/';
	process.env.CHAT_MODEL = 'test-model';
	process.env.SD_URL = 'http://localhost:7860/';
	process.env.SD_BACKEND = 'automatic1111';
	process.env.SD_PHOTO_MODEL = 'test-photo';
	process.env.SD_PHOTO_PROMPT = '';
	process.env.SD_PHOTO_NEGATIVE_PROMPT = '';
	process.env.SD_DRAWING_MODEL = 'test-drawing';
	process.env.SD_DRAWING_PROMPT = '';
	process.env.SD_DRAWING_NEGATIVE_PROMPT = '';
	process.env.SD_STYLIZED_MODEL = 'test-stylized';
	process.env.SD_STYLIZED_PROMPT = '';
	process.env.SD_STYLIZED_NEGATIVE_PROMPT = '';

	// Remove any existing test database for a clean start
	if (existsSync(TEST_DB_PATH)) {
		unlinkSync(TEST_DB_PATH);
	}

	// Create the test database schema using drizzle-kit push
	execFileSync('pnpm', ['exec', 'drizzle-kit', 'push', '--config=drizzle.test.config.ts'], {
		env: { ...process.env, DATABASE_URL: TEST_DATABASE_URL },
		stdio: 'pipe'
	});
}

export function teardown() {
	if (existsSync(TEST_DB_PATH)) {
		unlinkSync(TEST_DB_PATH);
	}
}
