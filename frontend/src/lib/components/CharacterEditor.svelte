<script lang="ts">
	import { untrack } from 'svelte';

	import { createCharacter, updateCharacter, type CharacterDetail } from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import {
		cardFromDraft,
		draftFromCard,
		draftProblems,
		emptyBook,
		emptyDraft,
		readJsonObject,
		type Draft,
		type JsonObject
	} from '$lib/cardDraft';
	import { errorMessage } from '$lib/errors';
	import CharacterBookEditor from './CharacterBookEditor.svelte';
	import StringListEditor from './StringListEditor.svelte';

	type Tab = 'identity' | 'prompting' | 'lorebook' | 'extensions' | 'raw';

	type Props = {
		/** Existing card when editing; omit or pass null to create a new one. */
		card?: JsonObject | null;
		/** Character id when editing; null/omitted means create. */
		characterId?: number | null;
		onSaved: (detail: CharacterDetail) => void;
		onCancel: () => void;
	};

	let { card = null, characterId = null, onSaved, onCancel }: Props = $props();

	const TABS: { id: Tab; label: string }[] = [
		{ id: 'identity', label: 'Identity' },
		{ id: 'prompting', label: 'Prompting' },
		{ id: 'lorebook', label: 'Lorebook' },
		{ id: 'extensions', label: 'Extensions' },
		{ id: 'raw', label: 'Raw JSON' }
	];

	// The draft is mutable state; `cardFromDraft` overlays our edits back onto the
	// original JSON so unknown keys survive the round trip. The card is an
	// intentional one-time snapshot of the prop.
	let draft = $state<Draft>(untrack(() => (card ? draftFromCard(card) : emptyDraft())));
	let tab = $state<Tab>('identity');
	let rawText = $state('');
	let rawError = $state<string | null>(null);
	let busy = $state(false);
	let error = $state<string | null>(null);
	let saved = $state(false);

	const editing = $derived(characterId !== null);
	const problems = $derived(draftProblems(draft));
	const blocking = $derived(tab !== 'raw' && problems.length > 0);

	function selectTab(next: Tab) {
		if (next === tab) return;

		if (next === 'raw') {
			// Serialise the current form so the two views stay coherent.
			rawText = JSON.stringify(cardFromDraft($state.snapshot(draft)), null, 2);
			rawError = null;
		} else if (tab === 'raw') {
			// Rebuild the draft from whatever the user typed.
			const parsed = readJsonObject(rawText);
			if (!parsed.ok) {
				rawError = parsed.error;
				return;
			}
			rawError = null;
			Object.assign(draft, draftFromCard(parsed.value));
		}

		tab = next;
	}

	function removeBook() {
		if (confirm('Remove the character book? Its entries are discarded when you save.')) {
			draft.book = null;
		}
	}

	async function save() {
		const token = auth.token;
		if (!token) {
			error = 'You are signed out.';
			return;
		}

		error = null;
		saved = false;

		let payload: JsonObject;
		if (tab === 'raw') {
			const parsed = readJsonObject(rawText);
			if (!parsed.ok) {
				rawError = parsed.error;
				return;
			}
			rawError = null;
			// In raw mode the parsed object is sent as-is.
			payload = parsed.value;
		} else {
			if (problems.length > 0) return;
			payload = cardFromDraft($state.snapshot(draft));
		}

		busy = true;
		try {
			const detail =
				characterId === null
					? await createCharacter(token, payload)
					: await updateCharacter(token, characterId, { card: payload });
			saved = true;
			onSaved(detail);
		} catch (cause) {
			error = errorMessage(cause);
		} finally {
			busy = false;
		}
	}
</script>

