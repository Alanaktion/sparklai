<script lang="ts">
	import AddStarburst from 'virtual:icons/fluent-color/add-starburst-16';
	import Image from 'virtual:icons/fluent-color/image-24';
	import Dialog from './base/dialog.svelte';
	import { resolve } from '$app/paths';

	type ImageJob = {
		id: number;
		status: 'queued' | 'processing' | 'completed' | 'failed';
		image_id: number | null;
		image?: {
			id: number;
			blur: boolean;
		} | null;
	};

	const { post, images } = $props();

	let image_id = $derived(post.image_id);
	let open = $state(false);

	let creating = $state(false);
	let imageJobId = $state<number | null>(null);
	let imageJobError = $state('');

	async function pollImageJob(jobId: number) {
		imageJobId = jobId;
		imageJobError = '';

		while (true) {
			const response = await fetch(resolve(`/image-jobs/${jobId}`));
			if (!response.ok) {
				imageJobError = 'Unable to check image generation status';
				imageJobId = null;
				return;
			}
			const job = (await response.json()) as ImageJob;
			if (typeof job?.status === 'undefined') {
				imageJobError = 'Invalid image job response';
				imageJobId = null;
				return;
			}
			if (job.status === 'completed' && job.image_id) {
				post.image_id = job.image_id;
				if (job.image && !images.some((image: { id: number }) => image.id === job.image!.id)) {
					images.push(job.image);
				}
				imageJobId = null;
				open = false;
				return;
			}
			if (job.status === 'failed') {
				imageJobError = 'Image generation failed';
				imageJobId = null;
				return;
			}

			await new Promise((resolveDelay) => setTimeout(resolveDelay, 1500));
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
				void pollImageJob(body.id);
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
					post.image_id = image_id;
					open = false;
				}
			);
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
		<button
			type="submit"
			disabled={creating || imageJobId !== null}
			class="rounded-2xl px-3 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
		>
			{imageJobId !== null ? 'Generating...' : 'Set image'}
		</button>
		{#if imageJobError}
			<p class="mt-2 text-sm text-red-500">{imageJobError}</p>
		{/if}
	</form>
</Dialog>
