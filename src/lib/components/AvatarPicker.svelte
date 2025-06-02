<script lang="ts">
	import Aperture from 'virtual:icons/lucide/aperture';
	import Avatar from './Avatar.svelte';
	import Dialog from './base/dialog.svelte';

	const { user, images } = $props();

	let image_id = $state(user.image_id);
	let open = $state(false);

	function setImage(e: Event) {
		e.preventDefault();
		fetch(`/users/${user.id}`, { method: 'PATCH', body: JSON.stringify({ image_id }) }).then(() => {
			user.image_id = image_id;
			open = false;
		});
	}
</script>

<button type="button" class="group relative min-w-24 cursor-pointer" onclick={() => (open = true)}>
	<Avatar {user} class="size-24" />
	<div
		class="invisible absolute inset-0 flex items-center justify-center rounded-full bg-black/25 group-hover:visible group-focus:visible"
	>
		<Aperture class="size-6 text-white" />
	</div>
</button>

<Dialog title="Set user image" bind:open>
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
						class="relative block overflow-hidden rounded-full opacity-75 ring-blue-500 transition peer-checked:opacity-100 peer-checked:ring-3 hover:opacity-100"
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
		</div>
		<button
			type="submit"
			class="rounded-2xl px-3 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
		>
			Set image
		</button>
	</form>
</Dialog>
