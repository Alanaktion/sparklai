<script lang="ts">
	import Person from '$lib/icons/Person.svelte';
	let { user, class: cls = 'size-12' } = $props();
</script>

{#if user?.image_id}
	<img src="/images/{user?.image_id}" loading="lazy" alt={user?.name} class="{cls} rounded-full" />
{:else}
	<div class="{cls} relative rounded-full bg-purple-100 p-2 dark:bg-gray-700">
		<Person class="aspect-square h-full w-full text-gray-400" />
	</div>
{/if}
