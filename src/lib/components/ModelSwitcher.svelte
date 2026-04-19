<script lang="ts">
	import { onMount } from 'svelte';
	import Select from '$lib/components/base/select.svelte';
	import ChatMultiple from 'virtual:icons/fluent-color/chat-multiple-24';
	import Image from 'virtual:icons/fluent-color/image-24';

	type ChatModel = {
		id: string;
	};
	type SDModel = {
		model_name: string;
	};
	type SDStyle = 'photo' | 'drawing' | 'stylized' | 'sdxl';
	type ModelsResponse = {
		chat_models?: ChatModel[];
		chat_model?: string;
		sd_backend?: string;
		sd_model?: string;
		sd_models?: SDModel[];
		sd_style?: string;
		sd_styles?: string[];
		sd_supports_model_selection?: boolean;
	};

	const storageKey = 'sparklai:model-switcher';
	const sdStyleNames: SDStyle[] = ['photo', 'drawing', 'stylized', 'sdxl'];
	const sdStyleLabels: Record<SDStyle, string> = {
		photo: 'Photo',
		drawing: 'Drawing',
		stylized: 'Stylized',
		sdxl: 'SDXL'
	};

	let chat_models = $state<ChatModel[]>([]);
	let chat_model = $state('');
	let sd_models = $state<SDModel[]>([]);
	let sd_styles = $state<SDStyle[]>(['photo', 'drawing', 'stylized', 'sdxl']);
	let sd_backend = $state('automatic1111');
	let sd_style = $state<SDStyle>('photo');
	let sd_model = $state('');
	let sd_supports_model_selection = $state(true);
	let isLoading = $state(true);
	let isSaving = $state(false);
	let activeRequestId = 0;

	function parseSdStyle(value: string | null | undefined): SDStyle | null {
		if (!value) {
			return null;
		}

		return sdStyleNames.find((styleName) => styleName === value) ?? null;
	}

	function readSessionState() {
		if (typeof sessionStorage === 'undefined') {
			return null;
		}

		try {
			const raw = sessionStorage.getItem(storageKey);
			if (!raw) {
				return null;
			}

			return JSON.parse(raw) as {
				chat_model?: string;
				sd_model?: string;
				sd_style?: string;
			};
		} catch {
			return null;
		}
	}

	function persistSessionState() {
		if (typeof sessionStorage === 'undefined') {
			return;
		}

		sessionStorage.setItem(
			storageKey,
			JSON.stringify({
				chat_model,
				sd_model,
				sd_style
			})
		);
	}

	function pickChatModel(preferred: string | null | undefined, availableModels: ChatModel[]) {
		const normalized = preferred?.trim();
		if (normalized && availableModels.some((model) => model.id === normalized)) {
			return normalized;
		}

		return availableModels[0]?.id ?? '';
	}

	function pickSdStyle(preferred: string | null | undefined, availableStyles: SDStyle[]) {
		const normalized = parseSdStyle(preferred);
		if (normalized && availableStyles.includes(normalized)) {
			return normalized;
		}

		return availableStyles[0] ?? 'photo';
	}

	function pickSdModel(preferred: string | null | undefined, availableModels: SDModel[]) {
		const normalized = preferred?.trim();
		if (normalized && availableModels.some((model) => model.model_name === normalized)) {
			return normalized;
		}

		return availableModels[0]?.model_name ?? '';
	}

	function applyResponse(data: ModelsResponse) {
		chat_models = Array.isArray(data.chat_models) ? data.chat_models : [];
		sd_models = Array.isArray(data.sd_models) ? data.sd_models : [];
		sd_backend = typeof data.sd_backend === 'string' ? data.sd_backend : sd_backend;
		sd_supports_model_selection = Boolean(data.sd_supports_model_selection);

		const availableStyles = Array.isArray(data.sd_styles)
			? data.sd_styles
					.map((styleName) => parseSdStyle(styleName))
					.filter((styleName): styleName is SDStyle => styleName !== null)
			: [];
		sd_styles = availableStyles.length ? availableStyles : sd_styles;

		chat_model = pickChatModel(data.chat_model, chat_models);
		sd_style = pickSdStyle(data.sd_style, sd_styles);
		sd_model = sd_supports_model_selection ? pickSdModel(data.sd_model, sd_models) : '';
		persistSessionState();
	}

	async function syncModels(method: 'GET' | 'POST', body?: Record<string, string>) {
		const requestId = ++activeRequestId;
		const response = await fetch('/models', {
			method,
			headers: body
				? {
						'Content-Type': 'application/json'
					}
				: undefined,
			body: body ? JSON.stringify(body) : undefined
		});

		if (!response.ok) {
			throw new Error(`Model sync failed with ${response.status}`);
		}

		const data = (await response.json()) as ModelsResponse;
		if (requestId !== activeRequestId) {
			return;
		}

		applyResponse(data);
	}

	async function loadModels() {
		isLoading = true;
		try {
			await syncModels('GET');
		} finally {
			isLoading = false;
		}
	}

	async function updateModels(body: Record<string, string>) {
		persistSessionState();
		isSaving = true;
		try {
			await syncModels('POST', body);
		} finally {
			isSaving = false;
		}
	}

	function onchange_chat() {
		void updateModels({
			chat_model,
			sd_style
		});
	}

	function onchange_style() {
		sd_model = '';
		persistSessionState();
		void updateModels({
			chat_model,
			sd_style
		});
	}

	function onchange_sd() {
		void updateModels({
			chat_model,
			sd_model
		});
	}

	onMount(() => {
		const stored = readSessionState();
		if (stored?.chat_model) {
			chat_model = stored.chat_model;
		}
		if (stored?.sd_style) {
			const storedStyle = parseSdStyle(stored.sd_style);
			if (storedStyle) {
				sd_style = storedStyle;
			}
		}
		if (stored?.sd_model) {
			sd_model = stored.sd_model;
		}

		void loadModels();
	});
</script>

<div
	aria-busy={isLoading || isSaving}
	class="mx-2 flex flex-wrap items-center justify-center gap-2 py-4 opacity-25 transition-opacity focus-within:opacity-100 hover:opacity-100 @sm:mx-4"
>
	{#if chat_models.length}
		<ChatMultiple class="text-gray-400 dark:text-gray-500" />
		<Select
			bind:value={chat_model}
			onchange={onchange_chat}
			class="max-w-60 text-sm"
			disabled={isLoading || isSaving}
		>
			{#each chat_models as model (model.id)}
				<option value={model.id}>{model.id}</option>
			{/each}
		</Select>
	{/if}
	<div class="@sm:mx-2"></div>
	{#if sd_models.length || !sd_supports_model_selection}
		<Image class="text-gray-400 dark:text-gray-500" />
		<Select
			bind:value={sd_style}
			onchange={onchange_style}
			class="max-w-40 text-sm"
			disabled={isLoading || isSaving}
		>
			{#each sd_styles as styleName (styleName)}
				<option value={styleName}>{sdStyleLabels[styleName]}</option>
			{/each}
		</Select>
		{#if sd_supports_model_selection && sd_models.length}
			<Select
				bind:value={sd_model}
				onchange={onchange_sd}
				class="max-w-60 text-sm"
				disabled={isLoading || isSaving}
			>
				{#each sd_models as model (model.model_name)}
					<option value={model.model_name}>{model.model_name}</option>
				{/each}
			</Select>
		{:else}
			<span class="text-xs text-gray-400 dark:text-gray-500">{sd_backend}</span>
		{/if}
	{/if}
</div>
