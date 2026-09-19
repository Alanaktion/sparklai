<script lang="ts">
	// A repeatable list of plain strings (alternate greetings, tags). The parent
	// passes a reactive array and this component mutates it in place.
	type Props = {
		label: string;
		placeholder?: string;
		items: string[];
	};

	let { label, placeholder = '', items }: Props = $props();
</script>

<div class="rows">
	{#each items as _item, index (index)}
		<div class="row">
			<input
				bind:value={items[index]}
				{placeholder}
				aria-label={`${label} ${index + 1}`}
			/>
			<button
				type="button"
				class="ghost"
				onclick={() => items.splice(index, 1)}
				aria-label={`Remove ${label} ${index + 1}`}
			>
				Remove
			</button>
		</div>
	{/each}
	<button type="button" onclick={() => items.push('')}>Add {label}</button>
</div>

<style>
	.rows {
		display: grid;
		gap: 0.4rem;
	}

	.row {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}

	.row input {
		flex: 1;
	}

	.rows > button {
		justify-self: start;
	}
</style>
