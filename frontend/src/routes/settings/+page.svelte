<script lang="ts">
	import {
		deleteProvider,
		getSettings,
		listProviders,
		testProvider,
		updateSettings,
		type Provider,
		type ProviderTestResult,
		type UserSettings
	} from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import ProviderEditor from '$lib/components/ProviderEditor.svelte';
	import { errorMessage } from '$lib/errors';

	let settings = $state<UserSettings | null>(null);
	let providers = $state<Provider[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let notice = $state<string | null>(null);

	let displayName = $state('');
	let systemPrompt = $state('');
	let ujb = $state('');
	let savingBasics = $state(false);

	let creating = $state(false);
	let editingId = $state<number | null>(null);
	let testing = $state<number | null>(null);
	let testResults = $state<Record<number, ProviderTestResult>>({});

	$effect(() => {
		void load();
	});

	async function load() {
		const token = auth.token;
		if (!token) return;
		loading = true;
		error = null;
		try {
			const [loadedSettings, loadedProviders] = await Promise.all([
				getSettings(token),
				listProviders(token)
			]);
			settings = loadedSettings;
			providers = loadedProviders;
			displayName = loadedSettings.display_name;
			systemPrompt = loadedSettings.default_system_prompt;
			ujb = loadedSettings.default_ujb;
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			loading = false;
		}
	}

	async function reloadProviders() {
		const token = auth.token;
		if (!token) return;
		try {
			providers = await listProviders(token);
		} catch (cause) {
			error = errorMessage(cause);
		}
	}

	async function saveBasics(event: SubmitEvent) {
		event.preventDefault();
		const token = auth.token;
		if (!token) return;
		savingBasics = true;
		error = null;
		notice = null;
		try {
			settings = await updateSettings(token, {
				display_name: displayName,
				default_system_prompt: systemPrompt,
				default_ujb: ujb
			});
			notice = 'Saved.';
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			savingBasics = false;
		}
	}

	async function changeDefaultProvider(event: Event) {
		const token = auth.token;
		if (!token) return;
		const value = (event.currentTarget as HTMLSelectElement).value;
		try {
			settings = await updateSettings(token, {
				default_provider_id: value ? Number(value) : null
			});
		} catch (cause) {
			error = errorMessage(cause);
		}
	}

	async function onSaved() {
		creating = false;
		editingId = null;
		await reloadProviders();
	}

	async function test(provider: Provider) {
		const token = auth.token;
		if (!token) return;
		testing = provider.id;
		try {
			const result = await testProvider(token, provider.id);
			testResults = { ...testResults, [provider.id]: result };
		} catch (cause) {
			testResults = {
				...testResults,
				[provider.id]: { ok: false, message: errorMessage(cause), reply: null }
			};
		} finally {
			testing = null;
		}
	}

	async function remove(provider: Provider) {
		if (!confirm(`Delete provider “${provider.name}”?`)) return;
		const token = auth.token;
		if (!token) return;
		error = null;
		try {
			await deleteProvider(token, provider.id);
			await reloadProviders();
		} catch (cause) {
			error = errorMessage(cause);
		}
	}
</script>

<svelte:head>
	<title>Settings · Sparkl Chat</title>
</svelte:head>

<main class="page">
	<h1>Settings</h1>

	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}

	{#if loading}
		<p class="muted">Loading settings…</p>
	{:else}
		<section class="section">
			<h2>Account &amp; defaults</h2>
			<form class="basics" onsubmit={saveBasics}>
				<label>
					<span>Display name</span>
					<input bind:value={displayName} maxlength="80" placeholder="How should we greet you?" />
				</label>
				<label>
					<span>Default provider</span>
					<select value={settings?.default_provider_id ?? ''} onchange={changeDefaultProvider}>
						<option value="">None</option>
						{#each providers as provider (provider.id)}
							<option value={provider.id}>{provider.name}</option>
						{/each}
					</select>
				</label>
				<label>
					<span>Default system prompt</span>
					<textarea bind:value={systemPrompt} rows="4"></textarea>
				</label>
				<label>
					<span>Default UJB (post-history instructions)</span>
					<textarea bind:value={ujb} rows="4"></textarea>
				</label>
				<div class="actions">
					<button class="primary" type="submit" disabled={savingBasics}>
						{savingBasics ? 'Saving…' : 'Save'}
					</button>
					{#if notice}
						<span class="saved">{notice}</span>
					{/if}
				</div>
			</form>
		</section>

		<section class="section">
			<h2>Providers</h2>

			{#if providers.length === 0 && !creating}
				<p class="muted">No providers yet. Add one to start chatting.</p>
			{/if}

			<ul class="providers">
				{#each providers as provider (provider.id)}
					<li class="provider">
						<div class="head">
							<div class="who">
								<strong>{provider.name}</strong>
								<span class="muted">
									{provider.provider_type} · {provider.model}{provider.is_default
										? ' · default'
										: ''}
								</span>
							</div>
							<div class="controls">
								<button onclick={() => test(provider)} disabled={testing === provider.id}>
									{testing === provider.id ? 'Testing…' : 'Test'}
								</button>
								<button
									onclick={() => {
										editingId = editingId === provider.id ? null : provider.id;
										creating = false;
									}}
								>
									{editingId === provider.id ? 'Close' : 'Edit'}
								</button>
								<button class="danger" onclick={() => remove(provider)}>Delete</button>
							</div>
						</div>

						{#if testResults[provider.id]}
							{@const result = testResults[provider.id]}
							<p class="result" class:ok={result.ok} class:error={!result.ok} role="status">
								{result.message}
								{#if result.reply}
									<span class="muted">— “{result.reply}”</span>
								{/if}
							</p>
						{/if}

						{#if editingId === provider.id}
							<ProviderEditor
								{provider}
								onSaved={onSaved}
								onCancel={() => (editingId = null)}
							/>
						{/if}
					</li>
				{/each}
			</ul>

			{#if creating}
				<ProviderEditor onSaved={onSaved} onCancel={() => (creating = false)} />
			{:else}
				<button
					class="primary"
					onclick={() => {
						creating = true;
						editingId = null;
					}}
				>
					Add provider
				</button>
			{/if}
		</section>
	{/if}
</main>

<style>
	.section {
		margin-top: 1.75rem;
	}

	.section h2 {
		margin: 0 0 0.75rem;
		font-size: 0.95rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
	}

	.basics {
		display: grid;
		gap: 0.75rem;
		max-width: 40rem;
	}

	.basics label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.88rem;
	}

	.actions {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}

	.saved {
		font-size: 0.85rem;
		color: var(--muted);
	}

	.providers {
		display: grid;
		gap: 0.75rem;
		margin: 0 0 1rem;
		padding: 0;
		list-style: none;
	}

	.provider {
		display: grid;
		gap: 0.6rem;
		padding: 0.75rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.head {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		align-items: center;
		justify-content: space-between;
	}

	.who {
		display: grid;
		gap: 0.1rem;
	}

	.who span {
		font-size: 0.82rem;
	}

	.controls {
		display: flex;
		gap: 0.4rem;
	}

	.controls button {
		padding: 0.3rem 0.6rem;
		font-size: 0.85rem;
	}

	.result {
		margin: 0;
		font-size: 0.85rem;
	}

	.ok {
		color: #2da44e;
	}
</style>
