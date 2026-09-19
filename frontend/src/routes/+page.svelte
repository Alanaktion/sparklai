<script lang="ts">
	import { onMount } from 'svelte';

	import { getHealth, getMe, login, type User } from '$lib/api';

	let health = $state('checking…');
	let email = $state('');
	let password = $state('');
	let user = $state<User | null>(null);
	let token = $state<string | null>(null);
	let error = $state<string | null>(null);
	let busy = $state(false);

	onMount(async () => {
		try {
			health = (await getHealth()).status;
		} catch (cause) {
			health = `unreachable (${cause instanceof Error ? cause.message : 'unknown error'})`;
		}
	});

	async function handleLogin(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		error = null;
		try {
			const issued = await login(email, password);
			token = issued.access_token;
			user = await getMe(token);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Login failed';
		} finally {
			busy = false;
		}
	}

	function signOut() {
		// Tokens are stateless; dropping the client copy is the whole log out.
		user = null;
		token = null;
		password = '';
	}
</script>

<svelte:head>
	<title>Sparkl Chat</title>
</svelte:head>

<main>
	<h1>Sparkl Chat</h1>
	<p class="status">
		Backend: <strong>{health}</strong>
	</p>

	{#if user}
		<p>
			Signed in as <strong>{user.email}</strong>
		</p>
		<button onclick={signOut}>Sign out</button>
	{:else}
		<form onsubmit={handleLogin}>
			<label>
				Email
				<input type="email" bind:value={email} required />
			</label>
			<label>
				Password
				<input type="password" bind:value={password} required />
			</label>
			{#if error}
				<p class="error">{error}</p>
			{/if}
			<button type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
		</form>
	{/if}

	<p class="hint">
		Scaffold only — characters, providers, and chat sessions are next.
	</p>
</main>

<style>
	main {
		max-width: 32rem;
		margin: 4rem auto;
		padding: 0 1rem;
		font-family: system-ui, sans-serif;
		line-height: 1.5;
	}

	.status {
		color: #555;
	}

	form {
		display: grid;
		gap: 0.75rem;
		margin-top: 1.5rem;
		max-width: 20rem;
	}

	label {
		display: grid;
		gap: 0.25rem;
	}

	input {
		padding: 0.4rem;
	}

	button {
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.error {
		color: #c0392b;
	}

	.hint {
		margin-top: 2rem;
		color: #777;
		font-size: 0.9rem;
	}
</style>
