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
	class="relative flex w-fit items-center rounded bg-gray-50 text-gray-950 dark:bg-gray-700 dark:text-gray-100"
>
	<select
		class={twMerge(
			'w-fit py-1 pr-10 pl-2', // box sizing
			'cursor-pointer appearance-none rounded border border-gray-300 dark:border-gray-600', // visual
			'outline-0 outline-blue-500 hover:outline focus:outline', // outline
			disabled && 'cursor-not-allowed bg-gray-200 text-gray-400 outline-none dark:bg-gray-800',
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
		class="pointer-events-none absolute right-2 size-5 text-gray-400 dark:text-gray-600"
	/>
{/snippet}
