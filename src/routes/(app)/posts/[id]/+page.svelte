<script lang="ts">
	import { browser } from '$app/environment';
	import { looksNonEnglish } from '$lib/language';
	import { parseInlineItalics } from '$lib/text';
	import { goto } from '$app/navigation';
	import { hotkey } from '$lib/actions/hotkey.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import DropdownOption from '$lib/components/base/dropdown-option.svelte';
	import Dropdown from '$lib/components/base/dropdown.svelte';
	import ImagePicker from '$lib/components/ImagePicker.svelte';
	import MediaPicker from '$lib/components/MediaPicker.svelte';
	import Post from '$lib/components/Post.svelte';
	import DismissCircle from 'virtual:icons/fluent-color/dismiss-circle-16';
	import ImageOff from 'virtual:icons/fluent-color/image-off-24';
	import SlideTextSparkle from 'virtual:icons/fluent-color/slide-text-sparkle-24';
	import Loader from 'virtual:icons/lucide/loader';

	import type { PostType, UserType } from '$lib/server/db/schema';
	import type { PageProps } from './$types';
	import { resolve } from '$app/paths';

	let { data }: PageProps = $props();

	type PostPickerImage = {
		id: number;
		blur?: boolean;
		params?: Record<string, unknown> | null;
	};

	type PostPickerMedia = {
		id: number;
		type: string;
	};

	let user = $derived<UserType>(data.post.user);
	let users = $derived<UserType[]>(data.users);
	let post = $derived(
		data.post as PostType & { image?: PostPickerImage | null; media?: PostPickerMedia | null }
	);
	let comments = $derived(data.post.comments);
	let postImages = $derived<PostPickerImage[]>(data.images);
	let postMedia = $derived<PostPickerMedia[]>(data.media);

	let open = $state(false);
	let responding = $state(false);
	function respond(user_id: number | null = null) {
		responding = true;
		open = false;
		fetch(resolve(`/posts/${data.id}/comments/respond`), {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ user_id })
		})
			.then((response) => response.json())
			.then((body) => {
				responding = false;
				comments = [...comments, body];
			})
			.catch(() => (responding = false));
	}

	let message = $state('');
	let submitting = $state(false);
	function submit(e: Event) {
		e.preventDefault();
		submitting = true;
		fetch(resolve(`/posts/${data.id}/comments`), {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `message=${encodeURIComponent(message)}`
		})
			.then((response) => response.json())
			.then((body) => {
				comments = [...comments, body];
				message = '';
				submitting = false;
			})
			.catch(() => (submitting = false));
	}

	function deletePost() {
		fetch(resolve(`/posts/${data.id}`), { method: 'DELETE' }).then(() => goto(resolve('/')));
	}
	function deleteComment(id: number) {
		fetch(resolve(`/posts/${data.id}/comments/${id}`), { method: 'DELETE' }).then(() => {
			comments = comments.filter((comment) => comment.id !== id);
		});
	}
	function detatchImage() {
		fetch(resolve(`/posts/${data.id}`), {
			method: 'PATCH',
			body: JSON.stringify({ image_id: null })
		}).then(() => {
			post = { ...post, image_id: null, image: null };
		});
	}

	function detatchMedia() {
		fetch(resolve(`/posts/${data.id}`), {
			method: 'PATCH',
			body: JSON.stringify({ media_id: null })
		}).then(() => {
			post = { ...post, media_id: null, media: null };
		});
	}

	function handlePostImageChange(payload: {
		imageId: number | null;
		image?: PostPickerImage | null;
	}) {
		post = {
			...post,
			image_id: payload.imageId,
			image: payload.image ?? null
		};
		if (payload.image && !postImages.some((existing) => existing.id === payload.image!.id)) {
			postImages = [...postImages, payload.image];
		}
	}

	function handlePostMediaChange(payload: {
		mediaId: number | null;
		media?: PostPickerMedia | null;
	}) {
		post = {
			...post,
			media_id: payload.mediaId,
			media: payload.media ?? null
		};
		if (payload.media && !postMedia.some((existing) => existing.id === payload.media!.id)) {
			postMedia = [...postMedia, payload.media];
		}
	}

	let translatingCommentIds = $state<number[]>([]);

	async function translateComment(commentId: number) {
		if (translatingCommentIds.includes(commentId)) {
			return;
		}

		translatingCommentIds = [...translatingCommentIds, commentId];
		try {
			const response = await fetch(resolve(`/posts/${data.id}/comments/${commentId}/translate`), {
				method: 'POST'
			});
			if (!response.ok) {
				return;
			}
			const body = (await response.json()) as { body_en?: string | null };
			const comment = comments.find((c) => c.id === commentId);
			if (comment) {
				comment.body_en = body.body_en ?? null;
			}
		} finally {
			translatingCommentIds = translatingCommentIds.filter((id) => id !== commentId);
		}
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
					<ImagePicker {post} images={postImages} onPostImageChange={handlePostImageChange} />
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
				{#if !post.media_id}
					<MediaPicker {post} mediaItems={postMedia} onPostMediaChange={handlePostMediaChange} />
				{:else}
					<button
						onclick={detatchMedia}
						type="button"
						class="rounded p-1 text-sm text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-800"
					>
						<span class="sr-only">Detatch media</span>
						<DismissCircle class="size-4" />
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

			{#each comments as comment (comment.id)}
				{@const bodySegments = parseInlineItalics(comment.body)}
				<div class="group my-4 flex items-start gap-3">
					<a class="min-w-10" href={resolve(`/users/${comment.user_id}`)}>
						<Avatar user={comment.user} class="size-10" />
					</a>
					<div class="flex-1">
						<div class="flex justify-between text-sm leading-tight">
							{#if comment.user}
								<a
									class="text-blue-600 hover:underline dark:text-blue-400"
									href={resolve(`/users/${comment.user_id}`)}>{comment.user.name}</a
								>
							{:else}
								<span class="text-gray-500">User</span>
							{/if}
							<button
								onclick={() => deleteComment(comment.id)}
								type="button"
								class="rounded p-1 text-sm text-red-600 opacity-25 group-hover:opacity-100 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-800"
							>
								<span class="sr-only">Delete comment</span>
								<DismissCircle class="size-4" />
							</button>
						</div>
						<p class="whitespace-pre-wrap">
							{#each bodySegments as segment, i (i)}
								{#if segment.italic}
									<em>{segment.text}</em>
								{:else}
									{segment.text}
								{/if}
							{/each}
						</p>
						{#if !comment.body_en && looksNonEnglish(comment.body)}
							<button
								type="button"
								onclick={() => translateComment(comment.id)}
								disabled={translatingCommentIds.includes(comment.id)}
								class="mt-1 rounded border border-gray-300 px-2 py-0.5 text-xs text-gray-600 hover:bg-gray-100 disabled:cursor-wait disabled:opacity-60 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
							>
								{translatingCommentIds.includes(comment.id)
									? 'Translating...'
									: 'Translate to English'}
							</button>
						{/if}
						{#if comment.body_en}
							<p class="mt-1 text-xs whitespace-pre-wrap text-gray-600 dark:text-gray-400">
								{comment.body_en}
							</p>
						{/if}
					</div>
				</div>
			{/each}

			{#if browser}
				<form onsubmit={submit} class="mt-5 flex items-center gap-2 py-2">
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
							{#each users as u (u.id)}
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
					{#if submitting}
						<Loader class="mx-auto my-2 size-4 animate-spin text-gray-600 dark:text-gray-400" />
					{:else}
						<button
							disabled={submitting}
							type="submit"
							class="rounded-2xl px-2 py-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
						>
							Post
						</button>
					{/if}
				</form>
			{/if}
		</div>
	</div>
{:else}
	<Loader class="mx-auto my-6 size-12 animate-spin text-gray-600 dark:text-gray-400" />
{/if}
