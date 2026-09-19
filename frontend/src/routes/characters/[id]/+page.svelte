<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	import {
		createSession,
		deleteSession,
		downloadCharacterCard,
		getCharacter,
		listCharacters,
		listSessions,
		updateCharacter,
		type CharacterDetail,
		type CharacterExportFormat,
		type CharacterSummary,
		type SessionSummary
	} from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import { errorMessage } from '$lib/errors';
	import { formatDate } from '$lib/format';

	let character = $state<CharacterDetail | null>(null);
	let sessions = $state<SessionSummary[]>([]);
	let loading = $state(true);
	let starting = $state(false);
	let exporting = $state<CharacterExportFormat | null>(null);
	let togglingVisibility = $state(false);
	let error = $state<string | null>(null);

	let others = $state<CharacterSummary[]>([]);
	let groupSelection = $state<number[]>([]);
	let startingGroup = $state(false);

	const characterId = $derived(Number(page.params.id));

	$effect(() => {
		void load(characterId);
	});

	async function load(id: number) {
		const token = auth.token;
		if (!token) return;
		if (!Number.isFinite(id)) {
			error = 'Invalid character id';
			loading = false;
			return;
		}

		loading = true;
		error = null;
		try {
			character = await getCharacter(token, id);
		} catch (cause) {
			error = errorMessage(cause);
			loading = false;
			return;
		}

		try {
			sessions = await listSessions(token, id);
		} catch {
			sessions = [];
		}
		void loadOthers(id);
		loading = false;
	}

	async function startChat() {
		const token = auth.token;
		if (!token || !character) return;
		starting = true;
		error = null;
		try {
			const created = await createSession(token, character.id);
			await goto(`/chat/${created.id}`);
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			starting = false;
		}
	}

	async function removeSession(session: SessionSummary) {
		if (!confirm(`Delete session “${session.title}”?`)) return;
		const token = auth.token;
		if (!token) return;
		error = null;
		try {
			await deleteSession(token, session.id);
			sessions = sessions.filter((item) => item.id !== session.id);
		} catch (cause) {
			error = errorMessage(cause);
		}
	}

	async function toggleVisibility() {
		const token = auth.token;
		if (!token || !character) return;
		togglingVisibility = true;
		error = null;
		try {
			character = await updateCharacter(token, character.id, {
				is_public: !character.is_public
			});
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			togglingVisibility = false;
		}
	}

	async function loadOthers(id: number) {
		const token = auth.token;
		if (!token) return;
		try {
			const [mine, shared] = await Promise.all([
				listCharacters(token, { limit: 200 }),
				listCharacters(token, { limit: 200, scope: 'public' })
			]);
			const seen = new Set<number>();
			const merged: CharacterSummary[] = [];
			for (const item of [...mine, ...shared]) {
				if (item.id === id || seen.has(item.id)) continue;
				seen.add(item.id);
				merged.push(item);
			}
			others = merged.sort((a, b) => a.name.localeCompare(b.name));
		} catch {
			others = [];
		}
	}

	async function startGroup() {
		const token = auth.token;
		if (!token || !character || groupSelection.length === 0) return;
		startingGroup = true;
		error = null;
		try {
			const created = await createSession(token, character.id, {
				character_ids: groupSelection
			});
			await goto(`/chat/${created.id}`);
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			startingGroup = false;
		}
	}

	async function exportCard(format: CharacterExportFormat) {
		const token = auth.token;
		if (!token || !character) return;
		exporting = format;
		error = null;
		try {
			await downloadCharacterCard(token, character.id, format);
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			exporting = null;
		}
	}
</script>

<svelte:head>
	<title>{character ? `${character.name} · Sparkl Chat` : 'Character · Sparkl Chat'}</title>
</svelte:head>

