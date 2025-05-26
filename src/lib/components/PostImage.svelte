<script lang="ts">
	import { escapeKey } from '$lib/actions/escape-key.svelte';
	import { fade, slide } from 'svelte/transition';
	import { twMerge } from 'tailwind-merge';

	let { src, class: imgClass, image = null } = $props();
	let params = $state(image?.params);
	let lightbox = $state(false);
</script>

<button
	type="button"
	onclick={() => (lightbox = true)}
	class="relative block cursor-pointer overflow-hidden"
>
	<img {src} alt="" loading="lazy" class={imgClass} />
	{#if image?.blur}
		<div
			class={[
				imgClass,
				'group absolute inset-0 flex items-center justify-center backdrop-blur-3xl transition hover:backdrop-blur-xl'
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
		<img {src} alt="" />
	</button>
	{#if params}
		<p
			in:slide={{ duration: 75, delay: 250 }}
			out:slide={{ duration: 75 }}
			class="fixed inset-x-3 bottom-3 z-1000 text-xs leading-tight whitespace-pre-wrap"
		>
			{params?.prompt}
		</p>
	{/if}
{/if}
