<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import slide_text_sparkle from '@fluentui/svg-icons/icons/slide_text_sparkle_24_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={slide_text_sparkle} alt="" />
