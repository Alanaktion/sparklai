<script lang="ts">
	import { untrack } from 'svelte';

	import {
		createCharacter,
		deleteCharacterAvatar,
		fetchCharacterAsset,
		updateCharacter,
		uploadCharacterAvatar,
		type CharacterDetail
	} from '#lib/api.js';
	import { auth } from '#lib/auth.svelte.js';
	import { forgetAvatar } from '#lib/avatars.js';
	import Avatar from './Avatar.svelte';
	import {
		cardFromDraft,
		draftFromCard,
		draftProblems,
		emptyBook,
		emptyDraft,
		readJsonObject,
		type Draft,
		type JsonObject
	} from '#lib/cardDraft.js';
	import { errorMessage } from '#lib/errors.js';
	import CharacterBookEditor from './CharacterBookEditor.svelte';
	import StringListEditor from './StringListEditor.svelte';

	type Tab = 'identity' | 'prompting' | 'lorebook' | 'extensions' | 'assets' | 'raw';

	type Props = {
		/** Existing card when editing; omit or pass null to create a new one. */
		card?: JsonObject | null;
		/** Character id when editing; null/omitted means create. */
		characterId?: number | null;
		/** Whether the character being edited already has an avatar. */
		hasAvatar?: boolean;
		onSaved: (detail: CharacterDetail) => void;
		onCancel: () => void;
	};

	let { card = null, characterId = null, hasAvatar = false, onSaved, onCancel }: Props = $props();

	const TABS: { id: Tab; label: string }[] = [
		{ id: 'identity', label: 'Identity' },
		{ id: 'prompting', label: 'Prompting' },
		{ id: 'lorebook', label: 'Lorebook' },
		{ id: 'extensions', label: 'Extensions' },
		{ id: 'assets', label: 'Assets' },
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

	// Assets stored on the server are only reachable through the authenticated
	// asset endpoint, so an `embeded://` asset is fetched into an object URL to
	// preview it. Anything else (or any failure) simply shows no preview.
	const ASSET_URI_PREFIX = 'embeded://';

	function embeddedPath(uri: string): string | null {
		const trimmed = uri.trim();
		return trimmed.startsWith(ASSET_URI_PREFIX) ? trimmed.slice(ASSET_URI_PREFIX.length) : null;
	}

	const embeddedAssets = $derived(
		draft.assets
			.map((asset) => embeddedPath(asset.uri))
			.filter((path): path is string => path !== null)
	);

	let previews = $state<Record<string, string>>({});
	const pending = new Set<string>();
	const failed = new Set<string>();

	function previewFor(uri: string): string | null {
		const path = embeddedPath(uri);
		return path === null ? null : (previews[path] ?? null);
	}

	$effect(() => {
		const id = characterId;
		const token = auth.token;
		const paths = embeddedAssets;
		if (id === null || !token) return;

		// Untracked so a loaded preview cannot retrigger this effect.
		untrack(() => {
			const wanted = new Set(paths);
			for (const path of Object.keys(previews)) {
				if (wanted.has(path)) continue;
				URL.revokeObjectURL(previews[path]);
				delete previews[path];
			}

			for (const path of wanted) {
				if (path in previews || failed.has(path) || pending.has(path)) continue;
				pending.add(path);
				fetchCharacterAsset(token, id, path)
					.then((blob) => {
						previews[path] = URL.createObjectURL(blob);
					})
					.catch(() => {
						failed.add(path);
					})
					.finally(() => pending.delete(path));
			}
		});
	});

	$effect(() => {
		return () => {
			for (const url of Object.values(previews)) URL.revokeObjectURL(url);
		};
	});

	// --- Images -------------------------------------------------------------
	// Image changes are staged and applied when the card is saved, so creating
	// and editing behave the same way.
	const MAX_IMAGE_BYTES = 3 * 1024 * 1024;
	const MAX_AVATAR_BYTES = 10 * 1024 * 1024;
	const ASSET_TYPES: { value: string; label: string }[] = [
		{ value: 'icon', label: 'Icon' },
		{ value: 'user_icon', label: 'Persona image' },
		{ value: 'background', label: 'Background' },
		{ value: 'emotion', label: 'Emotion' }
	];

	let createdId = $state<number | null>(null);
	let avatarFile = $state<File | null>(null);
	let avatarPreview = $state<string | null>(null);
	let avatarRemoved = $state(false);
	let imageError = $state<string | null>(null);
	const showsStoredAvatar = $derived(hasAvatar && !avatarRemoved && !avatarFile);
	const hasShownAvatar = $derived(showsStoredAvatar || avatarFile !== null);

	function stageAvatar(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file) return;
		if (!file.type.startsWith('image/')) {
			imageError = `${file.name} is not an image.`;
			return;
		}
		if (file.size > MAX_AVATAR_BYTES) {
			imageError = `${file.name} is larger than 10 MB.`;
			return;
		}
		imageError = null;
		if (avatarPreview) URL.revokeObjectURL(avatarPreview);
		avatarPreview = URL.createObjectURL(file);
		avatarFile = file;
		avatarRemoved = false;
	}

	function clearAvatar() {
		if (avatarPreview) URL.revokeObjectURL(avatarPreview);
		avatarPreview = null;
		avatarFile = null;
		avatarRemoved = hasAvatar;
	}

	$effect(() => {
		return () => {
			if (avatarPreview) URL.revokeObjectURL(avatarPreview);
		};
	});

	function readAsDataUrl(file: File): Promise<string> {
		return new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onload = () => resolve(String(reader.result));
			reader.onerror = () => reject(reader.error);
			reader.readAsDataURL(file);
		});
	}

	function extensionOf(file: File): string {
		const fromName = file.name.split('.').pop()?.toLowerCase() ?? '';
		if (/^[a-z0-9]+$/.test(fromName) && fromName !== file.name.toLowerCase()) return fromName;
		return file.type.split('/')[1]?.replace(/[^a-z0-9]/g, '') || 'png';
	}

	async function addImages(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const files = [...(input.files ?? [])];
		input.value = '';
		imageError = null;
		for (const file of files) {
			if (!file.type.startsWith('image/')) {
				imageError = `${file.name} is not an image.`;
				continue;
			}
			if (file.size > MAX_IMAGE_BYTES) {
				imageError = `${file.name} is larger than 3 MB; card images are stored inside the card.`;
				continue;
			}
			try {
				draft.assets.push({
					base: {},
					type: 'icon',
					uri: await readAsDataUrl(file),
					name: file.name.replace(/\.[^.]*$/, '') || 'image',
					ext: extensionOf(file)
				});
			} catch {
				imageError = `Could not read ${file.name}.`;
			}
		}
	}

	function inlinePreview(uri: string): string | null {
		return uri.startsWith('data:image/') ? uri : null;
	}

	async function applyAvatarChange(token: string, id: number): Promise<CharacterDetail | null> {
		let updated: CharacterDetail;
		if (avatarFile) {
			updated = await uploadCharacterAvatar(token, id, avatarFile);
		} else if (avatarRemoved) {
			updated = await deleteCharacterAvatar(token, id);
		} else {
			return null;
		}
		forgetAvatar(id);
		return updated;
	}

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
			// A create whose avatar upload failed is retried as an update, so
			// pressing Save again cannot produce a duplicate character.
			const id = characterId ?? createdId;
			let detail =
				id === null
					? await createCharacter(token, payload)
					: await updateCharacter(token, id, { card: payload });
			createdId = detail.id;
			detail = (await applyAvatarChange(token, detail.id)) ?? detail;
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
					<span>Nickname</span>
					<input bind:value={draft.nickname} maxlength="200" />
				</label>
				<p class="hint">
					When set, replaces <code>{'{{char}}'}</code> in prompts. Leave empty to keep using the
					name.
				</p>
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
					<legend>Group-only greetings</legend>
					<StringListEditor
						label="group-only greeting"
						placeholder="An opening line offered only in group chats…"
						items={draft.groupOnlyGreetings}
					/>
					<p class="hint">Only offered when this character opens a group chat.</p>
				</fieldset>

				<fieldset>
					<legend>Source</legend>
					<StringListEditor
						label="source"
						placeholder="https://example.com/character"
						items={draft.source}
					/>
					<p class="hint">
						An id or an https URL recording where the card came from. Usually written by the
						importing tool rather than by hand.
					</p>
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

				<fieldset>
					<legend>Creator notes by language</legend>
					<p class="hint">
						Language keys are ISO 639-1 codes without a region (e.g. <code>en</code>,
						<code>ja</code>). The plain Creator notes field above is the <code>en</code> fallback.
					</p>

					{#each draft.creatorNotesMultilingual as row, index (index)}
						<div class="ext-row">
							<input
								bind:value={row.key}
								placeholder="en"
								aria-label={`Creator notes language ${index + 1}`}
							/>
							<textarea
								bind:value={row.value}
								rows="3"
								aria-label={`Creator notes for language ${index + 1}`}
							></textarea>
							<button
								type="button"
								class="ghost"
								onclick={() => draft.creatorNotesMultilingual.splice(index, 1)}
								aria-label={`Remove creator notes language ${index + 1}`}
							>
								Remove
							</button>
						</div>
					{/each}

					{#if draft.creatorNotesMultilingual.length === 0}
						<p class="muted">No translated creator notes.</p>
					{/if}

					<button
						type="button"
						onclick={() => draft.creatorNotesMultilingual.push({ key: '', value: '' })}
					>
						Add language
					</button>
				</fieldset>

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
		{:else if tab === 'assets'}
			<div class="fields">
				<section class="image-section">
					<h3>Character image</h3>
					<p class="hint">The picture shown in lists and next to the character's messages.</p>
					<div class="avatar-row">
						{#if hasShownAvatar}
							<Avatar
								characterId={characterId ?? createdId ?? 0}
								name={draft.name || 'Character'}
								hasAvatar={showsStoredAvatar}
								url={avatarPreview}
								size={96}
								expandable
							/>
						{:else}
							<span class="avatar-empty">No image</span>
						{/if}
						<div class="avatar-actions">
							<label class="file-button">
								<input type="file" accept="image/*" onchange={stageAvatar} hidden />
								<span>{hasShownAvatar ? 'Replace image' : 'Upload image'}</span>
							</label>
							{#if hasShownAvatar}
								<button type="button" class="ghost" onclick={clearAvatar}>Remove</button>
							{/if}
							{#if avatarFile || avatarRemoved}
								<span class="muted">Applied when you save.</span>
							{/if}
						</div>
					</div>
				</section>

				<section class="image-section">
					<h3>Other images</h3>
					<p class="hint">
						Extra pictures stored in the card, such as a persona image or backgrounds.
					</p>

					<div class="image-grid">
						{#each draft.assets as asset, index (index)}
							{@const preview = inlinePreview(asset.uri) ?? previewFor(asset.uri)}
							<div class="image-card">
								{#if preview}
									<img class="asset-preview" src={preview} alt={asset.name || `Asset ${index + 1}`} />
								{:else}
									<div class="asset-preview placeholder muted">No preview</div>
								{/if}
								<label>
									<span>Use as</span>
									<select bind:value={asset.type} aria-label={`Asset ${index + 1} use`}>
										{#each ASSET_TYPES as option (option.value)}
											<option value={option.value}>{option.label}</option>
										{/each}
										{#if !ASSET_TYPES.some((option) => option.value === asset.type)}
											<option value={asset.type}>{asset.type || 'Unspecified'}</option>
										{/if}
									</select>
								</label>
								<label>
									<span>Name</span>
									<input bind:value={asset.name} aria-label={`Asset ${index + 1} name`} />
								</label>
								<button
									type="button"
									class="ghost"
									onclick={() => draft.assets.splice(index, 1)}
									aria-label={`Remove asset ${index + 1}`}
								>
									Remove
								</button>
							</div>
						{/each}
					</div>

					{#if draft.assets.length === 0}
						<p class="muted">No extra images.</p>
					{/if}

					<label class="file-button">
						<input type="file" accept="image/*" multiple onchange={addImages} hidden />
						<span>Add images</span>
					</label>
				</section>

				{#if imageError}
					<p class="error" role="alert">{imageError}</p>
				{/if}

				<details class="advanced">
					<summary>Advanced: edit asset entries directly</summary>
					<p class="hint">
						<code>uri</code> may be <code>embeded://path</code>, <code>ccdefault:</code>, an https URL,
						or a data URL. <code>ext</code> is a lowercase extension without a dot.
					</p>

					{#each draft.assets as asset, index (index)}
						<div class="ext-row">
							<div class="grid">
								<label>
									<span>Type</span>
									<input
										bind:value={asset.type}
										placeholder="icon"
										aria-label={`Asset ${index + 1} type`}
									/>
								</label>
								<label>
									<span>Extension</span>
									<input
										bind:value={asset.ext}
										placeholder="png"
										aria-label={`Asset ${index + 1} extension`}
									/>
								</label>
							</div>
							<label>
								<span>URI</span>
								<input
									bind:value={asset.uri}
									placeholder="embeded://assets/icon/main.png"
									aria-label={`Asset ${index + 1} URI`}
								/>
							</label>
						</div>
					{/each}

					<button
						type="button"
						onclick={() => draft.assets.push({ base: {}, type: '', uri: '', name: '', ext: '' })}
					>
						Add entry
					</button>
				</details>
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

	.grid {
		display: grid;
		gap: 0.4rem;
		grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
	}

	.image-section h3 {
		margin: 0 0 0.25rem;
		font-size: 1rem;
	}

	.avatar-row {
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.avatar-actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}

	.avatar-empty {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 96px;
		height: 96px;
		border: 1px dashed var(--border);
		border-radius: 0.5rem;
		color: var(--muted);
		font-size: 0.8rem;
	}

	.file-button {
		display: inline-block;
		padding: 0.3rem 0.7rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		cursor: pointer;
	}

	.image-grid {
		display: grid;
		gap: 0.75rem;
		margin-bottom: 0.6rem;
		grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr));
	}

	.image-card {
		display: grid;
		gap: 0.4rem;
		align-content: start;
		padding: 0.6rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}

	.image-card > button {
		justify-self: start;
	}

	.placeholder {
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.8rem;
	}

	.advanced {
		margin-top: 0.5rem;
	}

	.asset-preview {
		width: 8rem;
		height: 8rem;
		justify-self: start;
		background: var(--surface-2);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		object-fit: contain;
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

	/* "Save changes"/"Create character"/"Saving…" swap labels. */
	.actions button {
		min-width: 9.5rem;
	}

	.saved {
		font-size: 0.85rem;
		color: var(--muted);
	}
</style>
