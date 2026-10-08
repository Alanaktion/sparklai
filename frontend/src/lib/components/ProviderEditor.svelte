<script lang="ts">
	import {
		createProvider,
		updateProvider,
		type Provider,
		type ProviderInput,
		type ProviderType
	} from '#lib/api.js';
	import { auth } from '#lib/auth.svelte.js';
	import { errorMessage } from '#lib/errors.js';
	import { untrack } from 'svelte';

	type Props = {
		provider?: Provider | null;
		onSaved: (provider: Provider) => void;
		onCancel: () => void;
	};

	let { provider = null, onSaved, onCancel }: Props = $props();

	const PROVIDER_TYPES: ProviderType[] = [
		'openai',
		'anthropic',
		'ollama',
		'koboldcpp',
		'custom',
		'comfyui'
	];

	// The editor is mounted fresh for each provider, so the form fields are an
	// intentional one-time snapshot of the given provider.
	const initial = untrack(() => ({
		name: provider?.name ?? '',
		providerType: provider?.provider_type ?? ('openai' as ProviderType),
		baseUrl: provider?.base_url ?? '',
		model: provider?.model ?? '',
		temperature: provider?.temperature?.toString() ?? '',
		maxTokens: provider?.max_tokens?.toString() ?? '',
		topP: provider?.top_p?.toString() ?? '',
		extraParams:
			provider && Object.keys(provider.extra_params).length > 0
				? JSON.stringify(provider.extra_params, null, 2)
				: ''
	}));

	let name = $state(initial.name);
	let providerType = $state<ProviderType>(initial.providerType);
	let baseUrl = $state(initial.baseUrl);
	let model = $state(initial.model);
	let apiKey = $state('');
	let clearKey = $state(false);
	let temperature = $state(initial.temperature);
	let maxTokens = $state(initial.maxTokens);
	let topP = $state(initial.topP);
	let extraParams = $state(initial.extraParams);

	let busy = $state(false);
	let error = $state<string | null>(null);

	// A ComfyUI provider generates images, not chat replies: it has no "model"
	// in the chat sense (the workflow's own checkpoint default is used unless
	// overridden here), and its settings live entirely in the JSON below.
	const isComfyUI = $derived(providerType === 'comfyui');

	function numberOrNull(value: string): number | null {
		const trimmed = value.trim();
		if (!trimmed) return null;
		const parsed = Number(trimmed);
		return Number.isFinite(parsed) ? parsed : null;
	}

	function parseExtra(): Record<string, unknown> | null {
		const raw = extraParams.trim();
		if (!raw) return null;
		const parsed: unknown = JSON.parse(raw);
		if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
			throw new Error('Extra params must be a JSON object.');
		}
		return parsed as Record<string, unknown>;
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		const token = auth.token;
		if (!token) {
			error = 'You are signed out.';
			return;
		}

		let extra: Record<string, unknown> | null;
		try {
			extra = parseExtra();
		} catch (cause) {
			error = errorMessage(cause);
			return;
		}

		busy = true;
		error = null;
		try {
			const saved = provider
				? await updateProvider(token, provider.id, patchFor(extra))
				: await createProvider(token, createFor(extra));
			onSaved(saved);
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			busy = false;
		}
	}

	function createFor(extra: Record<string, unknown> | null): ProviderInput {
		const input: ProviderInput = {
			name: name.trim(),
			provider_type: providerType,
			base_url: baseUrl.trim() || null,
			model: model.trim(),
			temperature: numberOrNull(temperature),
			max_tokens: numberOrNull(maxTokens),
			top_p: numberOrNull(topP),
			extra_params: extra ?? {}
		};
		if (apiKey.trim()) input.api_key = apiKey.trim();
		return input;
	}

	function patchFor(extra: Record<string, unknown> | null): Partial<ProviderInput> {
		const patch: Partial<ProviderInput> = {
			name: name.trim(),
			provider_type: providerType,
			model: model.trim(),
			temperature: numberOrNull(temperature),
			max_tokens: numberOrNull(maxTokens),
			top_p: numberOrNull(topP)
		};
		if (baseUrl.trim()) patch.base_url = baseUrl.trim();
		if (extra) patch.extra_params = extra;
		if (clearKey) patch.api_key = null;
		else if (apiKey.trim()) patch.api_key = apiKey.trim();
		return patch;
	}
