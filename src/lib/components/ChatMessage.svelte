<script lang="ts">
	let { chat } = $props();
	const cls =
		chat.role == 'user'
			? 'bg-blue-600 dark:bg-blue-800 text-white self-end'
			: 'bg-gray-50 dark:bg-gray-800 self-start';
</script>

<div class="{cls} max-w-lg rounded-2xl px-3 py-1">
	<p class="whitespace-pre-wrap">{chat.body}</p>
</div>
