<script lang="ts">
	import type { ClassValue } from 'svelte/elements';
	import person_add from '@fluentui/svg-icons/icons/person_add_24_color.svg';
	const props: { class: ClassValue } = $props();
</script>

<img class={props.class} src={person_add} alt="" />
