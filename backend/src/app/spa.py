"""Serves the built Svelte SPA with client-side-routing fallback.

`@sveltejs/adapter-static`'s `fallback: 'index.html'` mode (see `svelte.config.js`) produces one
`index.html` designed to bootstrap the app for *any* route and let SvelteKit's own client-side
router take over from there — the same idea as an nginx `try_files ... /index.html` rule or a
Netlify `/* /index.html 200` redirect. Starlette's plain `StaticFiles(html=True)` doesn't do this:
it only serves `index.html` for an exact directory request, and 404s for anything else that isn't
a literal file on disk — so a deep link or a refresh on e.g. `/users/123` or `/settings` would 404
instead of loading the app. This subclass catches that 404 and retries with `index.html`, which is
what actually gives client-side routes their fallback behavior.

Genuinely missing static assets (a stale/renamed `/_app/immutable/...` chunk, a bad `/favicon.ico`)
fall back to `index.html` too under this scheme rather than 404ing "correctly" — that's an accepted
trade-off of this approach in general, not something specific to this implementation.
"""

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise
