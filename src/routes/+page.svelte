<script lang="ts">
	import { Loader, WandSparkles } from 'lucide-svelte';
	import type { PageProps } from './$types';
	let { data }: PageProps = $props();
	import { loadJson } from '$lib/api';
	import { browser } from '$app/environment';

	import Post from '$lib/components/Post.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import Dialog from '$lib/components/base/dialog.svelte';

	let open = $state(false);

	let users = $state(data.users);
	let posts = $state(data.posts);

	let creating = $state(false);
	let user_prompt = $state('');
	const newUser = (e: Event) => {
		e.preventDefault();
		creating = true;
		loadJson(`users`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `prompt=${encodeURIComponent(user_prompt)}`
		})
			.then((body) => {
				creating = false;
				open = false;
				user_prompt = '';
				users.push(body);
			})
			.catch(() => {
				creating = false;
				open = false;
			});
	};

	const user = (id: number) => {
		const matches = users.filter((u) => u.id == id);
		return matches ? matches[0] : {};
	};
</script>

<svelte:head>
	<title>Home ✨</title>
</svelte:head>

{#if users && posts}
	<div class="my-4 max-w-4xl grid-cols-3 gap-6 px-4 sm:mx-auto sm:grid lg:gap-8">
		<div class="col-span-2">
			<h2 class="mb-4 text-xl">Posts</h2>

			{#if posts.length}
				{#each posts as post}
					<Post {post} user={user(post.user_id)} />
				{/each}
			{:else}
				<Loader class="mx-auto my-6 size-12 animate-spin text-slate-600 dark:text-slate-400" />
			{/if}
		</div>

		<div>
			<div class="mb-4 flex items-center justify-between">
				<h2 class="text-xl">Users</h2>
				{#if browser}
					<button
						onclick={() => (open = true)}
						type="button"
						class="rounded p-1 text-sm text-sky-600 hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800"
					>
						<span class="sr-only">Add AI user</span>
						<WandSparkles class="size-4" />
					</button>
					<Dialog title="Add AI user" bind:open>
						<form class="grid gap-2" onsubmit={newUser} method="POST">
							<textarea
								bind:value={user_prompt}
								name="message"
								rows="6"
								class="flex w-full rounded border border-slate-300 bg-transparent px-2 py-1 text-sm shadow-sm transition-colors placeholder:text-slate-300 focus:border-sky-600 focus-visible:ring-1 focus-visible:ring-sky-500 focus-visible:outline-none disabled:opacity-50 dark:border-slate-500 dark:placeholder:text-slate-600"
								placeholder="User prompt (optional)"
							></textarea>
							{#if creating}
								<Loader
									class="mx-auto my-2 size-4 animate-spin text-slate-600 dark:text-slate-400"
								/>
							{:else}
								<button
									type="submit"
									class="rounded-2xl px-2 py-2 text-sm leading-none text-sky-600 hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800"
								>
									Create User
								</button>
							{/if}
						</form>
					</Dialog>
				{/if}
			</div>

			<div
				class="sticky top-4 rounded bg-slate-50 shadow-lg shadow-slate-500/10 dark:bg-slate-900 dark:shadow-slate-900/20"
			>
				{#if users.length}
					{#each users as user}
						<div
							class="relative flex items-center border-b border-slate-200 p-3 first:rounded-t last:rounded-b hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-700"
						>
							<Avatar {user} class="mr-3 size-10" />
							<div>
								<a
									class="block text-sm font-medium text-slate-700 dark:text-slate-300"
									href="/users/{user.id}"
								>
									<div class="absolute inset-0"></div>
									{user.name}
								</a>
								<p class="text-sm text-slate-400 dark:text-slate-500">{user.pronouns}</p>
							</div>
						</div>
					{/each}
				{:else}
					<Loader class="mx-auto size-12 animate-spin py-2 text-slate-600 dark:text-slate-400" />
				{/if}
			</div>
		</div>
	</div>
{/if}
