<script lang="ts">
	import { browser } from '$app/environment';
	import ModelSwitcher from '$lib/components/ModelSwitcher.svelte';
	import Sparkles from 'virtual:icons/lucide/sparkles';
	import Settings from 'virtual:icons/lucide/settings';
	import '../app.css';

	let { children } = $props();
</script>

<div class="flex items-center justify-between px-4 py-4">
	<a href="/" class="text-blue-600 xl:mb-4 dark:text-blue-400">
		<span class="sr-only">SparklAI</span>
		<Sparkles
			class="size-6 text-amber-500 *:first:fill-amber-400 *:first:stroke-none dark:*:first:fill-amber-300"
		/>
	</a>
	<a
		href="/settings"
		class="rounded-lg p-2 text-gray-600 transition hover:bg-gray-100 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
		title="Profile Settings"
	>
		<span class="sr-only">Settings</span>
		<Settings class="size-5" />
	</a>
</div>

{@render children()}

{#if browser}
	<ModelSwitcher />
{/if}
