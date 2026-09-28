<script lang="ts">
	import { goto } from '$app/navigation';

	import type { CharacterDetail } from '$lib/api';
	import type { JsonObject } from '$lib/cardDraft';
	import CharacterCreatorAssistant from '$lib/components/CharacterCreatorAssistant.svelte';
	import CharacterEditor from '$lib/components/CharacterEditor.svelte';

	type Mode = 'assistant' | 'blank';

	let mode = $state<Mode>('assistant');
	let startingCard = $state<JsonObject | null>(null);

	function onSaved(detail: CharacterDetail) {
		void goto(`/characters/${detail.id}`);
	}

	function onCancel() {
		void goto('/characters');
	}

	function useDraft(card: JsonObject) {
		startingCard = card;
		mode = 'blank';
	}

	function startBlank() {
		startingCard = null;
		mode = 'blank';
	}
</script>

<svelte:head>
	<title>New character · Sparkl Chat</title>
</svelte:head>

<main class="page full">
	<p><a href="/characters">← Characters</a></p>
	<h1>New character</h1>

	{#if mode === 'assistant'}
		<div class="intro">
			<p class="muted">
				Build a character with an AI assistant, or
				<button type="button" class="ghost link" onclick={startBlank}>start from a blank card</button>.
			</p>
		</div>
		<CharacterCreatorAssistant onUseDraft={useDraft} {onCancel} />
	{:else}
		<CharacterEditor card={startingCard} {onSaved} {onCancel} />
	{/if}
</main>

<style>
	.intro {
		margin-bottom: 0.75rem;
	}

	.link {
		padding: 0;
		border: none;
		background: none;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
	}
</style>
