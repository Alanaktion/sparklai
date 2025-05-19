<script lang="ts">
	import '../app.css';
	import Select from '$lib/components/base/select.svelte';
	import { browser } from '$app/environment';
	import { Image, LetterText, Sparkles } from 'lucide-svelte';

	let { children, data } = $props();
	let chat_model = $state(data.chat_model);
	let sd_model = $state(data.sd_model);
	$effect(() => {
		fetch('/images/model', {
			method: 'post',
			body: JSON.stringify({
				model: sd_model
			})
		});
	});
	$effect(() => {
		fetch('/posts/model', {
			method: 'post',
			body: JSON.stringify({
				model: chat_model
			})
		});
	});
</script>

<div class="flex items-center justify-center py-4">
	<a href="/" class="text-sky-600 xl:mb-4 dark:text-sky-400">
		<span class="sr-only">SparklAI</span>
		<Sparkles class="size-6" />
	</a>
</div>

{@render children()}

{#if browser}
	<div
		class="flex flex-col justify-center gap-2 py-4 opacity-25 transition-opacity focus-within:opacity-100 hover:opacity-100 sm:flex-row sm:items-center"
	>
		<LetterText class="text-slate-400 dark:text-slate-500" />
		<Select bind:value={chat_model} class="max-w-3xs text-sm">
			{#each data.chat_models as model}
				<option value={model.id}>{model.id}</option>
			{/each}
		</Select>
		<div class="sm:mx-2"></div>
		<Image class="text-slate-400 dark:text-slate-500" />
		<Select bind:value={sd_model} class="max-w-3xs text-sm">
			{#each data.sd_models as model}
				<option value={model.model_name}>{model.model_name}</option>
			{/each}
		</Select>
	</div>
{/if}
