import { sveltekit } from '@sveltejs/kit/vite';
import Icons from 'unplugin-icons/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit(), Icons({ compiler: 'svelte' })],
	test: {
		include: ['src/tests/**/*.test.ts'],
		environment: 'node',
		globalSetup: './src/tests/global-setup.ts',
		setupFiles: ['./src/tests/setup.ts'],
		fileParallelism: false,
		clearMocks: true
	}
});
