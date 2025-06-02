<script lang="ts">
	import { browser } from '$app/environment';
	import ModelSwitcher from '$lib/components/ModelSwitcher.svelte';
	import Sparkles from 'virtual:icons/lucide/sparkles';
	import '../app.css';

	let { children } = $props();
</script>

<div class="flex items-center justify-center py-4">
	<a href="/" class="text-blue-600 xl:mb-4 dark:text-blue-400">
		<span class="sr-only">SparklAI</span>
		<Sparkles
			class="size-6 text-amber-500 *:first:fill-amber-400 *:first:stroke-none dark:*:first:fill-amber-300"
		/>
	</a>
</div>

{@render children()}

{#if browser}
	<ModelSwitcher />
{/if}
