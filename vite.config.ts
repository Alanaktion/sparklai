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
		// comments, chat/messenger, images/media blob serving — see BACKEND_MIGRATION.md) live
		// under /api and are proxied there in dev. Everything else under /api (dream, and anything
		// else not yet ported) still falls through to SvelteKit's own dev server. The still-unported
		// bare `/users/*` route (the singular avatar-upload-or-generate `/users/{id}/image`) was
		// never under /api to begin with, so this proxy doesn't touch it at all — no bypass needed.
		// Override with BACKEND_URL if FastAPI isn't running on the default port.
		proxy: {
			'/api': {
				target: process.env.BACKEND_URL ?? 'http://127.0.0.1:8000',
				changeOrigin: true,
				bypass: (req) => {
					if (req.url?.startsWith('/api/users') && /\/dream$/.test(req.url)) {
						return req.url; // not ported yet — let SvelteKit's own route handle it
					}
				}
			}
		}
	}
});
