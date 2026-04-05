<script lang="ts">
	import AddStarburst from 'virtual:icons/fluent-color/add-starburst-16';
	import Image from 'virtual:icons/fluent-color/image-24';
	import Upload from 'virtual:icons/lucide/upload';
	import Dialog from './base/dialog.svelte';
	import { resolve } from '$app/paths';
	import { trackImageJob } from '$lib/stores/image-jobs';

	type ImageJob = {
		id: number;
		status: 'queued' | 'processing' | 'completed' | 'failed';
		image_id: number | null;
		error?: string | null;
		image?: {
			id: number;
			blur: boolean;
		} | null;
	};

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

	async function waitForJob(jobId: number) {
		imageJobId = jobId;
		imageJobError = '';

		try {
			const job = (await trackImageJob(jobId, { label: 'Post image' })) as ImageJob;
			if (job.status === 'completed' && job.image_id) {
				image_id = job.image_id;
				applyImageChange(job.image_id, job.image ?? null);
				open = false;
				return;
			}
			if (job.status === 'failed') {
				imageJobError = job.error || 'Image generation failed';
			}
		} catch {
			imageJobError = 'Unable to check image generation status';
		} finally {
			imageJobId = null;
		}
	}

	function addImage() {
		creating = true;
		fetch(`/posts/${post.id}/image`, { method: 'POST' })
			.then(async (response) => {
				if (!response.ok) {
					throw new Error('Image generation request failed');
				}
				return (await response.json()) as ImageJob;
			})
			.then((body: ImageJob) => {
				if (!Number.isFinite(body.id)) {
					throw new Error('Invalid image job id');
				}
				creating = false;
				void waitForJob(body.id);
			})
			.catch(() => {
				creating = false;
				imageJobError = 'Unable to start image generation';
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
					<AddStarburst class="size-12" />
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
