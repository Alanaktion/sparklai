<script lang="ts">
	import { loadJson } from '$lib/api';
	import Select from '$lib/components/base/select.svelte';
	import { Image, LetterText } from 'lucide-svelte';

	type ChatModel = {
		id: string;
	};
	type SDModel = {
		model_name: string;
	};

	let chat_models = $state<ChatModel[]>([]);
	let chat_model = $state<ChatModel | null>(null);
	let sd_models = $state<SDModel[]>([]);
	let sd_model = $state<SDModel | null>(null);
	loadJson('models').then((data) => {
		chat_models = data.chat_models;
		chat_model = data.chat_model;
		sd_models = data.sd_models;
		sd_model = data.sd_model;
	});
	$effect(() => {
		fetch('/models', {
			method: 'post',
			body: JSON.stringify({
				chat_model,
				sd_model
			})
		});
	});
</script>

<div
	class="flex flex-col justify-center mx-4 gap-2 py-4 opacity-25 transition-opacity focus-within:opacity-100 hover:opacity-100 sm:flex-row sm:items-center"
>
	<LetterText class="text-slate-400 dark:text-slate-500" />
	<Select bind:value={chat_model} class="max-w-3xs text-sm">
		{#each chat_models as model}
			<option value={model.id}>{model.id}</option>
		{/each}
	</Select>
	<div class="sm:mx-2"></div>
	<Image class="text-slate-400 dark:text-slate-500" />
	<Select bind:value={sd_model} class="max-w-3xs text-sm">
		{#each sd_models as model}
			<option value={model.model_name}>{model.model_name}</option>
		{/each}
	</Select>
</div>
