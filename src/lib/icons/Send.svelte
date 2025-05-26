<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import send from '@fluentui/svg-icons/icons/send_24_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={send} alt="" />
