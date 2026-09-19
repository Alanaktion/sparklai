<script lang="ts">
	import { goto } from '$app/navigation';

	import CharacterEditor from '$lib/components/CharacterEditor.svelte';
	import type { CharacterDetail } from '$lib/api';

	function onSaved(detail: CharacterDetail) {
		void goto(`/characters/${detail.id}`);
	}

	function onCancel() {
		void goto('/characters');
	}
</script>

<svelte:head>
	<title>New character · Sparkl Chat</title>
</svelte:head>

<main class="page">
	<p><a href="/characters">← Characters</a></p>
	<h1>New character</h1>
	<CharacterEditor {onSaved} {onCancel} />
</main>
