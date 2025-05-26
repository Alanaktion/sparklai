<script lang="ts">
	import type { Snippet } from 'svelte';
	import { escapeKey } from '$lib/actions/escape-key.svelte';
	import { fade } from 'svelte/transition';
	import { focusTrap } from '$lib/actions/focus-trap.svelte';
	import { twMerge } from 'tailwind-merge';
	import { X } from 'lucide-svelte';

	type Props = {
		children?: Snippet;
		class?: string;
		open: boolean;
		title?: string;
	};

	let { children, class: className, open = $bindable(false), title = '' }: Props = $props();
</script>

{#if open}
	<div
		in:fade={{ duration: 75 }}
		out:fade={{ duration: 75 }}
		class={twMerge(
			'grid place-content-center', // layout
			'fixed top-0 right-0 bottom-0 left-0 z-1000', // position
			'bg-gray-300/80 backdrop-blur-xs dark:bg-gray-900/80' // background
		)}
	>
		<div
			use:focusTrap
			use:escapeKey={() => (open = false)}
			class={twMerge(
				'relative z-10 max-h-[80vh] overflow-y-auto', // layout and positioning
				'w-screen sm:w-max sm:min-w-md', // width
				'bg-white text-left dark:bg-gray-900', // background and text
				'shadow-md dark:shadow-none', // shadow
				'border-y border-gray-300 p-4 sm:rounded sm:border dark:border-gray-800', // border
				className // override
			)}
		>
			<button
				class="absolute top-4 right-4 cursor-pointer rounded p-1 outline-gray-400 hover:outline"
				onclick={() => (open = false)}
			>
				{@render IconClose()}
			</button>

			{#if title}<p class="mb-3 font-semibold">{title}</p>{/if}

			{@render children?.()}
		</div>
	</div>
{/if}

{#snippet IconClose()}
	<X class="size-4" />
{/snippet}