<main class="page">
	{#if loading}
		<p class="muted">Loading character…</p>
	{:else if !character}
		<p class="error" role="alert">{error ?? 'Character not found.'}</p>
		<p><a href="/characters">Back to characters</a></p>
	{:else}
		{#if error}
			<p class="error" role="alert">{error}</p>
		{/if}

		<header class="profile">
			<Avatar characterId={character.id} name={character.name} hasAvatar={character.has_avatar} size={96} />
			<div class="meta">
				<h1>{character.name}</h1>
				<p class="muted byline">
					{#if character.creator}by {character.creator}{:else}Unknown creator{/if}
					{#if character.character_version}· v{character.character_version}{/if}
					· {character.spec_version}
					{#if character.is_public}· <span class="badge">Public</span>{/if}
				</p>
				{#if character.tags.length > 0}
					<ul class="tags">
						{#each character.tags as tag (tag)}
							<li>{tag}</li>
						{/each}
					</ul>
				{/if}
				<div class="actions">
					<button class="primary" onclick={startChat} disabled={starting}>
						{starting ? 'Starting…' : 'Start new chat'}
					</button>
					{#if character.is_mine}
						<a class="edit" href={`/characters/${character.id}/edit`}>Edit</a>
						<button onclick={toggleVisibility} disabled={togglingVisibility}>
							{togglingVisibility
								? 'Saving…'
								: character.is_public
									? 'Make private'
									: 'Publish'}
						</button>
					{/if}
				</div>

				{#if others.length > 0}
					<details class="group">
						<summary>New group chat</summary>
						<p class="muted">
							Pick the other characters in the scene. {character.name} stays the primary
							character.
						</p>
						<ul class="members">
							{#each others as other (other.id)}
								<li>
									<label>
										<input
											type="checkbox"
											checked={groupSelection.includes(other.id)}
											onchange={(event) => {
												const checked = (event.currentTarget as HTMLInputElement).checked;
												groupSelection = checked
													? [...groupSelection, other.id]
													: groupSelection.filter((value) => value !== other.id);
											}}
										/>
										<span>{other.name}</span>
										{#if !other.is_mine}<span class="muted">public</span>{/if}
									</label>
								</li>
							{/each}
						</ul>
						<button
							class="primary"
							onclick={startGroup}
							disabled={startingGroup || groupSelection.length === 0}
						>
							{startingGroup ? 'Starting…' : 'Start group chat'}
						</button>
					</details>
				{/if}
				<div class="export">
					<span class="muted">Export</span>
					<button onclick={() => exportCard('v2')} disabled={exporting !== null}>
						{exporting === 'v2' ? 'V2…' : 'V2 JSON'}
					</button>
					<button onclick={() => exportCard('v1')} disabled={exporting !== null}>
						{exporting === 'v1' ? 'V1…' : 'V1 JSON'}
					</button>
					<button onclick={() => exportCard('png')} disabled={exporting !== null}>
						{exporting === 'png' ? 'PNG…' : 'PNG'}
					</button>
				</div>
			</div>
		</header>

		<section class="panel">
			<h2>About</h2>
			{#if character.card.data?.creator_notes}
				<p class="notes">{character.card.data.creator_notes}</p>
			{:else}
				<p class="muted">No creator notes.</p>
			{/if}
		</section>

		{#if character.card.data?.description}
			<section class="panel">
				<h2>Description</h2>
				<p class="notes">{character.card.data.description}</p>
			</section>
		{/if}

		<section class="panel">
			<h2>Sessions</h2>
			{#if sessions.length === 0}
				<p class="muted">No chats yet. Start one above.</p>
			{:else}
				<ul class="sessions">
					{#each sessions as session (session.id)}
						<li>
							<a class="session" href={`/chat/${session.id}`}>
								<strong>{session.title}</strong>
								<span class="muted">{formatDate(session.updated_at)}</span>
							</a>
							<button class="danger" onclick={() => removeSession(session)}>Delete</button>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}
</main>

<style>
	.profile {
		display: flex;
		gap: 1.25rem;
		align-items: flex-start;
	}

	.meta {
		display: grid;
		gap: 0.5rem;
		justify-items: start;
	}

	.meta h1 {
		margin: 0;
	}

	.byline {
		margin: 0;
		font-size: 0.9rem;
	}

	.badge {
		padding: 0.1rem 0.45rem;
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 999px;
	}

	.actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		flex-wrap: wrap;
	}

	.group {
		max-width: 34rem;
		padding: 0.75rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.group summary {
		cursor: pointer;
	}

	.group p {
		margin: 0.5rem 0;
		font-size: 0.85rem;
	}

	.members {
		display: grid;
		gap: 0.3rem;
		margin: 0 0 0.75rem;
		padding: 0;
		list-style: none;
	}

	.members label {
		display: flex;
		gap: 0.4rem;
		align-items: center;
		font-size: 0.9rem;
	}

	.members .muted {
		font-size: 0.75rem;
	}

	.export {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
	}

	.export span {
		font-size: 0.8rem;
	}

	.export button {
		padding: 0.3rem 0.6rem;
		font-size: 0.85rem;
	}

	.edit {
		padding: 0.45rem 0.8rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: inherit;
		text-decoration: none;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.tags li {
		padding: 0.15rem 0.5rem;
		font-size: 0.78rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 999px;
	}

	.panel {
		margin-top: 1.75rem;
		padding: 0.9rem 1rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.panel h2 {
		margin: 0 0 0.5rem;
		font-size: 0.95rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
	}

	.notes {
		margin: 0;
		white-space: pre-wrap;
	}

	.sessions {
		display: grid;
		gap: 0.5rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.sessions li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.session {
		display: flex;
		gap: 0.6rem;
		align-items: baseline;
		text-decoration: none;
		color: inherit;
	}
</style>
