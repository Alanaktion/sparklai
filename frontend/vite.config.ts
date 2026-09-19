import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// Development: `vite dev` serves the app on :5173 and forwards `/api` to the
// FastAPI backend on :8000, so the browser sees a single origin.
// Production: `vite build` emits a static SPA into `build/`, which FastAPI
// serves from the same origin as the API (see src/sparklchat/main.py).
const backendUrl = 'http://127.0.0.1:8000';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// Static SPA: `build/index.html` plus hashed assets. The fallback page
			// is what FastAPI returns for client-side routes such as /characters/5.
			adapter: adapter({ fallback: 'index.html' })
		})
	],
	server: {
		proxy: {
			'/api': {
				target: backendUrl,
				changeOrigin: true
			}
		}
	}
});
