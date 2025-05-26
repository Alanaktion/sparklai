<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import chat from '@fluentui/svg-icons/icons/chat_24_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={chat} alt="" />
