<script lang="ts">
	import Select from '$lib/components/base/select.svelte';
	import ChatMultiple from '$lib/icons/ChatMultiple.svelte';
	import Image from '$lib/icons/Image.svelte';

	type ChatModel = {
		id: string;
	};
	type SDModel = {
		model_name: string;
	};

	let chat_models = $state<ChatModel[]>([]);
	let chat_model = $state<ChatModel | null>(null);
	let sd_models = $state<SDModel[]>([]);
	let sd_style = $state('photo');
	fetch('/models')
		.then((response) => response.json())
		.then((data) => {
			chat_models = data.chat_models;
			chat_model = data.chat_model;
			sd_models = data.sd_models;
			sd_style = data.sd_style;
		});

	function onchange() {
		fetch('/models', {
			method: 'post',
			body: JSON.stringify({
				chat_model,
				sd_style,
			})
		});
	}
</script>

<div
	class="mx-4 flex flex-col justify-center gap-2 py-4 opacity-25 transition-opacity focus-within:opacity-100 hover:opacity-100 sm:flex-row sm:items-center"
>
	{#if chat_models.length}
		<ChatMultiple class="text-gray-400 dark:text-gray-500" />
		<Select bind:value={chat_model} onchange={onchange} class="max-w-60 text-sm">
			{#each chat_models as model}
				<option value={model.id}>{model.id}</option>
			{/each}
		</Select>
	{/if}
	<div class="sm:mx-2"></div>
	{#if sd_models.length}
		<Image class="text-gray-400 dark:text-gray-500" />
		<Select bind:value={sd_style} onchange={onchange} class="max-w-40 text-sm">
			<option value="photo">Photo</option>
			<option value="drawing">Drawing</option>
			<option value="stylized">Stylized</option>
		</Select>
	{/if}
</div>
