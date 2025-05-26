<script lang="ts">
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import type { Snippet } from 'svelte';

	type Props = {
		active?: string;
		children?: Snippet;
		class?: string;
		disabled?: boolean;
		value?: string;
		onclick?: () => void;
	} & HTMLButtonAttributes;

	let {
		active = $bindable(),
		children,
		class: className,
		disabled = false,
		value = '',
		onclick,
		...props
	}: Props = $props();

	function handleOnClick() {
		active = value;
		onclick?.();
	}
</script>

<button
	class="cursor-pointer {active === value ? 'border-blue-500' : 'border-transparent'} border-b-2"
	type="button"
	onclick={handleOnClick}
	{disabled}
>
	{@render children?.()}
</button>
