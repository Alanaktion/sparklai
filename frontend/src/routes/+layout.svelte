<script lang="ts">
	import type { Snippet } from 'svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';

	import { setUnauthorizedHandler } from '$lib/api';
	import { auth } from '$lib/auth.svelte';
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';

	let { children }: { children: Snippet } = $props();

	// The app is client-rendered (see +layout.ts), so touching localStorage at
	// module init is safe.
	void auth.load();

	const publicRoutes = new Set(['/', '/login']);

	onMount(() => {
		// Any authenticated request that comes back 401 means the token is stale.
		setUnauthorizedHandler(() => {
			if (auth.isAuthenticated) void auth.signOut();
		});
		return () => setUnauthorizedHandler(null);
	});

	$effect(() => {
		if (!auth.ready || auth.isAuthenticated) return;
		const path = page.url.pathname;
		if (!publicRoutes.has(path)) {
			const target = `${path}${page.url.search}`;
			void goto(`/login?redirectTo=${encodeURIComponent(target)}`, { replaceState: true });
		}
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="shell">
	{#if auth.isAuthenticated}
		<header class="nav">
			<a class="brand" href="/characters">Sparkl Chat</a>
			<nav>
				<a href="/characters" class:active={page.url.pathname.startsWith('/characters')}>
					Characters
				</a>
				<a href="/settings" class:active={page.url.pathname.startsWith('/settings')}>Settings</a>
			</nav>
			<span class="spacer"></span>
			<span class="who">{auth.user?.email ?? ''}</span>
			<button onclick={() => void auth.signOut()}>Sign out</button>
		</header>
	{/if}
	{@render children()}
</div>

<style>
	.shell {
		display: flex;
		flex-direction: column;
		min-height: 100dvh;
	}

	.nav {
		display: flex;
		gap: 1rem;
		align-items: center;
		padding: 0.6rem 1.25rem;
		background: var(--surface);
		border-bottom: 1px solid var(--border);
	}

	.brand {
		font-weight: 700;
		text-decoration: none;
		color: var(--text);
	}

	.nav nav {
		display: flex;
		gap: 0.75rem;
	}

	.nav nav a {
		text-decoration: none;
		color: var(--muted);
	}

	.nav nav a.active {
		color: var(--accent);
		font-weight: 600;
	}

	.spacer {
		flex: 1;
	}

	.who {
		color: var(--muted);
		font-size: 0.85rem;
	}
</style>
