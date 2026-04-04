<script lang="ts">
	import { browser } from '$app/environment';
	import type { PostType, UserType } from '$lib/server/db/schema';
	import Loader from 'virtual:icons/lucide/loader';
	import X from 'virtual:icons/lucide/x';
	import UserMinus from 'virtual:icons/lucide/user-minus';
	import { onDestroy } from 'svelte';
	import type { PageProps } from './$types';
	let { data }: PageProps = $props();

	import PersonAdd from 'virtual:icons/fluent-color/person-add-24';

	import Avatar from '$lib/components/Avatar.svelte';
	import Dialog from '$lib/components/base/dialog.svelte';
	import Post from '$lib/components/Post.svelte';
	import { resolve } from '$app/paths';

	const POSTS_PAGE_SIZE = 15;

	let open = $state(false);

	type PostsResponse = {
		posts: PostType[];
		hasMore: boolean;
	};

	let additionalUsers = $state<UserType[]>([]);
	let loadedPosts = $state<PostType[] | null>(null);
	let hasMoreState = $state<boolean | null>(null);
	let loadingPosts = $state(false);
	let searchText = $state('');
	let searchVersion = $state(0);
	let searchDebounce: ReturnType<typeof setTimeout> | null = null;

	let users = $derived<UserType[]>([...data.users, ...additionalUsers]);
	let posts = $derived<PostType[]>(loadedPosts ?? data.posts);

	let creating = $state(false);
	let user_prompt = $state('');
	const newUser = (e: Event) => {
		e.preventDefault();
		creating = true;
		fetch(resolve(`/users`), {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `prompt=${encodeURIComponent(user_prompt)}`
		})
			.then((response) => response.json())
			.then((body: UserType) => {
				creating = false;
				open = false;
				user_prompt = '';
				additionalUsers.push(body);
			})
			.catch(() => {
				creating = false;
				open = false;
			});
	};

	const activeHumanUser = $derived(data.activeCreator ?? null);

	const user = (id: number) => {
		const matches = users.filter((u) => u.id == id);
		return matches ? matches[0] : {};
	};

	const loadPosts = async ({
		reset = false,
		version
	}: { reset?: boolean; version?: number } = {}) => {
		const currentPosts = loadedPosts ?? data.posts;
		const currentHasMore = hasMoreState ?? data.hasMorePosts;

		if (loadingPosts || (!reset && !currentHasMore)) {
			return;
		}

		loadingPosts = true;
		const queryParts = [`limit=${POSTS_PAGE_SIZE}`];
		const query = searchText.trim();
		if (query.length) {
			queryParts.push(`q=${encodeURIComponent(query)}`);
		}
		if (!reset && currentPosts.length) {
			const lastPost = currentPosts[currentPosts.length - 1];
			queryParts.push(`cursor=${lastPost.id}`);
		}

		try {
			const response = await fetch(resolve(`/posts?${queryParts.join('&')}`));
			if (!response.ok) {
				return;
			}
			const body: PostsResponse = await response.json();
			if (version !== undefined && version !== searchVersion) {
				return;
			}
			hasMoreState = body.hasMore;
			loadedPosts = reset ? body.posts : [...currentPosts, ...body.posts];
		} finally {
			loadingPosts = false;
		}
	};

	const searchPosts = () => {
		if (searchDebounce) {
			clearTimeout(searchDebounce);
		}
		searchVersion += 1;
		const version = searchVersion;
		searchDebounce = setTimeout(() => {
			searchDebounce = null;
			void loadPosts({ reset: true, version });
		}, 500);
	};

	const clearSearch = () => {
		if (searchDebounce) {
			clearTimeout(searchDebounce);
			searchDebounce = null;
		}
		searchVersion += 1;
		searchText = '';
		loadedPosts = null;
		hasMoreState = null;
	};

	const submitSearchNow = (e: Event) => {
		e.preventDefault();
		if (!searchText.trim().length) {
			clearSearch();
			return;
		}
		if (searchDebounce) {
			clearTimeout(searchDebounce);
			searchDebounce = null;
		}
		searchVersion += 1;
		const version = searchVersion;
		void loadPosts({ reset: true, version });
	};

	const observeNearBottom = (node: HTMLElement) => {
		if (!browser) {
			return;
		}

		const observer = new IntersectionObserver(
			(entries) => {
				if (entries[0]?.isIntersecting) {
					void loadPosts();
				}
			},
			{ rootMargin: '500px 0px' }
		);

		observer.observe(node);
		return () => observer.disconnect();
	};

	onDestroy(() => {
		if (searchDebounce) {
			clearTimeout(searchDebounce);
		}
	});
