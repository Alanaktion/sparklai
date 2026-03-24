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
	let chat_model = $state('');
	let sd_models = $state<SDModel[]>([]);
	let sd_backend = $state('automatic1111');
	let sd_style = $state('photo');
	let sd_model = $state('');
	let sd_supports_model_selection = $state(true);
	fetch('/models')
		.then((response) => response.json())
		.then((data) => {
			chat_models = data.chat_models;
			const availableChatModels = chat_models.map((model) => model.id);
			const initialChatModel =
				typeof data.chat_model === 'string' ? data.chat_model.trim() : '';
			chat_model =
				availableChatModels.find((modelId) => modelId === initialChatModel) ||
				availableChatModels[0] ||
				'';
			sd_models = data.sd_models;
			sd_backend = data.sd_backend;
			sd_style = data.sd_style;
			sd_model = typeof data.sd_model === 'string' ? data.sd_model : '';
			sd_supports_model_selection = data.sd_supports_model_selection;
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
				sd_backend = data.sd_backend;
				sd_supports_model_selection = data.sd_supports_model_selection;
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
				sd_backend = data.sd_backend;
				sd_supports_model_selection = data.sd_supports_model_selection;
			});
	}
</script>

<div
	class="mx-2 @sm:mx-4 flex flex-col justify-center gap-2 py-4 opacity-25 transition-opacity focus-within:opacity-100 hover:opacity-100 @sm:flex-row @sm:items-center"
>
	{#if chat_models.length}
		<ChatMultiple class="text-gray-400 dark:text-gray-500" />
		<Select bind:value={chat_model} {onchange} class="max-w-60 text-sm">
			{#each chat_models as model (model.id)}
				<option value={model.id}>{model.id}</option>
			{/each}
		</Select>
	{/if}
	<div class="@sm:mx-2"></div>
	{#if sd_models.length || !sd_supports_model_selection}
		<Image class="text-gray-400 dark:text-gray-500" />
		<Select bind:value={sd_style} {onchange} class="max-w-40 text-sm">
			<option value="photo">Photo</option>
			<option value="drawing">Drawing</option>
			<option value="stylized">Stylized</option>
		</Select>
		{#if sd_supports_model_selection && sd_models.length}
			<Select bind:value={sd_model} onchange={onchange_sd} class="max-w-60 text-sm">
				{#each sd_models as model (model.model_name)}
					<option value={model.model_name}>{model.model_name}</option>
				{/each}
			</Select>
		{:else}
			<span class="text-xs text-gray-400 dark:text-gray-500">{sd_backend}</span>
		{/if}
	{/if}
</div>
