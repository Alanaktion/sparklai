<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	import { auth } from '$lib/auth.svelte';

	let email = $state('');
	let password = $state('');
	let mode = $state<'login' | 'register'>('login');
	let busy = $state(false);
	let error = $state<string | null>(null);

	function redirectTarget(): string {
		const target = page.url.searchParams.get('redirectTo');
		// Only ever redirect to an in-app path.
		return target && target.startsWith('/') ? target : '/';
	}

	$effect(() => {
		if (auth.ready && auth.isAuthenticated) {
			void goto(redirectTarget(), { replaceState: true });
		}
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		error = null;
		try {
			if (mode === 'register') await auth.register(email, password);
			else await auth.login(email, password);
			await goto(redirectTarget(), { replaceState: true });
		} catch (cause) {
			error = cause instanceof Error ? cause.message : 'Something went wrong';
		} finally {
			busy = false;
		}
	}

	function toggleMode() {
		mode = mode === 'login' ? 'register' : 'login';
		error = null;
	}
</script>

<svelte:head>
	<title>Sign in · Sparkl Chat</title>
</svelte:head>

<main class="auth">
	<h1>Sparkl Chat</h1>
	<p class="muted">
		{mode === 'login' ? 'Sign in to continue.' : 'Create an account to get started.'}
	</p>

	<form onsubmit={submit}>
		<label>
			<span>Email</span>
			<input type="email" bind:value={email} autocomplete="email" required />
		</label>
		<label>
			<span>Password</span>
			<input
				type="password"
				bind:value={password}
				autocomplete={mode === 'login' ? 'current-password' : 'new-password'}
				required
				minlength={mode === 'register' ? 8 : undefined}
			/>
		</label>
		{#if error}
			<p class="error" role="alert">{error}</p>
		{/if}
		<button class="primary" type="submit" disabled={busy}>
			{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
		</button>
	</form>

	<button class="toggle" onclick={toggleMode}>
		{mode === 'login' ? 'Need an account? Register' : 'Have an account? Sign in'}
	</button>
</main>

<style>
	.auth {
		max-width: 22rem;
		margin: 4rem auto;
		padding: 0 1.25rem;
		display: grid;
		gap: 0.5rem;
	}

	form {
		display: grid;
		gap: 0.75rem;
	}

	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.9rem;
	}

	.toggle {
		margin-top: 0.5rem;
		background: transparent;
		border-color: transparent;
		color: var(--muted);
	}
</style>
