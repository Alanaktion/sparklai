<script lang="ts">
	import { onMount } from 'svelte';

	import {
		listProviders,
		streamCreatorMessage,
		type CreatorTurn,
		type Provider
	} from '#lib/api.js';
	import { auth } from '#lib/auth.svelte.js';
	import { draftFromCard, type JsonObject } from '#lib/cardDraft.js';
	import { errorMessage } from '#lib/errors.js';

	type Props = {
		/** The user picked up the assistant's draft; hand it to the full editor. */
		onUseDraft: (card: JsonObject) => void;
		onCancel: () => void;
	};

	let { onUseDraft, onCancel }: Props = $props();

	// Must match `DRAFT_MARKER` in `services/character_creator.py`: the assistant's
	// reply is split on this marker so the JSON patch after it never renders.
	const DRAFT_MARKER = '%%%SPARKLCHAT_DRAFT%%%';

	// `content` (sent back to the backend as context) keeps the assistant's raw
	// reply, marker and patch included: seeing its own past replies still carry
	// the patch is what keeps the model reliably repeating the pattern on later
	// turns. `display` is the cleaned text the user actually reads.
	type Turn = CreatorTurn & { display: string };

	let providers = $state<Provider[]>([]);
	let providerId = $state<number | null>(null);
	let turns = $state<Turn[]>([]);
	let draft = $state<JsonObject>({});
	let input = $state('');
	let streaming = $state(false);
	let streamText = $state('');
	let error = $state<string | null>(null);
	let log: HTMLDivElement | null = null;
	let controller: AbortController | null = null;

	const preview = $derived(draftFromCard(draft));
	const hasDraft = $derived(Boolean(preview.name.trim() || preview.description.trim()));
	// The marker (and everything after it) is stripped from the live view, so the
	// raw patch JSON is never shown while it is still streaming in.
	const liveText = $derived(streamText.split(DRAFT_MARKER)[0]);

	onMount(() => {
		const token = auth.token;
		if (!token) return;
		listProviders(token)
			.then((rows) => {
				providers = rows;
				providerId = rows.find((row) => row.is_default)?.id ?? rows[0]?.id ?? null;
			})
			.catch(() => {
				providers = [];
			});
		return () => controller?.abort();
	});

	async function scrollToBottom() {
		await Promise.resolve();
		if (log) log.scrollTop = log.scrollHeight;
	}

	function isAbort(cause: unknown): boolean {
		return cause instanceof Error && cause.name === 'AbortError';
	}

	async function send() {
		const content = input.trim();
		const token = auth.token;
		if (!content || streaming || !token) return;

		input = '';
		error = null;
		streamText = '';
		streaming = true;
		controller = new AbortController();
		const nextTurns: Turn[] = [...turns, { role: 'user', content, display: content }];
		turns = nextTurns;
		void scrollToBottom();

		try {
			await streamCreatorMessage(
				token,
				{
					provider_id: providerId,
					draft,
					messages: nextTurns.map(({ role, content: text }) => ({ role, content: text }))
				},
				{
					onDelta: (delta) => {
						streamText += delta;
						void scrollToBottom();
					},
					onMessage: (reply) => {
						// `streamText` still holds the full raw reply (marker and patch
						// included) at this point; that is what goes back as context.
						turns = [...turns, { role: 'assistant', content: streamText, display: reply }];
						streamText = '';
						void scrollToBottom();
					},
					onDraft: (next) => {
						draft = next;
					},
					onError: (detail) => {
						error = detail;
					}
				},
				controller.signal
			);
		} catch (cause) {
			if (!isAbort(cause)) error = errorMessage(cause);
		} finally {
			streaming = false;
			controller = null;
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			void send();
		}
	}
</script>

