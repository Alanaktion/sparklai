<script lang="ts">
	import { Loader, MessageCircle, WandSparkles } from 'lucide-svelte';
	import { loadJson } from '$lib/api';
	import type { PageProps } from './$types';
	let { data }: PageProps = $props();

	import Avatar from '$lib/components/Avatar.svelte';
	import Post from '$lib/components/Post.svelte';
	import Image from '$lib/components/Image.svelte';

	let tab = $state('posts');
	let user = $state(data.user);
	let posts = $state(data.posts);
	let images = $state(data.images);

	let creating = $state(false);
	const newPost = () => {
		creating = true;
		loadJson(`users/${data.id}/posts`, { method: 'POST' })
			.then((body) => {
				posts = [body, ...posts];
				creating = false;
			})
			.catch(() => {
				creating = false;
			});
	};
</script>

<svelte:head>
	<title>{user && user.name}</title>
</svelte:head>

{#if user}
	<div class="mx-auto my-4 max-w-2xl px-4">
		<header
			class="border-b border-slate-300 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-900"
		>
			<div class="flex items-center gap-4">
				<Avatar {user} class="size-24" />
				<div class="ms-auto text-end">
					<h1 class="text-xl font-semibold text-slate-800 dark:text-slate-200">{user.name}</h1>
					<p class="text-sm text-slate-400">{user.pronouns}</p>
				</div>
				<a
					href="/users/{user.id}/chat"
					class="rounded p-1 text-sm text-sky-600 hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800"
				>
					<span class="sr-only">Messages</span>
					<MessageCircle />
				</a>
			</div>
		</header>

		<section class="px-6 py-4">
			<div class="py-4 text-slate-700 dark:text-slate-400">
				<p class="text-lg">{user.bio}</p>
			</div>
		</section>

		<section class="px-6 py-4">
			<div class="mb-4 flex items-center justify-between gap-4">
				<div
					class="flex items-center gap-3 text-xl font-semibold text-slate-800 dark:text-slate-200"
				>
					<button
						class="cursor-pointer {tab == 'posts'
							? 'border-sky-500'
							: 'border-transparent'} border-b-2"
						type="button"
						onclick={() => (tab = 'posts')}>Posts</button
					>
					<button
						class="cursor-pointer {tab == 'images'
							? 'border-sky-500'
							: 'border-transparent'} border-b-2"
						type="button"
						onclick={() => (tab = 'images')}>Images</button
					>
				</div>
				{#if creating}
					<Loader class="mx-1 size-4 animate-spin text-slate-600 dark:text-slate-400" />
				{:else if tab == 'posts'}
					<button
						onclick={newPost}
						type="button"
						class="rounded p-1 text-sm text-sky-600 hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800"
					>
						<span class="sr-only">Add AI post</span>
						<WandSparkles class="size-4" />
					</button>
				{/if}
			</div>

			{#if tab == 'posts'}
				{#each posts as post}
					<Post {post} {user} />
				{/each}
			{:else if tab == 'images'}
				<div class="grid grid-cols-2 gap-2 md:grid-cols-3">
					{#each images as image}
						<Image {image} />
					{/each}
				</div>
			{/if}
		</section>
	</div>
{:else}
	<Loader class="mx-auto my-6 size-12 animate-spin text-slate-600 dark:text-slate-400" />
{/if}
