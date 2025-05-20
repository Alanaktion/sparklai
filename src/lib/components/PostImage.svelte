<script lang="ts">
	import { fade } from 'svelte/transition';
	import { twMerge } from 'tailwind-merge';
	import { escapeKey } from '$lib/actions/escape-key.svelte';

	let { src, class: imgClass } = $props();
	let lightbox = $state(false);
</script>

<button type="button" onclick={() => (lightbox = true)} class="block cursor-pointer">
	<img {src} alt="" class={imgClass} />
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
			'bg-slate-300/80 backdrop-blur-xs dark:bg-slate-900/80' // background
		)}
	>
		<img {src} alt="" />
	</button>
{/if}
