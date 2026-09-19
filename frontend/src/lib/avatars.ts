// Avatars are served from an authenticated endpoint, so they cannot be used as
// a plain `<img src="/api/...">`. Fetch the bytes with the bearer token and keep
// one object URL per character for the life of the page.
import { fetchAvatar } from './api';

const urls = new Map<number, string>();
const inflight = new Map<number, Promise<string>>();

export function cachedAvatar(id: number): string | null {
	return urls.get(id) ?? null;
}

export function loadAvatar(id: number, token: string): Promise<string> {
	const cached = urls.get(id);
	if (cached) return Promise.resolve(cached);

	const pending = inflight.get(id);
	if (pending) return pending;

	const request = fetchAvatar(token, id)
		.then((blob) => {
			const url = URL.createObjectURL(blob);
			urls.set(id, url);
			return url;
		})
		.finally(() => {
			inflight.delete(id);
		});

	inflight.set(id, request);
	return request;
}
