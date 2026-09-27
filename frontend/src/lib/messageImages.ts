// Generated images are served from an authenticated endpoint, so they cannot be
// used as a plain `<img src="/api/...">`. Fetch the bytes with the bearer token
// and keep one object URL per message/index for the life of the page.
import { fetchMessageImage } from './api';

const urls = new Map<string, string>();
const inflight = new Map<string, Promise<string>>();

function key(sessionId: number, messageId: number, index: number): string {
	return `${sessionId}:${messageId}:${index}`;
}

export function cachedMessageImage(sessionId: number, messageId: number, index: number): string | null {
	return urls.get(key(sessionId, messageId, index)) ?? null;
}

export function loadMessageImage(
	token: string,
	sessionId: number,
	messageId: number,
	index: number
): Promise<string> {
	const cacheKey = key(sessionId, messageId, index);
	const cached = urls.get(cacheKey);
	if (cached) return Promise.resolve(cached);

	const pending = inflight.get(cacheKey);
	if (pending) return pending;

	const request = fetchMessageImage(token, sessionId, messageId, index)
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
