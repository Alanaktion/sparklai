<script lang="ts">
	import { ChevronDown } from 'lucide-svelte';
	import type { Snippet } from 'svelte';
	import type { HTMLSelectAttributes } from 'svelte/elements';
	import { twMerge } from 'tailwind-merge';

	type Props = {
		children?: Snippet;
		class?: string;
		disabled?: boolean;
		open?: boolean;
		value?: any;
	} & HTMLSelectAttributes;

	let {
		children,
		class: className,
		disabled = false,
		value = $bindable(),
		...props
	}: Props = $props();
</script>

<!-- Customize container here -->
<div
	class="relative flex w-fit items-center rounded bg-slate-50 text-slate-950 dark:bg-slate-700 dark:text-slate-100"
>
	<select
		class={twMerge(
			'w-fit py-1 pr-10 pl-2', // box sizing
			'cursor-pointer appearance-none rounded border border-slate-300 dark:border-slate-600', // visual
			'outline-0 outline-sky-500 hover:outline focus:outline', // outline
			disabled && 'cursor-not-allowed bg-slate-200 text-slate-400 outline-none dark:bg-slate-800',
			className
		)}
		{disabled}
		{...props}
		bind:value
	>
		{@render children?.()}
	</select>

	{@render ArrowDown()}
</div>

<!-- Customize icon for indicator -->
{#snippet ArrowDown()}
	<ChevronDown
		class="pointer-events-none absolute right-2 size-5 text-slate-400 dark:text-slate-600"
	/>
{/snippet}
