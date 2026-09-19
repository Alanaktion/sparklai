<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	import { getCharacter, type CharacterDetail } from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import CharacterEditor from '$lib/components/CharacterEditor.svelte';
	import { isObject } from '$lib/cardDraft';
	import { errorMessage } from '$lib/errors';

	let character = $state<CharacterDetail | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

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
		} finally {
			loading = false;
		}
	}

	function onSaved(detail: CharacterDetail) {
		void goto(`/characters/${detail.id}`);
	}

	function onCancel() {
		if (character) void goto(`/characters/${character.id}`);
		else void goto('/characters');
	}
</script>

<svelte:head>
	<title>{character ? `Edit ${character.name} · Sparkl Chat` : 'Edit character · Sparkl Chat'}</title>
</svelte:head>

<main class="page">
	{#if loading}
		<p class="muted">Loading character…</p>
	{:else if !character}
		<p class="error" role="alert">{error ?? 'Character not found.'}</p>
		<p><a href="/characters">Back to characters</a></p>
	{:else}
		<p><a href={`/characters/${character.id}`}>← {character.name}</a></p>
		<h1>Edit character</h1>
		<CharacterEditor
			card={isObject(character.card) ? character.card : {}}
			characterId={character.id}
			{onSaved}
			{onCancel}
		/>
	{/if}
</main>
