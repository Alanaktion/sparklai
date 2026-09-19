<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	import {
		deleteCharacter,
		listCharacters,
		uploadCharacter,
		type CharacterSummary
	} from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import { errorMessage } from '$lib/errors';

	let characters = $state<CharacterSummary[]>([]);
	let loading = $state(true);
	let uploading = $state(false);
	let error = $state<string | null>(null);
	let search = $state('');

	const query = $derived(page.url.searchParams.get('q') ?? '');
	let requestId = 0;

	$effect(() => {
		const active = query;
		search = active;
		void load(active);
	});

	async function load(q: string) {
		const token = auth.token;
		if (!token) return;
		const id = ++requestId;
		loading = true;
		error = null;
		try {
			const result = await listCharacters(token, q);
			if (id === requestId) characters = result;
		} catch (cause) {
			if (id === requestId) error = errorMessage(cause);
		} finally {
			if (id === requestId) loading = false;
		}
	}

	function submitSearch(event: SubmitEvent) {
		event.preventDefault();
		const trimmed = search.trim();
		void goto(trimmed ? `/characters?q=${encodeURIComponent(trimmed)}` : '/characters');
	}

	async function onFileChange(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file) return;

		const token = auth.token;
		if (!token) return;

		uploading = true;
		error = null;
		try {
			await uploadCharacter(token, file);
			await load(query);
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			uploading = false;
		}
	}

	async function remove(character: CharacterSummary) {
		if (!confirm(`Delete “${character.name}”? This cannot be undone.`)) return;
		const token = auth.token;
		if (!token) return;

		error = null;
		try {
			await deleteCharacter(token, character.id);
			characters = characters.filter((item) => item.id !== character.id);
		} catch (cause) {
			error = errorMessage(cause);
		}
	}
</script>

<svelte:head>
	<title>Characters · Sparkl Chat</title>
</svelte:head>

<main class="page">
	<div class="header">
		<h1>Characters</h1>
		<label class="upload">
			<span>{uploading ? 'Importing…' : 'Import card (PNG or JSON)'}</span>
			<input
				type="file"
				accept=".png,.json,image/png,application/json"
				onchange={onFileChange}
				disabled={uploading}
			/>
		</label>
	</div>

	<form class="search" onsubmit={submitSearch}>
		<input
			type="search"
			bind:value={search}
			placeholder="Search by name…"
			aria-label="Search characters by name"
		/>
		<button type="submit">Search</button>
		{#if query}
			<a class="clear" href="/characters">Clear</a>
		{/if}
	</form>

	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}

	{#if loading}
		<p class="muted">Loading characters…</p>
	{:else if characters.length === 0}
		<p class="muted">
			{query ? 'No characters match that search.' : 'No characters yet — import a card to start.'}
		</p>
	{:else}
		<ul class="grid">
			{#each characters as character (character.id)}
				<li class="card">
					<a class="entry" href={`/characters/${character.id}`}>
						<Avatar
							characterId={character.id}
							name={character.name}
							hasAvatar={character.has_avatar}
							size={52}
						/>
						<span class="info">
							<strong>{character.name}</strong>
							{#if character.creator}
								<span class="muted">{character.creator}</span>
							{/if}
							{#if character.tags.length > 0}
								<span class="tags">{character.tags.slice(0, 4).join(' · ')}</span>
							{/if}
						</span>
					</a>
					<button class="danger" onclick={() => remove(character)}>Delete</button>
				</li>
			{/each}
		</ul>
	{/if}
</main>

<style>
	.header {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		align-items: flex-end;
		justify-content: space-between;
	}

	.header h1 {
		margin: 0;
	}

	.upload {
		display: grid;
		gap: 0.25rem;
		font-size: 0.8rem;
		color: var(--muted);
	}

	.upload input {
		max-width: 18rem;
	}

	.search {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		margin: 1.25rem 0;
	}

	.search input {
		max-width: 22rem;
	}

	.clear {
		font-size: 0.85rem;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
		gap: 0.75rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.6rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.entry {
		display: flex;
		gap: 0.6rem;
		align-items: center;
		min-width: 0;
		text-decoration: none;
		color: inherit;
	}

	.info {
		display: grid;
		gap: 0.1rem;
		min-width: 0;
	}

	.info strong {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.tags {
		font-size: 0.78rem;
		color: var(--muted);
	}
</style>
