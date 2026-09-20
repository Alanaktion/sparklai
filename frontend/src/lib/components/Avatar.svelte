<script lang="ts">
	import { auth } from '$lib/auth.svelte';
	import { cachedAvatar, loadAvatar } from '$lib/avatars';

	type Props = {
		characterId: number;
		name: string;
		hasAvatar?: boolean;
		size?: number;
		/** Explicit image source; when set, no avatar is fetched. */
		url?: string | null;
	};

	let { characterId, name, hasAvatar = false, size = 48, url = null }: Props = $props();

	let fetched = $state<string | null>(null);
	let failed = $state(false);

	$effect(() => {
		if (url) return;

		const id = characterId;
		if (!hasAvatar || failed) return;

		const cached = cachedAvatar(id);
		if (cached) {
			fetched = cached;
			return;
		}

		const token = auth.token;
		if (!token) return;

		let active = true;
		loadAvatar(id, token)
			.then((loaded) => {
				if (active) fetched = loaded;
			})
			.catch(() => {
				if (active) failed = true;
			});
		return () => {
			active = false;
		};
	});

	const shown = $derived(url ?? (failed ? null : fetched));
	const initial = $derived(name.trim().charAt(0).toUpperCase() || '?');
</script>

{#if shown}
	<img src={shown} alt={name} width={size} height={size} />
{:else}
	<span class="initial" style:--size="{size}px" aria-hidden="true">{initial}</span>
{/if}

<style>
	img {
		border-radius: 50%;
		object-fit: cover;
		background: var(--surface-2);
	}

	.initial {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--size);
		height: var(--size);
		border-radius: 50%;
		background: var(--accent);
		color: var(--accent-contrast);
		font-weight: 600;
	}
</style>
