<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import add_starburst from '@fluentui/svg-icons/icons/add_starburst_16_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={add_starburst} alt="" />
