<script lang="ts">
	import type { Snippet } from 'svelte';
	import { escapeKey } from '$lib/actions/escape-key.svelte';
	import { fade, scale } from 'svelte/transition';
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
			'fixed top-0 right-0 bottom-0 left-0 z-[999999999]', // position
			'bg-slate-900/80 backdrop-blur-xs', // background
		)}
	>
		<div
			use:focusTrap
			use:escapeKey={() => (open = false)}
			in:scale={{ duration: 75, delay: 75, start: 0.9 }}
			out:scale={{ duration: 75, start: 0.9 }}
			class={twMerge(
				'relative z-10', // layout and positioning
				'w-screen sm:w-max sm:min-w-md', // width
				'dark:bg-slate-900 text-left', // background and text
				'shadow-md dark:shadow-none', // shadow
				'border-y p-4 sm:rounded sm:border border-slate-300 dark:border-slate-800', // border
				className // override
			)}
		>
			<button
				class="outline-slate-400 absolute top-4 right-4 cursor-pointer rounded p-1 hover:outline"
				onclick={() => (open = false)}
			>
				{@render IconClose()}
			</button>

			{#if title}<p class="font-semibold mb-3">{title}</p>{/if}

			{@render children?.()}
		</div>
	</div>
{/if}

{#snippet IconClose()}
	<X class="size-4" />
{/snippet}
