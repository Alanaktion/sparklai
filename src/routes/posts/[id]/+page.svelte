<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { hotkey } from '$lib/actions/hotkey.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import DropdownOption from '$lib/components/base/dropdown-option.svelte';
	import Dropdown from '$lib/components/base/dropdown.svelte';
	import ImagePicker from '$lib/components/ImagePicker.svelte';
	import Post from '$lib/components/Post.svelte';
	import DismissCircle from '$lib/icons/DismissCircle.svelte';
	import ImageOff from '$lib/icons/ImageOff.svelte';
	import SlideTextSparkle from '$lib/icons/SlideTextSparkle.svelte';
	import { Loader } from 'lucide-svelte';

	import type { PostType, UserType } from '$lib/server/db/schema';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let user = $state<UserType>(data.post.user);
	let users = $state<UserType[]>(data.users);
	let post = $state<PostType>(data.post);
	let comments = $state(data.post.comments);

	let open = $state(false);
	let responding = $state(false);
	function respond(user_id: Number | null = null) {
		responding = true;
		open = false;
		fetch(`/posts/${data.id}/comments/respond`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ user_id })
		})
			.then((response) => response.json())
			.then((body) => {
				responding = false;
				comments.push(body);
			})
			.catch(() => (responding = false));
	}

	let form: HTMLFormElement | undefined = $state();
	let message = $state('');
	let submitting = $state(false);
	function submit(e: Event) {
		e.preventDefault();
		fetch(`/posts/${data.id}/comments`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `message=${encodeURIComponent(message)}`
		})
			.then((response) => response.json())
			.then((body) => {
				comments.push(body);
				message = '';
				submitting = false;
			})
			.catch(() => (submitting = false));
	}

	function deletePost() {
		fetch(`/posts/${data.id}`, { method: 'DELETE' }).then(() => goto('/'));
	}
	function deleteComment(id: number, index: number) {
		fetch(`/posts/${data.id}/comments/${id}`, { method: 'DELETE' }).then(() => {
			delete comments[index];
		});
	}
	function detatchImage() {
		fetch(`/posts/${data.id}`, { method: 'PATCH', body: JSON.stringify({ image_id: null }) }).then(
			() => (post.image_id = null)
		);
	}
</script>

<svelte:head>
	<title>Post by {user && user.name}</title>
</svelte:head>

{#if post}
	<div class="mx-auto my-4 max-w-xl">
		{#if browser}
			<div class="flex items-center justify-end gap-1">
				{#if !post.image_id}
					<ImagePicker {post} images={data.images} />
				{:else}
					<button
						onclick={detatchImage}
						type="button"
						class="rounded p-1 text-sm text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-800"
					>
						<span class="sr-only">Detatch image</span>
						<ImageOff class="size-4" />
					</button>
				{/if}
				<button
					onclick={deletePost}
					use:hotkey={{ code: 'Digit3', shiftKey: true, onKeydown: deletePost }}
					type="button"
					class="rounded p-1 text-sm text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-800"
				>
					<span class="sr-only">Delete post</span>
					<DismissCircle class="size-4" />
				</button>
			</div>
		{/if}

		<Post {post} {user} full />

		<div class="mb-4 lg:mb-6">
			<div class="text-gray-700 dark:text-gray-300">Comments</div>

			{#each comments as comment, index}
				<div class="group my-4 flex items-start gap-3">
					<a class="min-w-10" href="/users/{comment.user_id}">
						<Avatar user={comment.user} class="size-10" />
					</a>
					<div class="flex-1">
						<div class="flex justify-between text-sm leading-tight">
							{#if comment.user}
								<a
									class="text-blue-600 hover:underline dark:text-blue-400"
									href="/users/{comment.user_id}">{comment.user.name}</a
								>
							{:else}
								<span class="text-gray-500">User</span>
							{/if}
							<button
								onclick={() => deleteComment(comment.id, index)}
								type="button"
								class="rounded p-1 text-sm text-red-600 opacity-25 group-hover:opacity-100 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-800"
							>
								<span class="sr-only">Delete comment</span>
								<DismissCircle class="size-4" />
							</button>
						</div>
						<p class="whitespace-pre-wrap">{comment.body}</p>
					</div>
				</div>
			{/each}

			{#if browser}
				<form bind:this={form} onsubmit={submit} class="mt-5 flex items-center gap-2 py-2">
					{#if responding}
						<Loader class="mx-1 size-4 animate-spin text-gray-600 dark:text-gray-400" />
					{:else}
						<button
							onclick={() => (open = !open)}
							type="button"
							class="rounded p-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
						>
							<span class="sr-only">Add AI comment</span>
							<SlideTextSparkle class="size-4" />
						</button>
						<Dropdown bind:open placement="left">
							<DropdownOption onclick={() => respond()}>Random User</DropdownOption>
							<hr class="my-1 border-gray-400/50" />
							{#each users as u}
								<DropdownOption onclick={() => respond(u.id)}>
									<Avatar user={u} class="size-4" />
									{u.name}
								</DropdownOption>
							{/each}
						</Dropdown>
					{/if}
					<input
						autocomplete="off"
						bind:value={message}
						name="message"
						class="flex w-full rounded-2xl border border-gray-500 bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-gray-300 focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none disabled:opacity-50 dark:placeholder:text-gray-600"
						type="text"
						placeholder="Comment"
						required
					/>
					<button
						disabled={submitting}
						type="submit"
						class="rounded-2xl px-2 py-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
					>
						Post
					</button>
				</form>
			{/if}
		</div>
	</div>
{:else}
	<Loader class="mx-auto my-6 size-12 animate-spin text-gray-600 dark:text-gray-400" />
{/if}
