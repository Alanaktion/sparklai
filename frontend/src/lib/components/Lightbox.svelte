<script lang="ts">
	type Props = { src: string; alt: string; onclose: () => void };

	let { src, alt, onclose }: Props = $props();

	let dialog = $state<HTMLDialogElement>();

	$effect(() => {
		dialog?.showModal();
	});
</script>

<!-- The native dialog gives focus trapping and Escape-to-close; a click on the
backdrop (the dialog element itself) or the image closes it too. -->
<dialog bind:this={dialog} {onclose} aria-label={alt} onclick={() => dialog?.close()}>
	<img {src} {alt} />
	<button type="button" class="close" aria-label="Close" onclick={() => dialog?.close()}>×</button>
</dialog>

<style>
	dialog {
		max-width: 100vw;
		max-height: 100vh;
		width: 100%;
		height: 100%;
		margin: 0;
		padding: 1rem;
		border: 0;
		background: transparent;
		cursor: zoom-out;
	}

	dialog:modal {
		display: flex;
		align-items: center;
		justify-content: center;
	}

	dialog::backdrop {
		background: rgb(0 0 0 / 0.85);
	}

	img {
		max-width: 100%;
		max-height: 100%;
		object-fit: contain;
		border-radius: 0.5rem;
	}

	.close {
		position: absolute;
		top: 0.75rem;
		right: 0.75rem;
		width: 2.25rem;
		height: 2.25rem;
		padding: 0;
		font-size: 1.5rem;
		line-height: 1;
		border-radius: 999px;
	}
</style>
