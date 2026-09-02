import type { PostType, UserType } from '$lib/server/db/schema';
import type { PageLoad } from './$types';

const INITIAL_POSTS_LIMIT = 15;

// Universal (client-side) load, replacing `+page.server.ts` — same shape, now backed by the
// FastAPI endpoints instead of a direct DB query.
export const load: PageLoad = async ({ fetch, parent }) => {
	const { activeCreator } = await parent();
	if (!activeCreator) {
		return { posts: [] as PostType[], hasMorePosts: false, users: [] as UserType[] };
	}

	const [postsRes, usersRes] = await Promise.all([
		fetch(`/api/posts?limit=${INITIAL_POSTS_LIMIT}`),
		fetch('/api/users')
	]);

	const postsBody: { posts: PostType[]; hasMore: boolean } = postsRes.ok
		? await postsRes.json()
		: { posts: [], hasMore: false };
	const users: UserType[] = usersRes.ok ? await usersRes.json() : [];

	return { posts: postsBody.posts, hasMorePosts: postsBody.hasMore, users };
};
