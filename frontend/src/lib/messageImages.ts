// Generated images are served from an authenticated endpoint, so they cannot be
// used as a plain `<img src="/api/...">`. Fetch the bytes with the bearer token
// and keep one object URL per message/index/version (message ids can be reused
// after a delete, so the file's version is part of the key) for the life of the page.
import { fetchMessageImage } from './api';

const urls = new Map<string, string>();
const inflight = new Map<string, Promise<string>>();

function key(sessionId: number, messageId: number, index: number, version: string): string {
	return `${sessionId}:${messageId}:${index}:${version}`;
}

export function cachedMessageImage(
	sessionId: number,
	messageId: number,
	index: number,
	version: string
): string | null {
	return urls.get(key(sessionId, messageId, index, version)) ?? null;
}

export function loadMessageImage(
	token: string,
	sessionId: number,
	messageId: number,
	index: number,
	version: string
): Promise<string> {
	const cacheKey = key(sessionId, messageId, index, version);
	const cached = urls.get(cacheKey);
	if (cached) return Promise.resolve(cached);

	const pending = inflight.get(cacheKey);
	if (pending) return pending;

	const request = fetchMessageImage(token, sessionId, messageId, index, version)
		.then((blob) => {
			const url = URL.createObjectURL(blob);
			urls.set(cacheKey, url);
			return url;
		})
		.finally(() => {
			inflight.delete(cacheKey);
		});

	inflight.set(cacheKey, request);
	return request;
}
