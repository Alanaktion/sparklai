<script lang="ts">
	import { auth } from '#lib/auth.svelte.js';
	import Lightbox from '#lib/components/Lightbox.svelte';
	import { fetchAvatar } from '#lib/api.js';
	import { cachedAvatar, loadAvatar } from '#lib/avatars.js';

	type Props = {
		characterId: number;
		name: string;
		hasAvatar?: boolean;
		size?: number;
		/** Explicit image source; when set, no avatar is fetched. */
		url?: string | null;
		/** Make the image a button that opens it full-size in a lightbox. */
		expandable?: boolean;
		/** Fetches the as-uploaded image for the lightbox (default: the character's). */
		loadOriginal?: ((token: string) => Promise<Blob>) | null;
	};

	let {
		characterId,
		name,
		hasAvatar = false,
		size = 48,
		url = null,
		expandable = false,
		loadOriginal = null
	}: Props = $props();

	let fetched = $state<string | null>(null);
	let failed = $state(false);
	let open = $state(false);
	let full = $state<string | null>(null);

	// Load the original on demand; the display copy shows until it arrives.
	$effect(() => {
		if (!open) return;
		const token = auth.token;
		if (!token) return;
		let active = true;
		let objectUrl: string | null = null;
		const request =
			loadOriginal?.(token) ?? (!url && hasAvatar ? fetchAvatar(token, characterId, true) : null);
		request
			?.then((blob) => {
				objectUrl = URL.createObjectURL(blob);
				if (active) full = objectUrl;
				else URL.revokeObjectURL(objectUrl);
			})
			.catch(() => {
				// Keep showing the display copy.
			});
		return () => {
			active = false;
			full = null;
			if (objectUrl) URL.revokeObjectURL(objectUrl);
		};
	});

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

{#if shown && expandable}
	<button type="button" class="zoom" title="View full size" onclick={() => (open = true)}>
		<img src={shown} alt={name} width={size} height={size} />
	</button>
	{#if open}
		<Lightbox src={full ?? shown} alt={name} onclose={() => (open = false)} />
	{/if}
{:else if shown}
	<img src={shown} alt={name} width={size} height={size} />
{:else}
	<span class="initial" style:--size="{size}px" aria-hidden="true">{initial}</span>
{/if}

<style>
	.zoom {
		display: inline-flex;
		padding: 0;
		border: 0;
		background: none;
		cursor: zoom-in;
	}

	img {
		border-radius: 0.5rem;
		object-fit: cover;
		background: var(--surface-2);
	}

	.initial {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: var(--size);
		height: var(--size);
		border-radius: 0.5rem;
		background: var(--accent);
		color: var(--accent-contrast);
		font-weight: 600;
	}
</style>
