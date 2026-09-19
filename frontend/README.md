# Sparkl Chat front end

A SvelteKit app built as a static SPA (`@sveltejs/adapter-static`, SPA mode) that
talks to the FastAPI backend under `/api`.

## Development

Run the API and the Vite dev server side by side:

```bash
uv run fastapi dev          # API on http://127.0.0.1:8000
npm run dev                 # app on http://127.0.0.1:5173
```

Vite proxies `/api` to the backend (see `vite.config.ts`), so the browser only
ever talks to one origin.

## Production build

```bash
npm install
npm run build               # emits build/index.html + hashed assets
```

FastAPI serves `build/` when it exists, so a plain `uv run fastapi run` hosts
both the API and the app.

## Checks

```bash
npm run check               # svelte-check + TypeScript
```
