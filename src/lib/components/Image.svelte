<script lang="ts">
	import { escapeKey } from '$lib/actions/escape-key.svelte';
	import { hotkey } from '$lib/actions/hotkey.svelte';
	import Eclipse from 'virtual:icons/lucide/eclipse';
	import Trash2 from 'virtual:icons/lucide/trash-2';
	import { fade, slide } from 'svelte/transition';
	import { twMerge } from 'tailwind-merge';

	let { image } = $props();
	let params = $state(image.params);
	let lightbox = $state(false);

	let deleted = $state(false);
	function deleteImage() {
		fetch(`/images/${image.id}`, { method: 'DELETE' }).then(() => {
			lightbox = false;
			deleted = true;
		});
	}

	let blur = $state(image.blur);
	function toggleBlur() {
		blur = !blur;
		fetch(`/images/${image.id}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ blur })
		});
	}
</script>

<button
	type="button"
	onclick={() => (lightbox = true)}
	class={['relative block cursor-pointer overflow-hidden', deleted && 'opacity-25']}
>
	<img
		loading="lazy"
		src="/images/{image.id}"
		alt={params?.prompt}
		class="aspect-square w-full object-contain"
	/>
	{#if blur}
		<div
			class={[
				'group absolute inset-0 flex items-center justify-center backdrop-blur-xl transition hover:backdrop-blur-lg'
			]}
		></div>
	{/if}
</button>

{#if lightbox}
	<button
		type="button"
		onclick={() => (lightbox = false)}
		use:escapeKey={() => (lightbox = false)}
		in:fade={{ duration: 75 }}
		out:fade={{ duration: 75 }}
		class={twMerge(
			'grid place-content-center', // layout
			'fixed top-0 right-0 bottom-0 left-0 z-1000', // position
			'bg-gray-300/80 backdrop-blur-xs dark:bg-gray-900/80' // background
		)}
	>
		<img src="/images/{image.id}" alt={params?.prompt} />
	</button>
	<button
		onclick={toggleBlur}
		type="button"
		class="fixed top-3 right-12 z-1000 rounded p-1 text-sm text-blue-600 hover:bg-blue-200/50 dark:text-blue-400 dark:hover:bg-blue-700/50"
	>
		<span class="sr-only">Toggle image blur</span>
		<Eclipse class="size-4" />
	</button>
	<button
		onclick={deleteImage}
		use:hotkey={{ code: 'Digit3', shiftKey: true, onKeydown: deleteImage }}
		type="button"
		class="fixed top-3 right-3 z-1000 rounded p-1 text-sm text-red-600 hover:bg-red-200/50 dark:text-red-400 dark:hover:bg-red-700/50"
	>
		<span class="sr-only">Delete image</span>
		<Trash2 class="size-4" />
	</button>
	<p
		in:slide={{ duration: 75, delay: 250 }}
		out:slide={{ duration: 75 }}
		class="fixed inset-x-3 bottom-3 z-1000 text-xs leading-tight whitespace-pre-wrap"
	>
		{params?.prompt}
	</p>
{/if}
