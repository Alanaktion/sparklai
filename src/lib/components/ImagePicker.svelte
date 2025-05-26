<script lang="ts">
	import AddStarburst from '$lib/icons/AddStarburst.svelte';
	import Image from '$lib/icons/Image.svelte';
	import Dialog from './base/dialog.svelte';

	const { post, images } = $props();

	let image_id = $state(post.image_id);
	let open = $state(false);

	let creating = $state(false);
	function addImage() {
		creating = true;
		fetch(`/posts/${post.id}/image`, { method: 'POST' })
			.then((response) => response.json())
			.then((body) => {
				creating = false;
				post.image_id = body;
				open = false;
			})
			.catch(() => (creating = false));
	}

	function setImage(e: Event) {
		e.preventDefault();
		if (image_id === null) {
			addImage();
		} else {
			fetch(`/posts/${post.id}`, { method: 'PATCH', body: JSON.stringify({ image_id }) }).then(
				() => {
					post.image_id = image_id;
					open = false;
				}
			);
		}
	}
</script>

<button
	type="button"
	class="rounded p-1 text-sm text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
	onclick={() => (open = true)}
>
	<span class="sr-only">Add AI image</span>
	<Image class="size-4" />
</button>

<Dialog title="Set post image" bind:open>
	<form onsubmit={setImage}>
		<div class="mb-3 grid grid-cols-2 gap-2 md:mb-4 md:grid-cols-3">
			{#each images as image}
				<div class="max-w-40">
					<input
						type="radio"
						class="peer sr-only"
						id={image.id}
						value={image.id}
						bind:group={image_id}
					/>
					<label
						for={image.id}
						class="block overflow-hidden rounded opacity-75 ring-blue-500 transition peer-checked:opacity-100 peer-checked:ring-3 hover:opacity-100"
					>
						<img
							src="/images/{image.id}"
							class={[
								'aspect-square object-cover',
								image.blur && 'blur-lg transition hover:blur-none'
							]}
							alt=""
						/>
					</label>
				</div>
			{/each}
			<div class="max-w-40">
				<input
					type="radio"
					class="peer sr-only"
					id="image-new"
					value={null}
					bind:group={image_id}
				/>
				<label
					for="image-new"
					class="flex aspect-square flex-col items-center justify-center gap-2 rounded bg-slate-50 opacity-75 ring-blue-500 transition peer-checked:opacity-100 peer-checked:ring-3 hover:opacity-100 dark:bg-slate-900"
				>
					<AddStarburst class="size-12" />
					<p>Generate image</p>
				</label>
			</div>
		</div>
		<button
			type="submit"
			disabled={creating}
			class="rounded-2xl px-3 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
		>
			Set image
		</button>
	</form>
</Dialog>
