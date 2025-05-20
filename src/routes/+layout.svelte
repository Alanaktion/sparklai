<script lang="ts">
	import '../app.css';
	import { browser } from '$app/environment';
	import { Sparkles } from 'lucide-svelte';
	import ModelSwitcher from '$lib/components/ModelSwitcher.svelte';

	let { children } = $props();
</script>

<div class="flex items-center justify-center py-4">
	<a href="/" class="text-sky-600 xl:mb-4 dark:text-sky-400">
		<span class="sr-only">SparklAI</span>
		<Sparkles class="size-6" />
	</a>
</div>

{@render children()}

{#if browser}
	<ModelSwitcher />
{/if}
