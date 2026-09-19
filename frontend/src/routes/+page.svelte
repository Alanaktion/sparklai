<script lang="ts">
	import { goto } from '$app/navigation';

	import { auth } from '$lib/auth.svelte';

	// `/` is public, so the layout guard leaves it alone; route signed-in users
	// to their characters and everyone else to the login form.
	$effect(() => {
		if (!auth.ready) return;
		void goto(auth.isAuthenticated ? '/characters' : '/login', { replaceState: true });
	});
</script>

<svelte:head>
	<title>Sparkl Chat</title>
</svelte:head>

<main class="page">
	<p class="muted">Redirecting…</p>
</main>
