import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://svelte.dev/docs/kit/integrations
	// for more information about preprocessors
	preprocess: vitePreprocess(),

	kit: {
		// Pure static SPA now that every route is either a prerenderable-by-default page or a
		// FastAPI /api/* endpoint — see BACKEND_MIGRATION.md. `fallback: 'index.html'` serves that
		// one file for any client-side route FastAPI's SPAStaticFiles doesn't find a real asset
		// for (backend/src/app/spa.py), so deep links / refreshes on e.g. /users/123 still work.
		adapter: adapter({
			fallback: 'index.html'
		})
	}
};

export default config;
