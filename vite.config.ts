import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import Icons from 'unplugin-icons/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit(),
		Icons({
			compiler: 'svelte'
		})
	],
	server: {
		allowedHosts: true,
		watch: {
			ignored: ['**/*.db', '**/*.db-wal', '**/*.db-shm']
		},
		// Routes ported to the FastAPI backend (creators/auth, posts, users CRUD/create/import,
		// comments, chat/messenger, dream/memory, image generation/image-jobs, model preferences,
		// images/media blob serving — see BACKEND_MIGRATION.md) live under /api and are proxied
		// there in dev. Override with BACKEND_URL if FastAPI isn't running on the default port.
		proxy: {
			'/api': {
				target: process.env.BACKEND_URL ?? 'http://127.0.0.1:8000',
				changeOrigin: true
			}
		}
	}
});
