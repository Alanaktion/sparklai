<script lang="ts">
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import type { Snippet } from 'svelte';
	import { twMerge } from 'tailwind-merge';
	import { Loader } from 'lucide-svelte';

	type Variant = 'default' | 'destructive';

	type Props = {
		children?: Snippet;
		class?: string | null;
		disabled?: boolean;
		loading?: boolean;
		variant?: Variant;
	} & HTMLButtonAttributes;

	let {
		children,
		class: className,
		disabled = false,
		loading = $bindable(false),
		variant = 'default',
		type = 'button',
		...props
	}: Props = $props();
</script>

<button
	class={twMerge(
		'relative flex cursor-pointer items-center gap-2 rounded', // base
		'w-full py-1 pr-12 pl-3', // box model
		'-outline-offset-1 outline-blue-500', // outline
		'hover:bg-blue-500/10 hover:outline', // hover
		'focus-visible:bg-blue-500/10 focus-visible:outline', // focus
		'active:outline-2 active:-outline-offset-2', // active

		variant === 'destructive' && [
			'text-rose-500 outline-rose-500',
			'hover:bg-rose-500/10 focus-visible:bg-rose-500/10'
		],

		(loading || disabled) && 'pointer-events-none cursor-not-allowed text-gray-400',

		className
	)}
	disabled={loading || disabled}
	{type}
	{...props}
>
	{#if loading}
		{@render IconSpinner()}
	{/if}
	{@render children?.()}
</button>

{#snippet IconSpinner()}
	<Loader class="absolute right-3 bottom-1/2 size-4 translate-y-1/2 animate-spin text-blue-500" />
{/snippet}
