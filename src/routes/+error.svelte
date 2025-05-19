<script lang="ts">
	import { page } from '$app/state';
</script>

<svelte:head>
	<title>{page.status}: {page?.error?.message}</title>
</svelte:head>

<p class="text-center text-2xl">{page.status}: {page?.error?.message}</p>
