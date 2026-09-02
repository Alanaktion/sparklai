import 'unplugin-icons/types/svelte';
// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			// Still populated by `hooks.server.ts` for routes not yet ported to FastAPI (chat,
			// image jobs, dream, etc. — see BACKEND_MIGRATION.md). Ported routes
			// (creators/auth, posts, users create/import) resolve the active creator client-side
			// via `GET /api/creators/me` instead and don't touch this.
			creator: import('$lib/server/db/schema').CreatorType | null;
		}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
