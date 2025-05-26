<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import add_circle from '@fluentui/svg-icons/icons/add_circle_16_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={add_circle} alt="" />