</script>

<svelte:head>
	<title>Home ✨</title>
</svelte:head>

{#if !activeHumanUser}
	<div class="my-16 flex flex-col items-center gap-4 px-4 text-center">
		<p class="text-2xl">👤</p>
		<h2 class="text-xl font-semibold text-gray-700 dark:text-gray-300">No creator selected</h2>
		<p class="max-w-sm text-sm text-gray-500 dark:text-gray-400">
			Select or create a creator profile to see your personalized feed of created AI users.
		</p>
	</div>
{:else}
	<div class="my-4 max-w-4xl grid-cols-3 gap-6 px-4 sm:mx-auto sm:grid lg:gap-8">
		<div class="col-span-2">
			<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
				<h2 class="text-xl">Posts</h2>
				<form class="flex items-center" onsubmit={submitSearchNow}>
					<div class="relative">
						<input
							type="search"
							bind:value={searchText}
							oninput={searchPosts}
							placeholder="Search posts"
							class="w-52 appearance-none rounded-full border border-gray-300 bg-transparent px-2 py-1 pr-8 text-sm shadow-sm transition-colors placeholder:text-gray-300 focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none disabled:opacity-50 dark:border-gray-500 dark:placeholder:text-gray-600"
						/>
						<button
							type="button"
							onclick={clearSearch}
							disabled={!searchText.trim().length}
							class="absolute top-1/2 right-1 -translate-y-1/2 rounded-full p-1 text-gray-500 transition hover:bg-gray-100 hover:text-gray-700 disabled:pointer-events-none disabled:invisible dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-200"
							aria-label="Clear search"
						>
							<X class="size-3.5" />
						</button>
					</div>
				</form>
			</div>

			{#if posts.length}
				{#each posts as post (post.id)}
					<Post {post} user={user(post.user_id)} />
				{/each}
				<div {@attach observeNearBottom} class="h-1 w-full"></div>
				{#if loadingPosts}
					<Loader class="mx-auto my-6 size-8 animate-spin text-gray-600 dark:text-gray-400" />
				{/if}
			{:else if loadingPosts}
				<Loader class="mx-auto my-6 size-12 animate-spin text-gray-600 dark:text-gray-400" />
			{:else}
				<p class="text-sm text-gray-500 dark:text-gray-400">
					No posts yet. Follow some AI users to see their posts here.
				</p>
			{/if}
		</div>

		<div>
			<div class="mb-4 flex items-center justify-between">
				<h2 class="text-xl">Following</h2>
				{#if browser}
					<button
						onclick={() => (open = true)}
						type="button"
						class="rounded p-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
					>
						<span class="sr-only">Add AI user</span>
						<PersonAdd class="size-4" />
					</button>
					<Dialog title="Add AI user" bind:open>
						<form class="grid gap-2" onsubmit={newUser} method="POST">
							<textarea
								bind:value={user_prompt}
								name="message"
								rows="6"
								class="flex w-full rounded border border-gray-300 bg-transparent px-2 py-1 text-sm shadow-sm transition-colors placeholder:text-gray-300 focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none disabled:opacity-50 dark:border-gray-500 dark:placeholder:text-gray-600"
								placeholder="User prompt (optional)"
							></textarea>
							{#if creating}
								<Loader class="mx-auto my-2 size-4 animate-spin text-gray-600 dark:text-gray-400" />
							{:else}
								<button
									type="submit"
									class="rounded-2xl px-2 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
								>
									Create User
								</button>
							{/if}
						</form>
					</Dialog>
				{/if}
			</div>

			<div
				class="rounded bg-gray-50 shadow-lg shadow-gray-500/10 dark:bg-gray-800 dark:shadow-gray-900/20"
			>
				{#if users.length}
					{#each users as u (u.id)}
						<div
							class="group relative flex items-center border-b border-gray-200 p-3 first:rounded-t last:rounded-b hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-blue-900"
						>
							<Avatar user={u} class="mr-3 size-10" />
							<div class="min-w-0 flex-1">
								<a
									class="block text-sm font-medium text-gray-700 dark:text-gray-300"
									href={resolve(`/users/${u.id}`)}
								>
									<div class="absolute inset-0"></div>
									{u.name}
								</a>
								<p class="text-sm text-gray-400 group-hover:text-blue-400 dark:text-gray-500">
									{u.pronouns}
								</p>
							</div>
						</div>
					{/each}
				{:else}
					<p class="px-3 py-4 text-sm text-gray-400 dark:text-gray-500">
						No followed users. Add an AI user to get started.
					</p>
				{/if}
			</div>
		</div>
	</div>
{/if}
