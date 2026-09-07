import type { PageLoad } from './$types';

// Universal (client-side) load, same convention as `settings/+page.ts` — fetches straight from
// the FastAPI backend since this SPA has no server-side load.
export const load: PageLoad = async ({ fetch }) => {
	const [bundleRes, activityRes] = await Promise.all([
		fetch('/api/auto-mode'),
		fetch('/api/auto-mode/activity')
	]);
	return {
		bundle: bundleRes.ok ? await bundleRes.json() : null,
		activity: activityRes.ok ? (await activityRes.json()).items : []
	};
};
