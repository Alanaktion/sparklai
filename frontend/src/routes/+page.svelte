<script lang="ts">
	import { goto } from '$app/navigation';

	import {
		createSession,
		listCharacters,
		listRecentSessions,
		type CharacterSummary,
		type SessionListItem
	} from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import { errorMessage } from '$lib/errors';
	import { formatDate } from '$lib/format';

	const RECENT_SESSION_LIMIT = 10;
	const RECENT_CHARACTER_LIMIT = 8;

	let sessions = $state<SessionListItem[]>([]);
	let characters = $state<CharacterSummary[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let startingId = $state<number | null>(null);

	// The most recently active session, if the user has any.
	const latest = $derived(sessions.at(0) ?? null);

	// `/` is public, so the layout guard leaves it alone; send signed-out visitors
	// to the login form instead of flashing an empty dashboard.
	$effect(() => {
		if (!auth.ready) return;
		if (!auth.isAuthenticated) {
			void goto('/login', { replaceState: true });
			return;
		}
		void load();
	});

	async function load() {
		const token = auth.token;
		if (!token) return;
		loading = true;
		error = null;
		try {
			const [recent, newest] = await Promise.all([
				listRecentSessions(token, RECENT_SESSION_LIMIT),
				listCharacters(token, { sort: 'updated', limit: RECENT_CHARACTER_LIMIT })
			]);
			sessions = recent;
			characters = newest;
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			loading = false;
		}
	}

	async function startChat(character: CharacterSummary) {
		const token = auth.token;
		if (!token) return;
		startingId = character.id;
		error = null;
		try {
			const created = await createSession(token, character.id);
			await goto(`/chat/${created.id}`);
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			startingId = null;
		}
	}
</script>

<svelte:head>
	<title>Home · Sparkl Chat</title>
</svelte:head>

<main class="page">
	<header class="hero">
		<div>
			<h1>Welcome back, {auth.user?.email ?? 'there'}</h1>
			{#if latest}
				<p class="muted">
					Last chat: <strong>{latest.title}</strong>
					{#if latest.title !== latest.character_name}
						· {latest.character_name}
					{/if}
				</p>
			{:else}
				<p class="muted">Pick up a chat or start a new one.</p>
			{/if}
		</div>
		<div class="hero-actions">
			{#if latest}
				<a class="new" href={`/chat/${latest.id}`}>Continue last chat</a>
			{/if}
			<a class:new={!latest} href="/characters">Browse characters</a>
			<a href="/characters/new">New character</a>
		</div>
	</header>

	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}

	{#if loading}
		<p class="muted">Loading your dashboard…</p>
	{:else}
		<section class="panel">
			<div class="panel-head">
				<h2>Recent chats</h2>
			</div>
			{#if sessions.length === 0}
				<p class="muted">
					No chats yet — open a character and say hello to start one.
					<a href="/characters">Browse your characters</a>.
				</p>
			{:else}
				<ul class="chats">
					{#each sessions as session (session.id)}
						<li>
							<a class="chat" href={`/chat/${session.id}`}>
								<Avatar
									characterId={session.character_id}
									name={session.character_name}
									hasAvatar={session.character_has_avatar}
									size={44}
								/>
								<span class="chat-body">
									<span class="chat-title">
										<strong>{session.title}</strong>
										{#if session.title !== session.character_name}
											<span class="muted with">{session.character_name}</span>
										{/if}
									</span>
									{#if session.last_message}
										<span class="preview">{session.last_message}</span>
									{:else}
										<span class="preview muted">No messages yet.</span>
									{/if}
								</span>
								<span class="when muted">{formatDate(session.updated_at)}</span>
							</a>
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<section class="panel">
			<div class="panel-head">
				<h2>Recent characters</h2>
				<a class="more" href="/characters">View all</a>
			</div>
			{#if characters.length === 0}
				<p class="muted">
					Nothing here yet.
					<a href="/characters/new">Create a character</a> or import a card from
					<a href="/characters">the library</a>.
				</p>
			{:else}
				<ul class="cards">
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
									{#if character.tags.length > 0}
										<span class="tags">{character.tags.slice(0, 3).join(' · ')}</span>
									{/if}
									{#if character.last_message_at}
										<span class="last">Chatted {formatDate(character.last_message_at)}</span>
									{:else}
										<span class="last">No chats yet</span>
									{/if}
								</span>
							</a>
							<button
								class="chat-start"
								onclick={() => startChat(character)}
								disabled={startingId !== null}
							>
								{startingId === character.id ? 'Starting…' : 'New chat'}
							</button>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}
</main>

<style>
	.hero {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		align-items: flex-end;
		justify-content: space-between;
	}

	.hero h1 {
		margin: 0 0 0.2rem;
	}

	.hero p {
		margin: 0;
	}

	.hero-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}

	.hero-actions a {
		padding: 0.45rem 0.8rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: inherit;
		text-decoration: none;
	}

	.hero-actions a.new {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--accent-contrast);
	}

	.panel {
		margin-top: 1.75rem;
		padding: 0.9rem 1rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.panel-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}

	.panel h2 {
		margin: 0 0 0.5rem;
		font-size: 0.95rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
	}

	.more {
		font-size: 0.85rem;
	}

	.chats {
		display: grid;
		gap: 0.4rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.chat {
		display: flex;
		gap: 0.7rem;
		align-items: center;
		padding: 0.5rem;
		border-radius: 8px;
		text-decoration: none;
		color: inherit;
	}

	.chat:hover {
		background: var(--surface-2);
	}

	.chat-body {
		display: grid;
		gap: 0.1rem;
		flex: 1;
		min-width: 0;
	}

	.chat-title {
		display: flex;
		gap: 0.4rem;
		align-items: baseline;
		min-width: 0;
	}

	.chat-title strong {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.chat-title .with {
		flex-shrink: 0;
		font-size: 0.82rem;
	}

	.preview {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.85rem;
		color: var(--muted);
	}

	.when {
		flex-shrink: 0;
		min-width: 4.5rem;
		font-size: 0.78rem;
		text-align: right;
	}

	.cards {
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
		background: var(--surface-2);
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

	.last {
		font-size: 0.75rem;
		color: var(--muted);
	}

	.chat-start {
		flex-shrink: 0;
		min-width: 6rem;
		padding: 0.3rem 0.6rem;
		font-size: 0.82rem;
	}
</style>
