<script lang="ts">
	import '../app.css';
	import ImageJobProgress from '$lib/components/ImageJobProgress.svelte';
	let { children } = $props();
</script>

{@render children()}

<ImageJobProgress />
