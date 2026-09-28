<script lang="ts">
	import { tick } from 'svelte';
	import { page } from '$app/state';

	import {
		deleteMessage,
		downloadChatTranscript,
		editMessage,
		getCharacter,
		getSession,
		listProviders,
		streamImage,
		streamMessage,
		streamRegenerate,
		swipeMessage,
		updateSession,
		type ChatExportFormat,
		type ChatStreamHandlers,
		type CharacterDetail,
		type ImageStreamHandlers,
		type Message,
		type Provider,
		type SessionDetail,
		type SwipeDirection
	} from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import Avatar from '$lib/components/Avatar.svelte';
	import MessageBubble from '$lib/components/MessageBubble.svelte';
	import RichText from '$lib/components/RichText.svelte';
	import { errorMessage } from '$lib/errors';
	import {
		canListen,
		canSpeak,
		recognitionConstructor,
		segmentsFrom,
		speak,
		stopSpeaking,
		type SpeechRecognitionLike
	} from '$lib/speech';

	let session = $state<SessionDetail | null>(null);
	let character = $state<CharacterDetail | null>(null);
	let messages = $state<Message[]>([]);
	let providers = $state<Provider[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let streamError = $state<string | null>(null);
	let streamText = $state('');
	let streaming = $state(false);
	let exporting = $state<ChatExportFormat | null>(null);
	let composer = $state('');
	let speakerId = $state<number | null>(null);
	let readAloud = $state(false);
	let listening = $state(false);
	let hearing = $state('');
	let recognizer: SpeechRecognitionLike | null = null;
	let heardSegments = 0;
	let controller: AbortController | null = null;
	let scroller = $state<HTMLDivElement | null>(null);

	// Image generation (ComfyUI providers), a separate flow from the chat reply.
	let imagePanelOpen = $state(false);
	let imagePrompt = $state('');
	let imageNegativePrompt = $state('');
	let imageWidth = $state('');
	let imageHeight = $state('');
	let imageProviderId = $state<number | null>(null);
	let imageBusy = $state(false);
	let imageStatus = $state('');
	let imageError = $state<string | null>(null);
	let imageController: AbortController | null = null;

	const sessionId = $derived(Number(page.params.sessionId));

	const lastAssistantId = $derived(
		messages.findLast((message) => message.role === 'assistant')?.id ?? null
	);

	const cast = $derived(session?.characters ?? []);
	const isGroup = $derived(cast.length > 1);
	// Who replies next: the chosen cast member, else the primary.
	const actingSpeaker = $derived(
		cast.find((member) => member.id === speakerId) ?? cast.find((member) => member.is_primary) ?? null
	);

	// Voice features are opt-in per card and only shown when the browser can do them.
	const ttsEnabled = $derived(Boolean(character?.hooks?.tts?.enabled) && canSpeak());
	const sttEnabled = $derived(Boolean(character?.hooks?.stt?.enabled) && canListen());

	// The image-generation panel is only offered when a ComfyUI provider exists.
	const comfyuiProviders = $derived(providers.filter((item) => item.provider_type === 'comfyui'));

	$effect(() => {
		void load(sessionId);
	});

	// Abort an in-flight stream when leaving the page.
	$effect(
		() => () => {
			controller?.abort();
			stopListening();
			stopSpeaking();
		}
	);

	async function load(id: number) {
		const token = auth.token;
		if (!token) return;
		if (!Number.isFinite(id)) {
			error = 'Invalid session id';
			loading = false;
			return;
		}

		loading = true;
		error = null;
		streamError = null;
		try {
			const loaded = await getSession(token, id);
			session = loaded;
			messages = loaded.messages;
			if (!loaded.characters.some((member) => member.id === speakerId)) {
				speakerId = loaded.characters.find((member) => member.is_primary)?.id ?? null;
			}
		} catch (cause) {
			error = errorMessage(cause);
			loading = false;
			return;
		}

		try {
			providers = await listProviders(token);
		} catch {
			providers = [];
		}

		if (character?.id !== session?.character_id) {
			try {
				character = await getCharacter(token, session.character_id);
			} catch {
				character = null;
			}
		}

		loading = false;
		void scrollToBottom();
	}

	async function refresh() {
		const token = auth.token;
		if (!token || !session) return;
		try {
			const loaded = await getSession(token, session.id);
			session = loaded;
			messages = loaded.messages;
		} catch (cause) {
			streamError = errorMessage(cause);
		}
	}

	async function scrollToBottom() {
		await tick();
		if (scroller) scroller.scrollTop = scroller.scrollHeight;
	}

	function upsert(message: Message) {
		const exists = messages.some((item) => item.id === message.id);
		messages = exists
			? messages.map((item) => (item.id === message.id ? message : item))
			: [...messages, message];
	}

	function streamHandlers(): ChatStreamHandlers {
		return {
			onUser: (message) => {
				upsert(message);
				void scrollToBottom();
			},
			onDelta: (delta) => {
				streamText += delta;
				void scrollToBottom();
			},
			onMessage: (message) => {
				streamText = '';
				upsert(message);
				if (readAloud && message.role === 'assistant') speakReply(message.content);
				void scrollToBottom();
			},
			onError: (detail) => {
				streamError = detail;
			}
		};
	}

	function isAbort(cause: unknown): boolean {
		return cause instanceof Error && cause.name === 'AbortError';
	}

	async function send() {
		const content = composer.trim();
		const token = auth.token;
		if (!content || streaming || !session || !token) return;

		composer = '';
		streamError = null;
		streamText = '';
		streaming = true;
		controller = new AbortController();

		try {
			await streamMessage(
				token,
				session.id,
				content,
				streamHandlers(),
				controller.signal,
				isGroup ? actingSpeaker?.id : null
			);
		} catch (cause) {
			if (!isAbort(cause)) streamError = errorMessage(cause);
		} finally {
			// If the stream stopped before the final message arrived, drop the
			// partial text and resync so the transcript matches the server.
			const interrupted = streamText.length > 0;
			streamText = '';
			streaming = false;
			controller = null;
			if (interrupted) await refresh();
		}
	}

	async function runRegenerate() {
		const token = auth.token;
		if (!token || !session || streaming) return;

		streamError = null;
		streamText = '';
		streaming = true;
		controller = new AbortController();

		try {
			await streamRegenerate(token, session.id, streamHandlers(), controller.signal);
		} catch (cause) {
			if (!isAbort(cause)) streamError = errorMessage(cause);
		} finally {
			const interrupted = streamText.length > 0;
			streamText = '';
			streaming = false;
			controller = null;
			if (interrupted) await refresh();
		}
	}

	function regenerate() {
		void runRegenerate();
	}

	function stop() {
		controller?.abort();
	}

	function toggleImagePanel() {
		imagePanelOpen = !imagePanelOpen;
		if (imagePanelOpen && imageProviderId === null) {
			imageProviderId = comfyuiProviders[0]?.id ?? null;
		}
	}

	function positiveIntOrUndefined(value: string): number | undefined {
		const trimmed = value.trim();
		if (!trimmed) return undefined;
		const parsed = Number(trimmed);
		return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
	}

	function imageStreamHandlers(): ImageStreamHandlers {
		return {
			onStatus: (status) => {
				switch (status.status) {
					case 'writing_prompt':
						imageStatus = 'Writing a prompt from the conversation…';
						break;
					case 'prompt_ready':
						imageStatus = status.prompt ? `Generating: ${status.prompt}` : 'Queued…';
						break;
					case 'queued':
						imageStatus = 'Queued…';
						break;
					default:
						imageStatus = `Generating… (${Math.round(status.elapsed ?? 0)}s)`;
				}
			},
			onMessage: (message) => {
				upsert(message);
				imagePanelOpen = false;
				imagePrompt = '';
				imageNegativePrompt = '';
				void scrollToBottom();
			},
			onError: (detail) => {
				imageError = detail;
			}
		};
	}

	/** `prompt` omitted asks the backend to write one from the conversation. */
	async function runImageGeneration(prompt: string | undefined) {
		const token = auth.token;
		if (!token || !session || imageProviderId === null || imageBusy) return;

		imageError = null;
		imageStatus = '';
		imageBusy = true;
		imageController = new AbortController();

		try {
			await streamImage(
				token,
				session.id,
				{
					provider_id: imageProviderId,
					prompt,
					negative_prompt: imageNegativePrompt.trim() || undefined,
					width: positiveIntOrUndefined(imageWidth),
					height: positiveIntOrUndefined(imageHeight)
				},
				imageStreamHandlers(),
				imageController.signal
			);
		} catch (cause) {
			if (!isAbort(cause)) imageError = errorMessage(cause);
		} finally {
			imageBusy = false;
			imageStatus = '';
			imageController = null;
		}
	}

	function generateImage(event: SubmitEvent) {
		event.preventDefault();
		const prompt = imagePrompt.trim();
		if (!prompt) return;
		void runImageGeneration(prompt);
	}

	function generateImageForConversation() {
		void runImageGeneration(undefined);
	}

	function cancelImage() {
		imageController?.abort();
	}

	async function swipe(message: Message, direction: SwipeDirection) {
		const token = auth.token;
		if (!token || !session || streaming) return;
		try {
			upsert(await swipeMessage(token, session.id, message.id, direction));
		} catch (cause) {
			streamError = errorMessage(cause);
		}
	}

	async function edit(message: Message, content: string) {
		const token = auth.token;
		if (!token || !session) throw new Error('No active session');
		try {
			upsert(await editMessage(token, session.id, message.id, content));
		} catch (cause) {
			streamError = errorMessage(cause);
			throw cause;
		}
	}

	async function remove(message: Message) {
		const token = auth.token;
		if (!token || !session) return;
		if (!confirm('Delete this message?')) return;
		try {
			await deleteMessage(token, session.id, message.id);
			messages = messages.filter((item) => item.id !== message.id);
		} catch (cause) {
			streamError = errorMessage(cause);
		}
	}

	async function changeProvider(event: Event) {
		const token = auth.token;
		if (!token || !session) return;
		const value = (event.currentTarget as HTMLSelectElement).value;
		try {
			session = await updateSession(token, session.id, {
				provider_id: value ? Number(value) : null
			});
		} catch (cause) {
			streamError = errorMessage(cause);
		}
	}

	async function toggleCharacterBook(event: Event) {
		const token = auth.token;
		if (!token || !session) return;
		const useCharacterBook = (event.currentTarget as HTMLInputElement).checked;
		try {
			session = await updateSession(token, session.id, { use_character_book: useCharacterBook });
		} catch (cause) {
			streamError = errorMessage(cause);
		}
	}

	async function toggleWorldBook(event: Event) {
		const token = auth.token;
		if (!token || !session) return;
		const useWorldBook = (event.currentTarget as HTMLInputElement).checked;
		try {
			session = await updateSession(token, session.id, { use_world_book: useWorldBook });
		} catch (cause) {
			streamError = errorMessage(cause);
		}
	}

	async function exportTranscript(format: ChatExportFormat) {
		const token = auth.token;
		if (!token || !session) return;
		exporting = format;
		streamError = null;
		try {
			await downloadChatTranscript(token, session.id, format);
		} catch (cause) {
			streamError = errorMessage(cause);
		} finally {
			exporting = null;
		}
	}

	function speakerOf(message: Message): string {
		if (message.role === 'user') return 'You';
		if (message.role === 'system') return 'System';
		const member = cast.find((item) => item.id === message.speaker_id);
		return member?.name ?? character?.name ?? 'Character';
	}

	function speakReply(text: string) {
		const tts = character?.hooks?.tts;
		speak(text, {
			voice: tts?.voice ?? null,
			lang: tts?.lang ?? null,
			rate: tts?.rate ?? null,
			pitch: tts?.pitch ?? null
		});
	}

	function stopListening() {
		recognizer?.stop();
		recognizer = null;
		listening = false;
		hearing = '';
		heardSegments = 0;
	}

	function toggleListening() {
		if (listening) {
			stopListening();
			return;
		}
		const Ctor = recognitionConstructor();
		if (!Ctor) return;

		const stt = character?.hooks?.stt;
		const instance = new Ctor();
		instance.lang = stt?.lang || 'en-US';
		instance.continuous = Boolean(stt?.continuous);
		instance.interimResults = true;
		instance.onresult = (event) => {
			const segments = segmentsFrom(event);
			const final = segments.filter((segment) => segment.isFinal);
			const fresh = final.slice(heardSegments);
			if (fresh.length > 0) {
				const addition = fresh
					.map((segment) => segment.transcript.trim())
					.filter(Boolean)
					.join(' ');
				if (addition) composer = composer ? `${composer} ${addition}` : addition;
				heardSegments = final.length;
			}
			hearing = segments
				.filter((segment) => !segment.isFinal)
				.map((segment) => segment.transcript)
				.join('');
		};
		instance.onerror = stopListening;
		instance.onend = stopListening;

		recognizer = instance;
		heardSegments = 0;
		listening = true;
		instance.start();
	}

	function submitComposer(event: SubmitEvent) {
		event.preventDefault();
		void send();
	}

	function onComposerKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			void send();
		}
	}
