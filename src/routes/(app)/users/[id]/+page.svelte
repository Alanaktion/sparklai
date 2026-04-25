<script lang="ts">
	import { browser } from '$app/environment';
	import { resolve } from '$app/paths';
	import Dialog from '$lib/components/base/dialog.svelte';
	import Post from '$lib/components/Post.svelte';
	import type { PostType } from '$lib/server/db/schema';
	import {
		dismissImageJob,
		failImageJobRequest,
		replaceImageJobRequest,
		startImageJobRequest,
		trackImageJob,
		type ImageGenerationJobResponse
	} from '$lib/stores/image-jobs';
	import SlideTextSparkle from 'virtual:icons/fluent-color/slide-text-sparkle-24';
	import Loader from 'virtual:icons/lucide/loader';
	import type { PageProps } from './$types';
	import { getUserProfileContext } from '$lib/user-profile-context';

	let { data }: PageProps = $props();
	const profileState = getUserProfileContext();

	type ImageJob = ImageGenerationJobResponse;
	type UserPagePost = PageProps['data']['posts'][number];

	type NewPostResponse = {
		post: PostType;
		image_job: ImageJob | null;
	};

	let posts = $derived(data.posts);
	let creating = $state(false);
	let open = $state(false);
	let prompt = $state('');
	let pendingImageJobIds = $state<number[]>([]);
	let recentlyQueuedImageJobIds = $state<number[]>([]);
	let imageJobError = $state('');

	function trackPendingJob(jobId: number) {
		if (!pendingImageJobIds.includes(jobId)) {
			pendingImageJobIds = [...pendingImageJobIds, jobId];
		}
	}

	function finishPendingJob(jobId: number) {
		pendingImageJobIds = pendingImageJobIds.filter((id) => id !== jobId);
		recentlyQueuedImageJobIds = recentlyQueuedImageJobIds.filter((id) => id !== jobId);
	}

	function trackPendingImageJob(jobId: number, postId: number) {
		trackPendingJob(jobId);
		imageJobError = '';

		void trackImageJob(jobId, { label: 'Post image' })
			.then((job) => {
				if (job.status === 'completed' && job.image_id) {
					if (job.image && !profileState.images.some((image) => image.id === job.image!.id)) {
						profileState.images = [...profileState.images, job.image];
					}
					posts = posts.map((post) =>
						post.id === postId
							? {
									...post,
									image_id: job.image_id
								}
							: post
					);
					return;
				}
				if (job.status === 'failed') {
					imageJobError = job.error || 'Image generation failed';
				}
			})
			.catch(() => {
				imageJobError = 'Unable to check image generation status';
			})
			.finally(() => {
				finishPendingJob(jobId);
			});
	}

	const newPost = (event: Event) => {
		event.preventDefault();
		creating = true;
		imageJobError = '';
		open = false;
		const pendingRequestId = startImageJobRequest({
			label: 'Post image',
			phase: 'prompt'
		});
		fetch(resolve(`/users/${data.id}/posts`), {
			method: 'POST',
			headers: {
				'Content-Type': 'application/x-www-form-urlencoded'
			},
			body: `prompt=${encodeURIComponent(prompt)}`
		})
			.then(async (response) => {
				if (!response.ok) {
					throw new Error('Post creation failed');
				}
				return (await response.json()) as NewPostResponse;
			})
			.then((body) => {
				const nextPost: UserPagePost = {
					...body.post,
					image: null,
					media: null
				};
				posts = [nextPost, ...posts];
				if (body.image_job && Number.isFinite(body.image_job.id)) {
					recentlyQueuedImageJobIds = [body.image_job.id, ...recentlyQueuedImageJobIds].slice(
						0,
						10
					);
					trackPendingJob(body.image_job.id);
					const [trackedJobPromise] = replaceImageJobRequest(pendingRequestId, [body.image_job], {
						label: 'Post image'
					});
					void trackedJobPromise
						.then((job) => {
							if (job.status === 'completed' && job.image_id) {
								if (job.image && !profileState.images.some((image) => image.id === job.image!.id)) {
									profileState.images = [...profileState.images, job.image];
								}
								posts = posts.map((post) =>
									post.id === body.post.id
										? {
												...post,
												image_id: job.image_id
											}
										: post
								);
								return;
							}
							if (job.status === 'failed') {
								imageJobError = job.error || 'Image generation failed';
							}
						})
						.catch(() => {
							imageJobError = 'Unable to check image generation status';
						})
						.finally(() => {
							finishPendingJob(body.image_job!.id);
						});
				} else {
					dismissImageJob(pendingRequestId);
				}
				creating = false;
				prompt = '';
			})
			.catch((error) => {
				creating = false;
				const message = error instanceof Error ? error.message : 'Unable to create post';
				failImageJobRequest(pendingRequestId, message, { label: 'Post image' });
				imageJobError = message;
			});
	};
</script>

<div class="mb-4 flex justify-end">
	{#if browser}
		<button
			onclick={() => (open = true)}
			type="button"
			class="rounded p-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
		>
			<span class="sr-only">Add AI post</span>
			<SlideTextSparkle class="size-4" />
		</button>
		<Dialog title="Add AI post" bind:open>
			<form class="grid gap-2" onsubmit={newPost} method="POST">
				<textarea
					bind:value={prompt}
					name="message"
					rows="6"
					class="flex w-full rounded border border-gray-300 bg-transparent px-2 py-1 text-sm shadow-sm transition-colors placeholder:text-gray-300 focus:border-blue-600 focus-visible:ring-1 focus-visible:ring-blue-500 focus-visible:outline-none disabled:opacity-50 dark:border-gray-500 dark:placeholder:text-gray-600"
					placeholder="Post prompt (optional)"
				></textarea>
				{#if creating}
					<Loader class="mx-auto my-2 size-4 animate-spin text-gray-600 dark:text-gray-400" />
				{:else}
					<button
						type="submit"
						class="rounded-2xl px-2 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
					>
						Create Post
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

{#key profileState.avatarRenderKey}
	{#each posts as post (post.id)}
		<Post {post} user={profileState.user} />
	{/each}
{/key}