<div class="assistant">
	<div class="chat">
		<label class="provider">
			<span>Provider</span>
			<select bind:value={providerId} disabled={providers.length === 0}>
				{#each providers as provider (provider.id)}
					<option value={provider.id}>{provider.name}</option>
				{/each}
			</select>
			{#if providers.length === 0}
				<span class="hint">Add a provider under Settings first.</span>
			{/if}
		</label>

		<div class="log" bind:this={log}>
			{#if turns.length === 0}
				<p class="muted intro">
					Describe a concept &mdash; a role, a vibe, a couple of traits &mdash; and the
					assistant will draft a full character and refine it with you from there.
				</p>
			{/if}
			{#each turns as turn, index (index)}
				<div class="turn {turn.role}">
					<span class="who">{turn.role === 'user' ? 'You' : 'Assistant'}</span>
					<p>{turn.display}</p>
				</div>
			{/each}
			{#if streaming}
				<div class="turn assistant">
					<span class="who">Assistant</span>
					<p>{liveText}<span class="cursor">▍</span></p>
				</div>
			{/if}
		</div>

		{#if error}
			<p class="error" role="alert">{error}</p>
		{/if}

		<form class="composer" onsubmit={(event) => { event.preventDefault(); void send(); }}>
			<textarea
				bind:value={input}
				onkeydown={handleKeydown}
				rows="2"
				placeholder="e.g. a grumpy retired dragon-slayer who now runs a bakery"
				disabled={streaming || providers.length === 0}
			></textarea>
			<button class="primary" type="submit" disabled={streaming || !input.trim()}>
				{streaming ? 'Thinking…' : 'Send'}
			</button>
		</form>
	</div>

	<div class="sheet">
		<h2>Draft</h2>
		{#if !hasDraft}
			<p class="muted">Nothing yet &mdash; start the conversation to see a draft appear here.</p>
		{:else}
			<dl>
				<dt>Name</dt>
				<dd>{preview.name || '—'}</dd>
				{#if preview.tags.length > 0}
					<dt>Tags</dt>
					<dd class="tags">
						{#each preview.tags as tag (tag)}<span class="tag">{tag}</span>{/each}
					</dd>
				{/if}
				<dt>Description</dt>
				<dd>{preview.description || '—'}</dd>
				<dt>Personality</dt>
				<dd>{preview.personality || '—'}</dd>
				<dt>Scenario</dt>
				<dd>{preview.scenario || '—'}</dd>
				<dt>First message</dt>
				<dd>{preview.firstMes || '—'}</dd>
				{#if preview.book && preview.book.entries.length > 0}
					<dt>Lorebook</dt>
					<dd>{preview.book.entries.length} entr{preview.book.entries.length === 1 ? 'y' : 'ies'}</dd>
				{/if}
			</dl>
		{/if}

		<div class="actions">
			<button class="primary" type="button" disabled={!hasDraft} onclick={() => onUseDraft(draft)}>
				Use this draft
			</button>
			<button type="button" onclick={onCancel}>Cancel</button>
		</div>
	</div>
</div>

<style>
	.assistant {
		display: grid;
		gap: 1rem;
		grid-template-columns: minmax(0, 1fr) minmax(0, 30rem);
		align-items: start;
	}

	@media (max-width: 60rem) {
		.assistant {
			grid-template-columns: 1fr;
		}
	}

	.chat {
		display: grid;
		gap: 0.6rem;
	}

	.provider {
		display: grid;
		gap: 0.25rem;
		font-size: 0.85rem;
		max-width: 16rem;
	}

	.log {
		display: grid;
		gap: 0.6rem;
		align-content: start;
		height: 24rem;
		overflow-y: auto;
		padding: 0.75rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.intro {
		margin: 0;
	}

	.turn {
		display: grid;
		gap: 0.15rem;
		padding: 0.5rem 0.65rem;
		border-radius: var(--radius);
		background: var(--surface-2);
		justify-self: start;
		max-width: 90%;
	}

	.turn.user {
		justify-self: end;
		background: color-mix(in srgb, var(--accent) 18%, var(--surface-2));
	}

	.turn .who {
		font-size: 0.72rem;
		color: var(--muted);
	}

	.turn p {
		margin: 0;
		white-space: pre-wrap;
	}

	.cursor {
		opacity: 0.6;
	}

	.composer {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 0.5rem;
		align-items: end;
	}

	.composer textarea {
		resize: vertical;
		field-sizing: content;
	}

	.composer button {
		min-width: 6rem;
	}

	.sheet {
		display: grid;
		gap: 0.6rem;
		align-content: start;
		padding: 0.9rem 1rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.sheet h2 {
		margin: 0;
		font-size: 1rem;
	}

	dl {
		display: grid;
		gap: 0.2rem;
		margin: 0;
	}

	dt {
		margin-top: 0.5rem;
		font-size: 0.72rem;
		color: var(--muted);
	}

	dd {
		margin: 0;
		white-space: pre-wrap;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}

	.tag {
		padding: 0.1rem 0.5rem;
		font-size: 0.75rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 999px;
	}

	.actions {
		display: flex;
		gap: 0.5rem;
		padding-top: 0.4rem;
		border-top: 1px solid var(--border);
	}
</style>
