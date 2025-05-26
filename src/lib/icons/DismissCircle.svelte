<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import dismiss_circle from '@fluentui/svg-icons/icons/dismiss_circle_16_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={dismiss_circle} alt="" />
