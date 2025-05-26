<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import comment_multiple from '@fluentui/svg-icons/icons/comment_multiple_24_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={comment_multiple} alt="" />
