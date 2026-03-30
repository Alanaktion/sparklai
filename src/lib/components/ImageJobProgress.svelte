<script lang="ts">
	import { onMount } from 'svelte';
	import Check from 'virtual:icons/lucide/check';
	import Loader from 'virtual:icons/lucide/loader';
	import TriangleAlert from 'virtual:icons/lucide/triangle-alert';
	import X from 'virtual:icons/lucide/x';
	import { dismissImageJob, imageJobs, initImageJobTracker } from '$lib/stores/image-jobs';
	import type { ImageJobStatus, TrackedImageJob } from '$lib/stores/image-jobs';

	let collapsed = $state(false);

	onMount(() => {
		initImageJobTracker();
	});

	function isActive(status: ImageJobStatus) {
		return status === 'queued' || status === 'processing';
	}

	function statusLabel(job: TrackedImageJob) {
		if (job.status === 'queued') {
			return 'Queued';
		}
		if (job.status === 'processing') {
			return 'Generating';
		}
		if (job.status === 'completed') {
			return 'Completed';
		}
		return 'Failed';
	}

	let activeCount = $derived(
		$imageJobs.filter((job) => job.status === 'queued' || job.status === 'processing').length
	);
</script>

{#if $imageJobs.length}
	<section class="pointer-events-none fixed right-4 bottom-4 z-50 w-80 max-w-[calc(100vw-2rem)]">
		<div
			class="pointer-events-auto overflow-hidden rounded-xl border border-gray-200 bg-white/95 shadow-lg backdrop-blur dark:border-gray-700 dark:bg-gray-900/95"
		>
			<button
				type="button"
				onclick={() => (collapsed = !collapsed)}
				class="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium text-gray-800 hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-gray-800"
			>
				<span>Image Jobs</span>
				<span class="text-xs text-gray-500 dark:text-gray-400">
					{activeCount} active / {$imageJobs.length} tracked
				</span>
			</button>

			{#if !collapsed}
				<div class="max-h-72 overflow-auto border-t border-gray-200 dark:border-gray-700">
					{#each $imageJobs as job (job.id)}
						<div
							class="flex items-start gap-2 px-3 py-2 text-sm even:bg-gray-50/60 dark:even:bg-gray-800/50"
						>
							{#if isActive(job.status)}
								<Loader
									class="mt-0.5 size-4 shrink-0 animate-spin text-blue-600 dark:text-blue-400"
								/>
							{:else if job.status === 'completed'}
								<Check class="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
							{:else}
								<TriangleAlert class="mt-0.5 size-4 shrink-0 text-rose-600 dark:text-rose-400" />
							{/if}
							<div class="min-w-0 flex-1">
								<p class="truncate font-medium text-gray-800 dark:text-gray-100">{job.label}</p>
								<p class="truncate text-xs text-gray-500 dark:text-gray-400">
									Job #{job.id} • {statusLabel(job)}
									{#if job.error}
										• {job.error}
									{/if}
								</p>
							</div>
							{#if !isActive(job.status)}
								<button
									type="button"
									onclick={() => dismissImageJob(job.id)}
									class="rounded p-1 text-gray-500 hover:bg-gray-200 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-200"
								>
									<span class="sr-only">Dismiss job</span>
									<X class="size-3.5" />
								</button>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</section>
{/if}