</script>

<svelte:head>
	<title>{session ? `${session.title} · Sparkl Chat` : 'Chat · Sparkl Chat'}</title>
</svelte:head>

<main class="chat">
	<header class="bar">
		<a class="back" href={character ? `/characters/${character.id}` : '/characters'}>
			‹ Characters
		</a>
		{#if character}
			<Avatar
				characterId={character.id}
				name={character.name}
				hasAvatar={character.has_avatar}
				size={32}
			/>
		{/if}
		<div class="title">
			<h1>{session?.title ?? 'Chat'}</h1>
			{#if character}
				<span class="muted">{character.name}</span>
			{/if}
		</div>
		<span class="spacer"></span>
		<div class="controls">
			<label>
				<span>Provider</span>
				<select
					value={session?.provider_id ?? ''}
					onchange={changeProvider}
					disabled={streaming || !session}
				>
					<option value="">Account default</option>
					{#each providers as provider (provider.id)}
						<option value={provider.id}>{provider.name}</option>
					{/each}
				</select>
			</label>
			<label class="check">
				<input
					type="checkbox"
					checked={session?.use_character_book ?? false}
					onchange={toggleCharacterBook}
					disabled={streaming || !session}
				/>
				<span>Character book</span>
			</label>
			<label class="check">
				<input
					type="checkbox"
					checked={session?.use_world_book ?? false}
					onchange={toggleWorldBook}
					disabled={streaming || !session}
				/>
				<span>World book</span>
			</label>
			{#if isGroup}
				<label>
					<span>Speaker</span>
					<select
						value={speakerId ?? ''}
						onchange={(event) =>
							(speakerId = Number((event.currentTarget as HTMLSelectElement).value))}
						disabled={streaming || !session}
					>
						{#each cast as member (member.id)}
							<option value={member.id}>{member.name}</option>
						{/each}
					</select>
				</label>
			{/if}
			{#if ttsEnabled}
				<label class="check">
					<input type="checkbox" bind:checked={readAloud} />
					<span>Read replies</span>
				</label>
			{/if}
			<div class="export">
				<span class="muted">Export</span>
				<button
					onclick={() => exportTranscript('json')}
					disabled={exporting !== null || !session}
				>
					{exporting === 'json' ? 'JSON…' : 'JSON'}
				</button>
				<button
					onclick={() => exportTranscript('markdown')}
					disabled={exporting !== null || !session}
				>
					{exporting === 'markdown' ? 'Markdown…' : 'Markdown'}
				</button>
			</div>
		</div>
	</header>

	<div class="transcript" bind:this={scroller}>
		{#if loading}
			<p class="muted">Loading conversation…</p>
		{:else if error}
			<p class="error" role="alert">{error}</p>
		{:else if messages.length === 0 && !streamText}
			<p class="muted">No messages yet — say hello.</p>
		{/if}

		{#each messages as message (message.id)}
			<MessageBubble
				{message}
				speaker={speakerOf(message)}
				busy={streaming}
				showRegenerate={message.id === lastAssistantId && !streaming}
				onSwipe={(direction) => swipe(message, direction)}
				onEdit={(content) => edit(message, content)}
				onDelete={() => remove(message)}
				onRegenerate={regenerate}
			/>
		{/each}

		{#if streamText}
			<article class="pending">
				<p class="pending-speaker">{actingSpeaker?.name ?? character?.name ?? 'Character'}</p>
				<div class="pending-content"><RichText text={streamText} /></div>
			</article>
		{/if}
	</div>

	{#if streamError}
		<p class="composer-error error" role="alert">{streamError}</p>
	{/if}

	{#if hearing}
		<p class="hearing muted" role="status">{hearing}</p>
	{/if}

	{#if imagePanelOpen}
		<form class="image-panel" onsubmit={generateImage}>
			<label>
				<span>Provider</span>
				<select bind:value={imageProviderId} disabled={imageBusy}>
					{#each comfyuiProviders as provider (provider.id)}
						<option value={provider.id}>{provider.name}</option>
					{/each}
				</select>
			</label>
			<textarea
				bind:value={imagePrompt}
				rows="2"
				placeholder="Describe the image to generate, or leave blank and use “Generate for this conversation” below…"
				aria-label="Image prompt"
				disabled={imageBusy}
			></textarea>
			<div class="image-panel-row">
				<label>
					<span>Negative prompt <em>optional</em></span>
					<input bind:value={imageNegativePrompt} disabled={imageBusy} />
				</label>
				<label class="narrow">
					<span>Width</span>
					<input bind:value={imageWidth} inputmode="numeric" placeholder="auto" disabled={imageBusy} />
				</label>
				<label class="narrow">
					<span>Height</span>
					<input bind:value={imageHeight} inputmode="numeric" placeholder="auto" disabled={imageBusy} />
				</label>
			</div>
			{#if imageError}
				<p class="error" role="alert">{imageError}</p>
			{/if}
			<div class="image-panel-actions">
				{#if imageBusy}
					<span class="muted" role="status">{imageStatus}</span>
					<button type="button" class="danger" onclick={cancelImage}>Cancel</button>
				{:else}
					<button class="primary" type="submit" disabled={!imagePrompt.trim() || !imageProviderId}>
						Generate
					</button>
					<button
						type="button"
						onclick={generateImageForConversation}
						disabled={!imageProviderId}
					>
						Generate for this conversation
					</button>
					<button type="button" onclick={() => (imagePanelOpen = false)}>Close</button>
				{/if}
			</div>
		</form>
	{/if}

	<form class="composer" onsubmit={submitComposer}>
		<textarea
			bind:value={composer}
			onkeydown={onComposerKeydown}
			rows="2"
			placeholder="Write a message… (Enter to send, Shift+Enter for a new line)"
			aria-label="Message"
			disabled={loading || !session}
		></textarea>
		{#if comfyuiProviders.length > 0}
			<button
				type="button"
				class:listening={imagePanelOpen}
				onclick={toggleImagePanel}
				disabled={streaming || !session}
				title="Generate an image"
			>
				Image
			</button>
		{/if}
		{#if sttEnabled}
			<button
				type="button"
				class:listening
				onclick={toggleListening}
				disabled={streaming || !session}
				title={listening ? 'Stop dictating' : 'Dictate'}
			>
				{listening ? 'Stop' : 'Dictate'}
			</button>
		{/if}
		{#if streaming}
			<button type="button" class="danger" onclick={stop}>Stop</button>
		{:else}
			<button class="primary" type="submit" disabled={!composer.trim() || !session}>Send</button>
		{/if}
	</form>
</main>

<style>
	.chat {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-height: 0;
		/* Only the transcript scrolls; the bar and composer stay put. */
		overflow: hidden;
	}

	.bar {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		align-items: center;
		padding: 0.6rem 1rem;
		background: var(--surface);
		border-bottom: 1px solid var(--border);
		position: sticky;
		top: 0;
		z-index: 5;
	}

	.back {
		text-decoration: none;
		font-size: 0.9rem;
	}

	.title {
		display: grid;
		min-width: 0;
	}

	.title h1 {
		margin: 0;
		overflow: hidden;
		font-size: 1rem;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.title span {
		font-size: 0.78rem;
	}

	.spacer {
		flex: 1;
	}

	.hearing {
		margin: 0;
		padding: 0.4rem 1rem;
		font-size: 0.85rem;
		font-style: italic;
	}

	.composer .listening {
		background: var(--danger);
		border-color: var(--danger);
		color: var(--accent-contrast);
	}

	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		align-items: center;
	}

	.controls label {
		display: flex;
		gap: 0.35rem;
		align-items: center;
		font-size: 0.8rem;
		color: var(--muted);
	}

	.controls select {
		width: auto;
		min-width: 8.5rem;
	}

	.export {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}

	.export span {
		font-size: 0.8rem;
	}

	.export button {
		min-width: 5.25rem;
		padding: 0.3rem 0.6rem;
		font-size: 0.85rem;
	}

	.transcript {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 0.6rem;
		min-height: 0;
		padding: 1rem;
		overflow-y: auto;
	}

	.pending {
		max-width: 44rem;
		padding: 0.6rem 0.75rem;
		background: var(--surface);
		border: 1px dashed var(--accent);
		border-radius: var(--radius);
	}

	.pending-speaker {
		margin: 0 0 0.3rem;
		font-size: 0.72rem;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--muted);
	}

	.pending-content {
		overflow-wrap: anywhere;
	}

	.composer-error {
		margin: 0;
		padding: 0.4rem 1rem;
		font-size: 0.9rem;
	}

	.image-panel {
		display: grid;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		background: var(--surface);
		border-top: 1px dashed var(--accent);
	}

	.image-panel label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.85rem;
	}

	.image-panel label em {
		margin-left: 0.35rem;
		font-style: normal;
		font-size: 0.75rem;
		color: var(--muted);
	}

	.image-panel-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
	}

	.image-panel-row label {
		flex: 1 1 10rem;
	}

	.image-panel-row .narrow {
		flex: 0 1 6rem;
	}

	.image-panel-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
	}

	.composer {
		display: flex;
		gap: 0.5rem;
		align-items: flex-end;
		padding: 0.75rem 1rem;
		background: var(--surface);
		border-top: 1px solid var(--border);
		/* Pinned to the bottom of the viewport while the transcript scrolls. */
		position: sticky;
		bottom: 0;
		z-index: 5;
	}

	/* Send/Stop and Dictate/Stop swap labels; a fixed width keeps the row still. */
	.composer button {
		min-width: 5.25rem;
	}

	.composer textarea {
		resize: vertical;
	}
</style>