</script>

<form class="editor" onsubmit={submit}>
	<div class="row">
		<label>
			<span>Name</span>
			<input bind:value={name} required maxlength="100" />
		</label>
		<label>
			<span>Type</span>
			<select bind:value={providerType}>
				{#each PROVIDER_TYPES as option (option)}
					<option value={option}>{option}</option>
				{/each}
			</select>
		</label>
	</div>

	<div class="row">
		<label>
			<span>Base URL <em>optional</em></span>
			<input bind:value={baseUrl} maxlength="500" placeholder="Use the type default" />
		</label>
		<label>
			<span>Model {#if isComfyUI}<em>optional</em>{/if}</span>
			<input
				bind:value={model}
				required={!isComfyUI}
				maxlength="200"
				placeholder={isComfyUI
					? 'Checkpoint/UNet override, e.g. sd_xl_base_1.0.safetensors'
					: ''}
			/>
		</label>
	</div>

	<label>
		<span>
			API key
			<em>
				{provider?.has_api_key ? 'stored — leave blank to keep' : 'optional'}
				{isComfyUI ? '(sent as x-api-key)' : ''}
			</em>
		</span>
		<input type="password" bind:value={apiKey} autocomplete="off" maxlength="500" />
	</label>
	{#if provider?.has_api_key}
		<label class="inline">
			<input type="checkbox" bind:checked={clearKey} />
			<span>Clear the stored API key</span>
		</label>
	{/if}

	{#if !isComfyUI}
		<div class="row">
			<label>
				<span>Temperature</span>
				<input bind:value={temperature} inputmode="decimal" />
			</label>
			<label>
				<span>Max tokens</span>
				<input bind:value={maxTokens} inputmode="numeric" />
			</label>
			<label>
				<span>Top P</span>
				<input bind:value={topP} inputmode="decimal" />
			</label>
		</div>
	{/if}

	<label>
		<span>Extra params <em>JSON object, optional</em></span>
		<textarea bind:value={extraParams} rows="3" spellcheck="false"></textarea>
	</label>
	{#if isComfyUI}
		<p class="hint">
			Recognized keys: <code>workflow</code> (one of <code>image</code>, <code>anime</code>,
			<code>sdxl</code>, <code>video</code>, <code>z_image_turbo</code>, or <code>custom</code> —
			defaults to <code>image</code>), <code>workflow_json</code> (required when
			<code>workflow</code> is <code>custom</code>: a raw ComfyUI node graph using
			<code>__POSITIVE_PROMPT__</code>/<code>__NEGATIVE_PROMPT__</code>/<code>__WIDTH__</code>/
			<code>__HEIGHT__</code>/<code>__SEED__</code>/<code>__MODEL__</code> placeholders),
			<code>width</code>, <code>height</code>, <code>negative_prompt</code>,
			<code>duration</code> (video frames), and <code>filename_prefix</code>.
		</p>
	{/if}

	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}

	<div class="actions">
		<button class="primary" type="submit" disabled={busy}>
			{busy ? 'Saving…' : provider ? 'Save provider' : 'Create provider'}
		</button>
		<button type="button" onclick={onCancel} disabled={busy}>Cancel</button>
	</div>
</form>

<style>
	.editor {
		display: grid;
		gap: 0.6rem;
		padding: 0.75rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
	}

	.row label {
		flex: 1 1 10rem;
	}

	.hint {
		margin: -0.3rem 0 0;
		font-size: 0.78rem;
		color: var(--muted);
	}

	.hint code {
		font-size: 0.85em;
	}

	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.85rem;
	}

	label em {
		margin-left: 0.35rem;
		font-style: normal;
		font-size: 0.75rem;
		color: var(--muted);
	}

	.inline {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}

	.actions {
		display: flex;
		gap: 0.5rem;
	}

	.actions button {
		min-width: 8.5rem;
	}
</style>
