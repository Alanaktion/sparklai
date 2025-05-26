<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import chat_multiple from '@fluentui/svg-icons/icons/chat_multiple_24_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={chat_multiple} alt="" />
