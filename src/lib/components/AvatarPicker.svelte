<script lang="ts">
	import Aperture from 'virtual:icons/octicon/pencil-16';
	import Upload from 'virtual:icons/octicon/upload-16';
	import Avatar from './Avatar.svelte';
	import Dialog from './base/dialog.svelte';
	import { resolve } from '$app/paths';
	import type { ImageType, UserType } from '$lib/server/db/schema';

	const { user, images, onAvatarChange } = $props<{
		user: UserType;
		images: Partial<ImageType>[];
		onAvatarChange?: (imageId: number, image?: Partial<ImageType>) => void;
	}>();

	let image_id = $derived(user.image_id);
	let open = $state(false);
	let uploading = $state(false);
	let uploadError = $state('');

	function setImage(e: Event) {
		e.preventDefault();
		fetch(resolve(`/users/${user.id}`), {
			method: 'PATCH',
			body: JSON.stringify({ image_id })
		}).then(() => {
			onAvatarChange?.(image_id);
			open = false;
		});
	}

	async function uploadImage(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		uploading = true;
		uploadError = '';

		const formData = new FormData();
		formData.append('file', file);

		try {
			const response = await fetch(resolve(`/users/${user.id}/image`), {
				method: 'POST',
				body: formData
			});
			if (!response.ok) {
				throw new Error('Upload failed');
			}
			const body = await response.json();
			const newImage = body.image;
			onAvatarChange?.(newImage.id, newImage);
			open = false;
		} catch {
			uploadError = 'Unable to upload image';
		} finally {
			uploading = false;
			input.value = '';
		}
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
			{#each images as image (image.id)}
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
						class="relative block aspect-square overflow-hidden rounded-full object-cover object-center opacity-75 ring-blue-500 transition peer-checked:opacity-100 peer-checked:ring-3 hover:opacity-100"
					>
						<img
							src={resolve(`/images/${image.id}`)}
							class={[
								'aspect-square object-cover object-center',
								image.blur && 'blur-lg transition hover:blur-none'
							]}
							alt=""
						/>
					</label>
				</div>
			{/each}
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<button
				type="submit"
				class="rounded-2xl px-3 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				Set image
			</button>
			<label
				class="flex cursor-pointer items-center gap-1 rounded-2xl px-3 py-2 text-sm leading-none text-blue-600 hover:bg-blue-100 dark:text-blue-400 dark:hover:bg-blue-900"
			>
				<Upload class="size-3.5" />
				{uploading ? 'Uploading...' : 'Upload image'}
				<input
					type="file"
					accept="image/*"
					class="sr-only"
					disabled={uploading}
					onchange={uploadImage}
				/>
			</label>
		</div>
		{#if uploadError}
			<p class="mt-2 text-sm text-red-500">{uploadError}</p>
		{/if}
	</form>
</Dialog>
