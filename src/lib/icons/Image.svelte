<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import image from '@fluentui/svg-icons/icons/image_24_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={image} alt="" />
