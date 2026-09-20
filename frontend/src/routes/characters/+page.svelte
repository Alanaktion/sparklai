<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	import {
		deleteCharacter,
		listCharacters,
		uploadCharacters,
		type CharacterSort,
		type CharacterSummary
	} from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import { errorMessage } from '$lib/errors';

	let characters = $state<CharacterSummary[]>([]);
	let loading = $state(true);
	let uploading = $state(false);
	let error = $state<string | null>(null);
	let notice = $state<string | null>(null);
	let importErrors = $state<string[]>([]);
	let search = $state('');
	let tagInput = $state('');
	let creatorInput = $state('');
	let versionInput = $state('');
	let sortInput = $state<CharacterSort>('name');

	const SORTS: { value: CharacterSort; label: string }[] = [
		{ value: 'name', label: 'Name' },
		{ value: 'created', label: 'Newest' },
		{ value: 'updated', label: 'Recently updated' },
		{ value: 'character_version', label: 'Character version' }
	];

	type Scope = 'mine' | 'public';
	type Filters = {
		q: string;
		tag: string;
		creator: string;
		version: string;
		scope: Scope;
		sort: CharacterSort;
	};

	function parseScope(value: string | null): Scope {
		return value === 'public' ? 'public' : 'mine';
	}

	function parseSort(value: string | null): CharacterSort {
		return SORTS.some((option) => option.value === value)
			? (value as CharacterSort)
			: 'name';
	}

	const query = $derived(page.url.searchParams.get('q') ?? '');
	const tagQuery = $derived(page.url.searchParams.get('tag') ?? '');
	const creatorQuery = $derived(page.url.searchParams.get('creator') ?? '');
	const versionQuery = $derived(page.url.searchParams.get('version') ?? '');
	const scopeQuery = $derived(parseScope(page.url.searchParams.get('scope')));
	const sortQuery = $derived(parseSort(page.url.searchParams.get('sort')));
	const hasFilters = $derived(Boolean(query || tagQuery || creatorQuery || versionQuery));
	let requestId = 0;

	$effect(() => {
		search = query;
		tagInput = tagQuery;
		creatorInput = creatorQuery;
		versionInput = versionQuery;
		sortInput = sortQuery;
		void load({
			q: query,
			tag: tagQuery,
			creator: creatorQuery,
			version: versionQuery,
			scope: scopeQuery,
			sort: sortQuery
		});
	});

	function scopeHref(scope: Scope): string {
		const params = new URLSearchParams(page.url.searchParams);
		if (scope === 'public') params.set('scope', 'public');
		else params.delete('scope');
		const qs = params.toString();
		return qs ? `/characters?${qs}` : '/characters';
	}

	function parseTags(value: string): string[] {
		return value
			.split(',')
			.map((tag) => tag.trim())
			.filter(Boolean);
	}

	async function load(filters: Filters) {
		const token = auth.token;
		if (!token) return;
		const id = ++requestId;
		loading = true;
		error = null;
		const tags = parseTags(filters.tag);
		try {
			const result = await listCharacters(token, {
				q: filters.q || undefined,
				tags: tags.length ? tags : undefined,
				creator: filters.creator || undefined,
				characterVersion: filters.version || undefined,
				scope: filters.scope,
				sort: filters.sort
			});
			if (id === requestId) characters = result;
		} catch (cause) {
			if (id === requestId) error = errorMessage(cause);
		} finally {
			if (id === requestId) loading = false;
		}
	}

	function currentFilters(): Filters {
		return {
			q: query,
			tag: tagQuery,
			creator: creatorQuery,
			version: versionQuery,
			scope: scopeQuery,
			sort: sortQuery
		};
	}

	function applyFilters(event: SubmitEvent) {
		event.preventDefault();
		const params = new URLSearchParams();
		const q = search.trim();
		if (q) params.set('q', q);
		const tag = tagInput.trim();
		if (tag) params.set('tag', tag);
		const creator = creatorInput.trim();
		if (creator) params.set('creator', creator);
		const version = versionInput.trim();
		if (version) params.set('version', version);
		if (scopeQuery === 'public') params.set('scope', 'public');
		if (sortInput !== 'name') params.set('sort', sortInput);
		const qs = params.toString();
		void goto(qs ? `/characters?${qs}` : '/characters');
	}

	function changeSort(event: Event) {
		const value = (event.currentTarget as HTMLSelectElement).value as CharacterSort;
		sortInput = value;
		const params = new URLSearchParams(page.url.searchParams);
		if (value === 'name') params.delete('sort');
		else params.set('sort', value);
		const qs = params.toString();
		void goto(qs ? `/characters?${qs}` : '/characters');
	}

	async function onFileChange(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const files = Array.from(input.files ?? []);
		input.value = '';
		if (files.length === 0) return;

		const token = auth.token;
		if (!token) return;

		uploading = true;
		error = null;
		notice = null;
		importErrors = [];
		try {
			const results = await uploadCharacters(token, files);
			const failed = results.filter((result) => result.error !== null);
			const imported = results.length - failed.length;
			importErrors = failed.map((result) => `${result.filename}: ${result.error}`);
			if (imported > 0) {
				notice = `Imported ${imported} character${imported === 1 ? '' : 's'}.`;
				await load(currentFilters());
			}
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
		<div class="header-actions">
			<a class="new" href="/characters/new">New character</a>
			<label class="upload" title="PNG cards, JSON, or CHARX — pick several at once">
				<span>{uploading ? 'Importing…' : 'Import cards'}</span>
				<input
					type="file"
					accept=".png,.json,.charx,image/png,application/json"
					multiple
					onchange={onFileChange}
					disabled={uploading}
				/>
			</label>
		</div>
	</div>

	{#if notice}
		<p class="notice" role="status">{notice}</p>
	{/if}

	{#if importErrors.length > 0}
		<div class="error import-errors" role="alert">
			<p>Some files could not be imported:</p>
			<ul>
				{#each importErrors as message, index (index)}
					<li>{message}</li>
				{/each}
			</ul>
		</div>
	{/if}

	<nav class="scopes" aria-label="Character library">
		<a class:active={scopeQuery === 'mine'} href={scopeHref('mine')}>Mine</a>
		<a class:active={scopeQuery === 'public'} href={scopeHref('public')}>Public library</a>
	</nav>

	<form class="filters" onsubmit={applyFilters}>
		<label class="field">
			<span>Name</span>
			<input
				type="search"
				bind:value={search}
				placeholder="Search by name…"
				aria-label="Search characters by name"
			/>
		</label>
		<label class="field">
			<span>Tags</span>
			<input
				bind:value={tagInput}
				placeholder="fantasy, romance"
				aria-label="Filter by tags, comma separated"
			/>
		</label>
		<label class="field">
			<span>Creator</span>
			<input bind:value={creatorInput} placeholder="Creator name" aria-label="Filter by creator" />
		</label>
		<label class="field">
			<span>Character version</span>
			<input
				bind:value={versionInput}
				placeholder="e.g. 1.2"
				aria-label="Filter by character version"
			/>
		</label>
		<div class="filter-actions">
			<label class="field sort">
				<span>Sort</span>
				<select value={sortInput} onchange={changeSort} aria-label="Sort characters">
					{#each SORTS as option (option.value)}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</label>
			<button type="submit">Apply</button>
			{#if hasFilters}
				<a class="clear" href="/characters">Clear</a>
			{/if}
		</div>
	</form>

	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}

	{#if loading}
		<p class="muted">Loading characters…</p>
	{:else if characters.length === 0}
		<p class="muted">
			{#if hasFilters}
				No characters match those filters.
			{:else if scopeQuery === 'public'}
				No public characters yet — publish one of yours to share it.
			{:else}
				No characters yet — import a card to start.
			{/if}
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
						{#if character.is_public}
							<span class="badge">Public</span>
						{/if}
					</a>
					{#if character.is_mine}
						<button class="danger" onclick={() => remove(character)}>Delete</button>
					{/if}
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

	.header-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		align-items: flex-end;
	}

	.new {
		padding: 0.45rem 0.8rem;
		background: var(--accent);
		border: 1px solid var(--accent);
		border-radius: 8px;
		color: var(--accent-contrast);
		text-decoration: none;
	}

	.upload {
		display: grid;
		gap: 0.25rem;
		font-size: 0.8rem;
		color: var(--muted);
	}

	.upload input {
		width: 18rem;
		max-width: 100%;
	}

	.notice {
		margin: 1rem 0 0;
		font-size: 0.9rem;
		color: var(--success);
	}

	.import-errors {
		margin: 1rem 0 0;
		font-size: 0.9rem;
	}

	.import-errors p {
		margin: 0 0 0.3rem;
	}

	.import-errors ul {
		margin: 0;
		padding-left: 1.1rem;
	}

	.scopes {
		display: flex;
		gap: 0.5rem;
		margin: 1rem 0 0;
	}

	.scopes a {
		padding: 0.3rem 0.7rem;
		font-size: 0.85rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 999px;
		color: var(--muted);
		text-decoration: none;
	}

	.scopes a.active {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--accent-contrast);
	}

	.badge {
		padding: 0.1rem 0.45rem;
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 999px;
		color: var(--muted);
	}

	.filters {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
		gap: 0.75rem 1rem;
		align-items: end;
		margin: 1.25rem 0;
	}

	.field {
		display: grid;
		gap: 0.25rem;
		font-size: 0.8rem;
		color: var(--muted);
	}

	.filter-actions {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}

	.filter-actions button {
		min-width: 5.25rem;
	}

	.sort select {
		min-width: 10rem;
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
