<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import image_off from '@fluentui/svg-icons/icons/image_off_24_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={image_off} alt="" />
