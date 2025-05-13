<script lang="ts">
	import '../app.css';
	import { Sparkles } from 'lucide-svelte';

	let { children } = $props();
</script>

<div class="flex items-center justify-center py-4 text-sky-600 xl:mb-4 dark:text-sky-400">
	<a href="/">
		<span class="sr-only">SparklAI</span>
		<Sparkles class="size-6" />
	</a>
</div>

{@render children()}
