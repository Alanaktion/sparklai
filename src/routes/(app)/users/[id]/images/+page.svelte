<script lang="ts">
	import { browser } from '$app/environment';
	import { resolve } from '$app/paths';
	import Dialog from '$lib/components/base/dialog.svelte';
	import Image from '$lib/components/Image.svelte';
	import {
		failImageJobRequest,
		replaceImageJobRequest,
		startImageJobRequest,
		type ImageGenerationJobResponse
	} from '$lib/stores/image-jobs';
	import ImageIcon from 'virtual:icons/octicon/image-24';
	import Loader from 'virtual:icons/octicon/issue-draft-16';
	import Loader24 from 'virtual:icons/octicon/issue-draft-24';
	import Ratio from 'virtual:icons/octicon/screen-normal-16';
	import Upload from 'virtual:icons/octicon/upload-16';
	import type { PageProps } from './$types';
	import { getUserProfileContext } from '$lib/user-profile-context';

	let { data }: PageProps = $props();
	const profileState = getUserProfileContext();

	type ImageJob = ImageGenerationJobResponse;

	let creating = $state(false);
	let open = $state(false);
	let prompt = $state('');
	let aspect = $state('square');
	let count = $state(1);
	let pendingImageJobIds = $state<number[]>([]);
	let recentlyQueuedImageJobIds = $state<number[]>([]);
	let imageJobError = $state('');
	let uploading = $state(false);
	let uploadError = $state('');

	function trackPendingJob(jobId: number) {
		if (!pendingImageJobIds.includes(jobId)) {
			pendingImageJobIds = [...pendingImageJobIds, jobId];
		}
	}

	function finishPendingJob(jobId: number) {
		pendingImageJobIds = pendingImageJobIds.filter((id) => id !== jobId);
		recentlyQueuedImageJobIds = recentlyQueuedImageJobIds.filter((id) => id !== jobId);
	}

	const uploadImages = async (event: Event) => {
		const input = event.target as HTMLInputElement;
		const files = input.files;
		if (!files || !files.length) return;

		uploading = true;
		uploadError = '';

		const formData = new FormData();
		for (const file of files) {
			formData.append('files', file);
		}

		try {
			const response = await fetch(resolve(`/users/${data.id}/images`), {
				method: 'POST',
				body: formData
			});
			if (!response.ok) {
				const body = await response.json().catch(() => ({}));
				throw new Error((body as { message?: string }).message || 'Upload failed');
			}
			const result = (await response.json()) as { images: (typeof profileState.images)[number][] };
			for (const image of result.images) {
				if (!profileState.images.some((img) => img.id === image.id)) {
					profileState.images = [...profileState.images, image];
				}
			}
		} catch (err) {
			uploadError = err instanceof Error ? err.message : 'Upload failed';
		} finally {
			uploading = false;
			input.value = '';
		}
	};

	const newImage = (event: Event) => {
		event.preventDefault();
		creating = true;
		imageJobError = '';
		open = false;
		const pendingRequestId = startImageJobRequest({
			label: 'Profile image',
			phase: prompt.trim() === '' ? 'prompt' : 'image'
		});
		fetch(resolve(`/users/${data.id}/image`), {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `prompt=${encodeURIComponent(prompt)}&aspect=${aspect}&count=${count}`
		})
			.then(async (response) => {
				if (!response.ok) {
					throw new Error('Image request failed');
				}
				return (await response.json()) as ImageJob[];
			})
			.then((jobs) => {
				if (!Array.isArray(jobs) || !jobs.length) {
					throw new Error('Invalid image jobs response');
				}
				const trackedJobs = replaceImageJobRequest(pendingRequestId, jobs, {
					label: 'Profile image'
				});
				for (const [index, job] of jobs.entries()) {
					recentlyQueuedImageJobIds = [job.id, ...recentlyQueuedImageJobIds].slice(0, 10);
					trackPendingJob(job.id);
					void trackedJobs[index]
						.then((trackedJob) => {
							if (trackedJob.status === 'completed' && trackedJob.image_id) {
								if (
									trackedJob.image &&
									!profileState.images.some((image) => image.id === trackedJob.image!.id)
								) {
									profileState.images = [...profileState.images, trackedJob.image];
								}
								if (trackedJob.set_as_user_image) {
									profileState.user.image_id = trackedJob.image_id;
									profileState.avatarRenderKey += 1;
								}
								return;
							}
							if (trackedJob.status === 'failed') {
								imageJobError = trackedJob.error || 'Image generation failed';
							}
						})
						.catch(() => {
							imageJobError = 'Unable to check image generation status';
						})
						.finally(() => {
							finishPendingJob(job.id);
						});
				}
				creating = false;
			})
			.catch((error) => {
				creating = false;
				const message = error instanceof Error ? error.message : 'Unable to start image generation';
				failImageJobRequest(pendingRequestId, message, { label: 'Profile image' });
				imageJobError = message;
			});
	};
