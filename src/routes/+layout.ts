// This is a pure client-rendered SPA (see svelte.config.js / BACKEND_MIGRATION.md): FastAPI
// serves the built static output and /api/* from the same origin in production, so there's never
// a server process to SSR against there. `vite dev`, however, *does* run a real SSR server unless
// told not to — and load functions' relative fetch('/api/...') calls then execute server-side,
// where they get resolved against the request's public origin and fail trying to loop back over
// the network instead of hitting Vite's `/api` dev proxy. Disabling ssr keeps dev consistent with
// how the app actually runs everywhere else: load functions only ever run in the browser.
export const ssr = false;