<div class="editor">
	<div class="tabs" role="tablist">
		{#each TABS as item (item.id)}
			<button
				type="button"
				role="tab"
				class:active={tab === item.id}
				aria-selected={tab === item.id}
				onclick={() => selectTab(item.id)}
			>
				{item.label}
			</button>
		{/each}
	</div>

	<form class="form" onsubmit={(event) => { event.preventDefault(); void save(); }}>
		{#if tab === 'identity'}
			<div class="fields">
				<label>
					<span>Name</span>
					<input bind:value={draft.name} maxlength="200" />
				</label>
				<label>
					<span>Description</span>
					<textarea bind:value={draft.description} rows="5"></textarea>
				</label>
				<label>
					<span>Personality</span>
					<textarea bind:value={draft.personality} rows="3"></textarea>
				</label>
				<label>
					<span>Scenario</span>
					<textarea bind:value={draft.scenario} rows="3"></textarea>
				</label>
				<label>
					<span>First message</span>
					<textarea bind:value={draft.firstMes} rows="4"></textarea>
				</label>
				<label>
					<span>Example messages</span>
					<textarea bind:value={draft.mesExample} rows="4"></textarea>
				</label>

				<fieldset>
					<legend>Alternate greetings</legend>
					<StringListEditor
						label="alternate greeting"
						placeholder="Another opening line…"
						items={draft.alternateGreetings}
					/>
				</fieldset>

				<fieldset>
					<legend>Tags</legend>
					<StringListEditor label="tag" placeholder="e.g. fantasy" items={draft.tags} />
				</fieldset>
			</div>
		{:else if tab === 'prompting'}
			<div class="fields">
				<label>
					<span>Creator</span>
					<input bind:value={draft.creator} maxlength="200" />
				</label>
				<label>
					<span>Character version</span>
					<input bind:value={draft.characterVersion} maxlength="100" />
				</label>
				<label>
					<span>Creator notes</span>
					<textarea bind:value={draft.creatorNotes} rows="3"></textarea>
				</label>

				<label>
					<span>System prompt</span>
					<textarea bind:value={draft.systemPrompt} rows="5"></textarea>
				</label>
				<p class="hint">
					Replaces your global system prompt for this character. Use <code>{'{{original}}'}</code> to
					insert the prompt that would otherwise have been used.
				</p>

				<label>
					<span>Post-history instructions (UJB)</span>
					<textarea bind:value={draft.postHistoryInstructions} rows="5"></textarea>
				</label>
				<p class="hint">
					Replaces your default UJB for this character. Use <code>{'{{original}}'}</code> to insert
					the instructions that would otherwise have been used.
				</p>
			</div>
		{:else if tab === 'lorebook'}
			{#if draft.book === null}
				<p class="muted">This character has no character book.</p>
				<button type="button" class="primary" onclick={() => (draft.book = emptyBook())}>
					Add character book
				</button>
			{:else}
				{@const book = draft.book}
				<button type="button" class="danger" onclick={removeBook}>Remove book</button>
				<CharacterBookEditor {book} />
			{/if}
		{:else if tab === 'extensions'}
			<div class="fields">
				<p class="hint">
					Keys should be namespaced (e.g. <code>myapp/voice</code>) so different tools do not
					collide. Values are JSON.
				</p>

				{#each draft.extensions as row, index (index)}
					<div class="ext-row">
						<input
							bind:value={row.key}
							placeholder="namespace/key"
							aria-label={`Extension key ${index + 1}`}
						/>
						<textarea
							bind:value={row.value}
							rows="3"
							spellcheck="false"
							aria-label={`Extension value ${index + 1}`}
						></textarea>
						<button
							type="button"
							class="ghost"
							onclick={() => draft.extensions.splice(index, 1)}
							aria-label={`Remove extension ${index + 1}`}
						>
							Remove
						</button>
					</div>
				{/each}

				{#if draft.extensions.length === 0}
					<p class="muted">No extensions.</p>
				{/if}

				<button type="button" onclick={() => draft.extensions.push({ key: '', value: '' })}>
					Add extension
				</button>
			</div>
		{:else}
			<div class="fields">
				<label>
					<span>Card JSON</span>
					<textarea
						class="json"
						bind:value={rawText}
						rows="26"
						spellcheck="false"
						oninput={() => (rawError = null)}
					></textarea>
				</label>
				{#if rawError}
					<p class="error" role="alert">{rawError}</p>
				{/if}
			</div>
		{/if}

		{#if error}
			<p class="error" role="alert">{error}</p>
		{/if}

		{#if tab !== 'raw' && problems.length > 0}
			<div class="problems" role="alert">
				<p>Fix these before saving:</p>
				<ul>
					{#each problems as problem, index (index)}
						<li>{problem}</li>
					{/each}
				</ul>
			</div>
		{/if}

		<div class="actions">
			<button class="primary" type="submit" disabled={busy || blocking}>
				{busy ? 'Saving…' : editing ? 'Save changes' : 'Create character'}
			</button>
			<button type="button" onclick={onCancel} disabled={busy}>Cancel</button>
			{#if saved}
				<span class="saved">Saved.</span>
			{/if}
		</div>
	</form>
</div>

<style>
	.editor {
		display: grid;
		gap: 0.9rem;
	}

	.tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--border);
	}

	.tabs button {
		padding: 0.35rem 0.7rem;
		background: transparent;
		border-color: transparent;
	}

	.tabs button.active {
		background: var(--surface-2);
		border-color: var(--border);
		font-weight: 600;
	}

	.form {
		display: grid;
		gap: 1rem;
	}

	.fields {
		display: grid;
		gap: 0.75rem;
	}

	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.85rem;
	}

	fieldset {
		display: grid;
		gap: 0.4rem;
		margin: 0;
		padding: 0.6rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	legend {
		padding: 0 0.3rem;
		font-size: 0.8rem;
		color: var(--muted);
	}

	.hint {
		margin: 0;
		font-size: 0.8rem;
		color: var(--muted);
	}

	code {
		padding: 0.05rem 0.3rem;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: 4px;
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.9em;
	}

	.json {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.85rem;
	}

	.ext-row {
		display: grid;
		gap: 0.4rem;
		padding: 0.6rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.ext-row > button {
		justify-self: start;
	}

	.problems {
		padding: 0.6rem 0.75rem;
		background: var(--surface);
		border: 1px solid var(--danger);
		border-radius: var(--radius);
		font-size: 0.85rem;
	}

	.problems p {
		margin: 0 0 0.3rem;
	}

	.problems ul {
		margin: 0;
		padding-left: 1.1rem;
	}

	.actions {
		display: flex;
		gap: 0.6rem;
		align-items: center;
		padding-top: 0.6rem;
		border-top: 1px solid var(--border);
	}

	.saved {
		font-size: 0.85rem;
		color: var(--muted);
	}
</style>