</script>

<div class="mb-4 flex justify-end">
	{#if browser}
		<label
			class="cursor-pointer rounded p-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
			title="Upload photos"
		>
			<span class="sr-only">Upload photos</span>
			{#if uploading}
				<Loader class="size-4 animate-spin" />
			{:else}
				<Upload class="size-4" />
			{/if}
			<input
				type="file"
				accept="image/*"
				multiple
				class="sr-only"
				onchange={uploadImages}
				disabled={uploading}
			/>
		</label>
		<button
			onclick={() => (open = true)}
			type="button"
			class="rounded p-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
		>
			<span class="sr-only">Add AI image</span>
			<ImageIcon class="size-4" />
		</button>
		<Dialog title="Add AI image" bind:open>
			<form class="grid gap-2" onsubmit={newImage} method="POST">
				<textarea
					bind:value={prompt}
					name="message"
					rows="6"
					class="flex w-full rounded border border-gray-300 bg-transparent px-2 py-1 text-sm shadow-sm transition-colors placeholder:text-gray-300 focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none disabled:opacity-50 dark:border-gray-500 dark:placeholder:text-gray-600"
					placeholder="Image prompt (optional)"
				></textarea>
				<div class="flex items-center gap-2 rounded focus-within:ring">
					<Ratio class="size-4 text-gray-400 dark:text-gray-500" />
					<label
						class="has-checked:text-blue-600 has-checked:underline dark:has-checked:text-blue-400"
					>
						<input type="radio" class="sr-only" bind:group={aspect} value="square" />
						Square
					</label>
					<label
						class="has-checked:text-blue-600 has-checked:underline dark:has-checked:text-blue-400"
					>
						<input type="radio" class="sr-only" bind:group={aspect} value="landscape" />
						Wide
					</label>
					<label
						class="has-checked:text-blue-600 has-checked:underline dark:has-checked:text-blue-400"
					>
						<input type="radio" class="sr-only" bind:group={aspect} value="portrait" />
						Tall
					</label>
				</div>
				<div class="flex items-center gap-2 rounded focus-within:ring">
					<span class="text-sm text-gray-400 dark:text-gray-500">Count:</span>
					{#each [1, 2, 3, 4, 5] as n (n)}
						<label
							class={count === n
								? 'cursor-pointer text-blue-600 underline dark:text-blue-400'
								: 'cursor-pointer text-gray-600 dark:text-gray-400'}
						>
							<input type="radio" class="sr-only" bind:group={count} value={n} />
							{n}
						</label>
					{/each}
				</div>
				{#if creating}
					<Loader class="mx-auto my-2 size-4 animate-spin text-gray-600 dark:text-gray-400" />
				{:else}
					<button
						type="submit"
						class="rounded-2xl px-2 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
					>
						Queue Image
					</button>
				{/if}
				{#if pendingImageJobIds.length}
					<div class="grid gap-1 text-sm text-gray-500 dark:text-gray-400">
						<p>{pendingImageJobIds.length} image job(s) in progress.</p>
						{#if recentlyQueuedImageJobIds.length}
							<p>Queued: {recentlyQueuedImageJobIds.map((id) => `#${id}`).join(', ')}</p>
						{/if}
					</div>
				{/if}
				{#if imageJobError}
					<p class="text-sm text-red-500">{imageJobError}</p>
				{/if}
			</form>
		</Dialog>
	{/if}
</div>

<div class="grid grid-cols-2 gap-2 md:grid-cols-3">
	{#each profileState.images as image (image.id)}
		<Image {image} />
	{/each}
	{#if creating}
		<div class="flex aspect-square w-full bg-gray-200 dark:bg-gray-800">
			<Loader24 class="m-auto size-8 animate-spin text-gray-600 dark:text-gray-400" />
		</div>
	{/if}
</div>
{#if uploadError}
	<p class="mt-2 text-sm text-red-500">{uploadError}</p>
{/if}
