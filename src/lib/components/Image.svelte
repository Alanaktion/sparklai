<script lang="ts">
	let { image } = $props();
	let params = image.params[0];
	let imgClass = '';
	let lightbox = $state(false);

	function keyup(e: KeyboardEvent) {
		if (e.key == 'Escape') {
			lightbox = false;
		}
	}
</script>

<button type="button" onclick={() => (lightbox = true)}>
	<img src="/images/{image.id}" alt="" class="w-full {imgClass}" />
</button>

{#if lightbox}
	<button
		type="button"
		class="fixed inset-0 flex items-center justify-center bg-white/80 dark:bg-black/80"
		onclick={() => (lightbox = false)}
	>
		<img src="/images/{image.id}" alt={params.prompt} />
		<p class="fixed inset-x-3 bottom-3 text-xs">{params.prompt}</p>
	</button>
{/if}

<svelte:window onkeyup={keyup} />
