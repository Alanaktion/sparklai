<script lang="ts">
	import { auth } from '$lib/auth.svelte';
	import { cachedAvatar, loadAvatar } from '$lib/avatars';

	type Props = {
		characterId: number;
		name: string;
		hasAvatar?: boolean;
		size?: number;
	};

	let { characterId, name, hasAvatar = false, size = 48 }: Props = $props();

	let url = $state<string | null>(null);
	let failed = $state(false);

	$effect(() => {
		const id = characterId;
		if (!hasAvatar || failed) return;

		const cached = cachedAvatar(id);
		if (cached) {
			url = cached;
			return;
		}

		const token = auth.token;
		if (!token) return;

		let active = true;
		loadAvatar(id, token)
			.then((loaded) => {
				if (active) url = loaded;
			})
			.catch(() => {
				if (active) failed = true;
			});
		return () => {
			active = false;
		};
	});

	const initial = $derived(name.trim().charAt(0).toUpperCase() || '?');
</script>

{#if url && !failed}
	<img src={url} alt={name} width={size} height={size} />
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
