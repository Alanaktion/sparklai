<script lang="ts">
	import Select from '$lib/components/base/select.svelte';
	import ChatMultiple from 'virtual:icons/fluent-color/chat-multiple-24';
	import Image from 'virtual:icons/fluent-color/image-24';

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
	let sd_model = $state<SDModel | null>(null);
	fetch('/models')
		.then((response) => response.json())
		.then((data) => {
			chat_models = data.chat_models;
			chat_model = data.chat_model;
			sd_models = data.sd_models;
			sd_style = data.sd_style;
			sd_model = data.sd_model;
		});

	function onchange() {
		fetch('/models', {
			method: 'post',
			body: JSON.stringify({
				chat_model,
				sd_style
			})
		})
			.then((response) => response.json())
			.then((data) => {
				sd_model = data.sd_model;
			});
	}
	function onchange_sd() {
		fetch('/models', {
			method: 'post',
			body: JSON.stringify({
				chat_model,
				sd_model
			})
		})
			.then((response) => response.json())
			.then((data) => {
				sd_model = data.sd_model;
			});
	}
</script>

<div
	class="mx-4 flex flex-col justify-center gap-2 py-4 opacity-25 transition-opacity focus-within:opacity-100 hover:opacity-100 sm:flex-row sm:items-center"
>
	{#if chat_models.length}
		<ChatMultiple class="text-gray-400 dark:text-gray-500" />
		<Select bind:value={chat_model} {onchange} class="max-w-60 text-sm">
			{#each chat_models as model}
				<option value={model.id}>{model.id}</option>
			{/each}
		</Select>
	{/if}
	<div class="sm:mx-2"></div>
	{#if sd_models.length}
		<Image class="text-gray-400 dark:text-gray-500" />
		<Select bind:value={sd_style} {onchange} class="max-w-40 text-sm">
			<option value="photo">Photo</option>
			<option value="drawing">Drawing</option>
			<option value="stylized">Stylized</option>
		</Select>
		<Select bind:value={sd_model} onchange={onchange_sd} class="max-w-60 text-sm">
			{#each sd_models as model}
				<option value={model.model_name}>{model.model_name}</option>
			{/each}
		</Select>
	{/if}
</div>
