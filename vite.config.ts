import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import Icons from 'unplugin-icons/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			// Consult https://svelte.dev/docs/kit/integrations
			// for more information about preprocessors
			preprocess: vitePreprocess(),

			// Pure static SPA now that every route is either a prerenderable-by-default page or a
			// FastAPI /api/* endpoint. `fallback: 'index.html'` serves that one file for any
			// client-side route FastAPI's SPAStaticFiles doesn't find a real asset for
			// (backend/src/app/spa.py), so deep links / refreshes on e.g. /users/123 still work.
			adapter: adapter({ fallback: 'index.html' })
		}),
		Icons({ compiler: 'svelte' })
	],
	server: {
		allowedHosts: true,
		watch: {
			ignored: ['**/*.db', '**/*.db-wal', '**/*.db-shm']
		},
		// The FastAPI backend (creators/auth, posts, users CRUD/create/import, comments,
		// chat/messenger, dream/memory, image generation/image-jobs, model preferences,
		// images/media blob serving) lives under /api and is proxied there in dev. Override with
		// BACKEND_URL if FastAPI isn't running on the default port.
		proxy: {
			'/api': {
				target: process.env.BACKEND_URL ?? 'http://127.0.0.1:8000',
				changeOrigin: true
			}
		}
	}
});
