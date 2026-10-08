<script lang="ts">
	import { auth } from '#lib/auth.svelte.js';
	import { cachedMessageImage, loadMessageImage } from '#lib/messageImages.js';
	import type { MessageImage } from '#lib/api.js';

	type Props = {
		sessionId: number;
		messageId: number;
		image: MessageImage;
	};

	let { sessionId, messageId, image }: Props = $props();

	let fetched = $state<string | null>(null);
	let failed = $state(false);

	$effect(() => {
		const cached = cachedMessageImage(sessionId, messageId, image.index);
		if (cached) {
			fetched = cached;
			return;
		}

		const token = auth.token;
		if (!token) return;

		let active = true;
		loadMessageImage(token, sessionId, messageId, image.index)
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
</script>

{#if fetched}
	<img src={fetched} alt="Generated" width={image.width ?? undefined} height={image.height ?? undefined} />
{:else if failed}
	<p class="muted">Image failed to load.</p>
{:else}
	<p class="muted">Loading image…</p>
{/if}

<style>
	img {
		display: block;
		max-width: 100%;
		height: auto;
		border-radius: var(--radius);
	}
</style>
