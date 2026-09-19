// SPA mode: nothing is rendered or prerendered on the server, so every route is
// handled by the client and the static adapter emits `index.html` as the
// fallback that FastAPI serves for deep links.
export const ssr = false;
export const prerender = false;
