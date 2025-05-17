<script lang="ts">
	import Avatar from '$lib/components/Avatar.svelte';
	import Post from '$lib/components/Post.svelte';
	import { ImagePlus, Loader, Trash2, WandSparkles } from 'lucide-svelte';

	import { loadJson } from '$lib/api';
	import type { PageProps } from './$types';
	let { data }: PageProps = $props();

	let user = $state(data.user);
	let post = $state(data.post);
	let comments = $state(data.comments);

	let creating = $state(false);
	function addImage() {
		creating = true;
		loadJson(`posts/${data.id}/image`, { method: 'POST' })
			.then((body) => {
				creating = false;
				post.image_id = body;
			})
			.catch(() => (creating = false));
	}

	let responding = $state(false);
	function respond() {
		responding = true;
		loadJson(`posts/${data.id}/comments/respond`, { method: 'POST' })
			.then((body) => {
				responding = false;
				comments.push(body);
			})
			.catch(() => (responding = false));
	}

	let form: HTMLFormElement | undefined = $state();
	let message = $state('');
	function submit(e: Event) {
		e.preventDefault();
		loadJson(`posts/${data.id}/comments`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `message=${encodeURIComponent(message)}`
		}).then((body) => comments.push(body));
		message = '';
	}

	function deletePost() {
		// TODO: CORS for DELETE is not an option, will need to POST with `_method` param or whatevs.
		loadJson(`/${data.id}`, { method: 'DELETE' }).then(() => (location.href = '/'));
	}
</script>

<svelte:head>
	<title>Post by {user && user.name}</title>
</svelte:head>

{#if post}
	<div class="mx-auto my-4 max-w-xl">
		{#if !post.image_id}
			<div class="flex items-center justify-end">
				{#if creating}
					<Loader class="mx-1 size-4 animate-spin text-slate-600 dark:text-slate-400" />
				{:else}
					<button
						onclick={addImage}
						type="button"
						class="rounded p-1 text-sm text-sky-600 hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800"
					>
						<span class="sr-only">Add AI image</span>
						<ImagePlus class="size-4" />
					</button>
				{/if}
				<button
					onclick={deletePost}
					type="button"
					class="rounded p-1 text-sm text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-800"
				>
					<span class="sr-only">Delete post</span>
					<Trash2 class="size-4" />
				</button>
			</div>
		{/if}

		<Post {post} {user} full />

		<div class="mb-4 lg:mb-6">
			<div class="text-slate-700 dark:text-slate-300">Comments</div>

			{#each comments as comment}
				<div class="my-4 flex gap-3">
					<Avatar user={comment.user} class="size-10" />
					<div>
						<div class="text-sm leading-tight">
							{#if comment?.user?.id}
								<a
									class="text-sky-600 hover:underline dark:text-sky-400"
									href="/users/{comment.user.id}">{comment.user.name}</a
								>
							{:else}
								<span class="text-slate-500">User</span>
							{/if}
						</div>
						<p>{comment.comment.body}</p>
					</div>
				</div>
			{/each}

			<form bind:this={form} onsubmit={submit} class="mt-5 flex items-center gap-2 py-2">
				{#if responding}
					<Loader class="mx-1 size-4 animate-spin text-slate-600 dark:text-slate-400" />
				{:else}
					<button
						onclick={respond}
						type="button"
						class="rounded p-1 text-sm text-sky-600 hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800"
					>
						<span class="sr-only">Add AI comment</span>
						<WandSparkles class="size-4" />
					</button>
				{/if}
				<input
					autocomplete="off"
					bind:value={message}
					name="message"
					class="flex w-full rounded-2xl border border-slate-500 bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-slate-300 dark:placeholder:text-slate-600 focus:border-sky-600 focus-visible:ring-1 focus-visible:ring-sky-500 focus-visible:outline-none disabled:opacity-50"
					type="text"
					placeholder="Comment"
				/>
				<button
					type="submit"
					class="rounded-2xl px-2 py-1 text-sm text-sky-600 hover:bg-sky-100 dark:text-sky-400 dark:hover:bg-sky-800"
				>
					Post
				</button>
			</form>
		</div>
	</div>
{:else}
	<Loader class="mx-auto my-6 size-12 animate-spin text-slate-600 dark:text-slate-400" />
{/if}
