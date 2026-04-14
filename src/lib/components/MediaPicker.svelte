<script lang="ts">
	import Video from 'virtual:icons/fluent-color/video-24';
	import Upload from 'virtual:icons/lucide/upload';
	import Dialog from './base/dialog.svelte';
	import { resolve } from '$app/paths';

	type SelectableMedia = {
		id: number;
		type: string;
	};

	type PickerPost = {
		id: number;
		media_id: number | null;
	};

	const { post, mediaItems, onPostMediaChange } = $props<{
		post: PickerPost;
		mediaItems: SelectableMedia[];
		onPostMediaChange?: (payload: {
			mediaId: number | null;
			media?: SelectableMedia | null;
		}) => void;
	}>();

	let media_id = $derived(post.media_id);
	let open = $state(false);
	let uploading = $state(false);
	let mediaUploadError = $state('');

	function applyMediaChange(mediaId: number | null, media?: SelectableMedia | null) {
		onPostMediaChange?.({ mediaId, media: media ?? null });
	}

	function setMedia(e: Event) {
		e.preventDefault();
		if (media_id === null) {
			return;
		}
		fetch(resolve(`/posts/${post.id}`), {
			method: 'PATCH',
			body: JSON.stringify({ media_id })
		}).then(() => {
			const selected = mediaItems.find((item: SelectableMedia) => item.id === media_id) || null;
			applyMediaChange(media_id, selected);
			open = false;
		});
	}

	async function uploadMedia(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		uploading = true;
		mediaUploadError = '';

		const formData = new FormData();
		formData.append('file', file);

		try {
			const response = await fetch(resolve(`/posts/${post.id}/media`), {
				method: 'POST',
				body: formData
			});
			if (!response.ok) {
				throw new Error('Upload failed');
			}
			const body = await response.json();
			const newMedia = body.media as SelectableMedia;
			media_id = newMedia.id;
			applyMediaChange(newMedia.id, newMedia);
			open = false;
		} catch {
			mediaUploadError = 'Unable to upload media';
		} finally {
			uploading = false;
			input.value = '';
		}
	}
</script>

<button
	type="button"
	class="rounded p-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
	onclick={() => (open = true)}
>
	<span class="sr-only">Add media</span>
	<Video class="size-4" />
</button>

<Dialog title="Set post media" bind:open>
	<form onsubmit={setMedia}>
		<div class="mb-3 grid grid-cols-1 gap-2 md:mb-4 md:grid-cols-2">
			{#each mediaItems as item (item.id)}
				<div>
					<input
						type="radio"
						class="peer sr-only"
						id={`media-${item.id}`}
						value={item.id}
						bind:group={media_id}
					/>
					<label
						for={`media-${item.id}`}
						class="block overflow-hidden rounded border border-gray-300 p-2 opacity-75 ring-blue-500 transition peer-checked:opacity-100 peer-checked:ring-3 hover:opacity-100 dark:border-gray-700"
					>
						{#if item.type.startsWith('audio/')}
							<audio controls class="w-full">
								<source src={resolve(`/media/${item.id}`)} type={item.type} />
							</audio>
						{:else if item.type.startsWith('video/')}
							<video controls class="w-full">
								<source src={resolve(`/media/${item.id}`)} type={item.type} />
							</video>
						{/if}
						<p class="mt-1 truncate text-xs text-gray-500 dark:text-gray-400">{item.type}</p>
					</label>
				</div>
			{/each}
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<button
				type="submit"
				disabled={media_id === null}
				class="rounded-2xl px-3 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				Set media
			</button>
			<label
				class="flex cursor-pointer items-center gap-1 rounded-2xl px-3 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				<Upload class="size-3.5" />
				{uploading ? 'Uploading...' : 'Upload media'}
				<input
					type="file"
					accept="audio/*,video/*"
					class="sr-only"
					disabled={uploading}
					onchange={uploadMedia}
				/>
			</label>
		</div>
		{#if mediaUploadError}
			<p class="mt-2 text-sm text-red-500">{mediaUploadError}</p>
		{/if}
	</form>
</Dialog>
