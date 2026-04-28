<script lang="ts">
	import PencilAi from 'virtual:icons/octicon/pencil-ai-16';
	import Image from 'virtual:icons/octicon/image-16';
	import Upload from 'virtual:icons/octicon/upload-16';
	import Dialog from './base/dialog.svelte';
	import { resolve } from '$app/paths';
	import {
		failImageJobRequest,
		replaceImageJobRequest,
		startImageJobRequest,
		type ImageGenerationJobResponse
	} from '$lib/stores/image-jobs';

	type ImageJob = ImageGenerationJobResponse;

	type SelectableImage = {
		id: number;
		blur?: boolean;
		params?: Record<string, unknown> | null;
	};

	type PickerPost = {
		id: number;
		image_id: number | null;
	};

	const { post, images, onPostImageChange } = $props<{
		post: PickerPost;
		images: SelectableImage[];
		onPostImageChange?: (payload: {
			imageId: number | null;
			image?: SelectableImage | null;
		}) => void;
	}>();

	let image_id = $derived(post.image_id);
	let open = $state(false);

	let creating = $state(false);
	let uploading = $state(false);
	let imageJobId = $state<number | null>(null);
	let imageJobError = $state('');

	function applyImageChange(imageId: number | null, image?: SelectableImage | null) {
		onPostImageChange?.({ imageId, image: image ?? null });
	}

	function addImage() {
		creating = true;
		imageJobError = '';
		open = false;
		const pendingRequestId = startImageJobRequest({
			label: 'Post image',
			phase: 'prompt'
		});
		fetch(`/posts/${post.id}/image`, { method: 'POST' })
			.then(async (response) => {
				if (!response.ok) {
					throw new Error('Image generation request failed');
				}
				return (await response.json()) as ImageJob;
			})
			.then(async (body: ImageJob) => {
				if (!Number.isFinite(body.id)) {
					throw new Error('Invalid image job id');
				}
				creating = false;
				imageJobId = body.id;
				const [job] = replaceImageJobRequest(pendingRequestId, [body], {
					label: 'Post image'
				});
				const trackedJob = (await job) as ImageJob;
				if (trackedJob.status === 'completed' && trackedJob.image_id) {
					image_id = trackedJob.image_id;
					applyImageChange(trackedJob.image_id, trackedJob.image ?? null);
					return;
				}
				if (trackedJob.status === 'failed') {
					imageJobError = trackedJob.error || 'Image generation failed';
				}
			})
			.catch((error) => {
				creating = false;
				const message = error instanceof Error ? error.message : 'Unable to start image generation';
				failImageJobRequest(pendingRequestId, message, { label: 'Post image' });
				imageJobError = message;
			})
			.finally(() => {
				imageJobId = null;
			});
	}

	function setImage(e: Event) {
		e.preventDefault();
		if (image_id === null) {
			addImage();
		} else {
			fetch(`/posts/${post.id}`, { method: 'PATCH', body: JSON.stringify({ image_id }) }).then(
				() => {
					const selected = images.find((image: SelectableImage) => image.id === image_id) || null;
					applyImageChange(image_id, selected);
					open = false;
				}
			);
		}
	}

	async function uploadImage(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		uploading = true;
		imageJobError = '';

		const formData = new FormData();
		formData.append('file', file);

		try {
			const response = await fetch(resolve(`/posts/${post.id}/image`), {
				method: 'POST',
				body: formData
			});
			if (!response.ok) {
				throw new Error('Upload failed');
			}
			const body = await response.json();
			const newImage = body.image;
			image_id = newImage.id;
			applyImageChange(newImage.id, newImage);
			open = false;
		} catch {
			imageJobError = 'Unable to upload image';
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
	<span class="sr-only">Add AI image</span>
	<Image class="size-4" />
</button>

<Dialog title="Set post image" bind:open>
	<form onsubmit={setImage}>
		<div class="mb-3 grid grid-cols-2 gap-2 md:mb-4 md:grid-cols-3">
			{#each images as image (image.id)}
				<div class="max-w-40">
					<input
						type="radio"
						class="peer sr-only"
						id={image.id}
						value={image.id}
						bind:group={image_id}
					/>
					<label
						for={image.id}
						class="block overflow-hidden rounded opacity-75 ring-blue-500 transition peer-checked:opacity-100 peer-checked:ring-3 hover:opacity-100"
					>
						<img
							src={resolve(`/images/${image.id}`)}
							class={[
								'aspect-square object-cover',
								image.blur && 'blur-lg transition hover:blur-none'
							]}
							alt=""
						/>
					</label>
				</div>
			{/each}
			<div class="max-w-40">
				<input
					type="radio"
					class="peer sr-only"
					id="image-new"
					value={null}
					bind:group={image_id}
				/>
				<label
					for="image-new"
					class="flex aspect-square flex-col items-center justify-center gap-2 rounded bg-slate-50 opacity-75 ring-blue-500 transition peer-checked:opacity-100 peer-checked:ring-3 hover:opacity-100 dark:bg-slate-900"
				>
					<PencilAi class="size-12" />
					<p>Generate image</p>
				</label>
			</div>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<button
				type="submit"
				disabled={creating || imageJobId !== null}
				class="rounded-2xl px-3 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				{imageJobId !== null ? 'Generating...' : 'Set image'}
			</button>
			<label
				class="flex cursor-pointer items-center gap-1 rounded-2xl px-3 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				<Upload class="size-3.5" />
				{uploading ? 'Uploading...' : 'Upload image'}
				<input
					type="file"
					accept="image/*"
					class="sr-only"
					disabled={uploading}
					onchange={uploadImage}
				/>
			</label>
		</div>
		{#if imageJobError}
			<p class="mt-2 text-sm text-red-500">{imageJobError}</p>
		{/if}
	</form>
</Dialog>
