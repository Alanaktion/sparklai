<script lang="ts">
	import { loadJson } from '$lib/api';
	import { CirclePlus, UserRound } from 'lucide-svelte';
	let { user, class: cls = 'size-12' } = $props();
	let generating = $state(false);
	async function generate() {
		generating = true;
		const response = await loadJson(`users/${user.id}/image`, { method: 'POST' });
		user.image_id = response;
		generating = false;
	}
</script>

{#if user?.image_id}
	<img src="/images/{user?.image_id}" alt={user?.name} class="{cls} rounded-full" />
{:else}
	<div class="{cls} relative rounded-full bg-slate-100 p-2 dark:bg-slate-600">
		<UserRound class="aspect-square h-full w-full text-slate-400" />
		{#if !generating && user?.id}
			<button type="button" class="absolute top-0 right-0 size-4 cursor-pointer" onclick={generate}>
				<CirclePlus />
			</button>
		{/if}
	</div>
{/if}
