<script lang="ts">
	import { emptyEntry, type DraftBook } from '$lib/cardDraft';
	import LorebookEntryRow from './LorebookEntryRow.svelte';

	type Props = { book: DraftBook };

	let { book }: Props = $props();

	let dragIndex = $state<number | null>(null);
	let overIndex = $state<number | null>(null);

	function renumber() {
		book.entries.forEach((entry, index) => {
			entry.insertionOrder = (index + 1) * 10;
		});
	}

	function moveEntry(from: number, to: number) {
		const { entries } = book;
		if (from === to || from < 0 || to < 0 || from >= entries.length || to >= entries.length) {
			return;
		}
		const [moved] = entries.splice(from, 1);
		if (!moved) return;
		entries.splice(to, 0, moved);
		renumber();
	}

	function addEntry() {
		const entry = emptyEntry();
		entry.insertionOrder = (book.entries.length + 1) * 10;
		book.entries.push(entry);
	}

	function removeEntry(index: number) {
		book.entries.splice(index, 1);
	}

	function onDrop(index: number) {
		if (dragIndex !== null) moveEntry(dragIndex, index);
		dragIndex = null;
		overIndex = null;
	}

	function onDragEnd() {
		dragIndex = null;
		overIndex = null;
	}
</script>

<section class="book">
	<h3>Character book</h3>

	<div class="grid">
		<label>
			<span>Name</span>
			<input bind:value={book.name} />
		</label>
		<label>
			<span>Scan depth</span>
			<input bind:value={book.scanDepth} inputmode="numeric" />
		</label>
		<label>
			<span>Token budget</span>
			<input bind:value={book.tokenBudget} inputmode="numeric" />
		</label>
	</div>

	<label>
		<span>Description</span>
		<textarea bind:value={book.description} rows="2"></textarea>
	</label>

	<label class="inline">
		<input type="checkbox" bind:checked={book.recursiveScanning} />
		<span>Recursive scanning</span>
	</label>

	<label>
		<span>Extensions <em>JSON object</em></span>
		<textarea bind:value={book.extensions} rows="3" spellcheck="false"></textarea>
	</label>

	<h4>Entries</h4>

	{#if book.entries.length === 0}
		<p class="muted">No entries yet.</p>
	{:else}
		<ul class="entries">
			{#each book.entries as entry, index (entry)}
				<LorebookEntryRow
					{entry}
					{index}
					total={book.entries.length}
					dropTarget={dragIndex !== null && overIndex === index && dragIndex !== index}
					onMove={moveEntry}
					onRemove={removeEntry}
					onDragStart={(value) => (dragIndex = value)}
					onDragOver={(value) => (overIndex = value)}
					{onDrop}
					{onDragEnd}
				/>
			{/each}
		</ul>
	{/if}

	<button type="button" onclick={addEntry}>Add entry</button>
</section>

<style>
	.book {
		display: grid;
		gap: 0.7rem;
	}

	h3,
	h4 {
		margin: 0;
	}

	h4 {
		font-size: 0.85rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
	}

	.grid {
		display: grid;
		gap: 0.6rem;
		grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
	}

	label {
		display: grid;
		gap: 0.25rem;
		font-size: 0.85rem;
	}

	label em {
		margin-left: 0.3rem;
		font-style: normal;
		font-size: 0.75rem;
		color: var(--muted);
	}

	.inline {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}

	.entries {
		display: grid;
		gap: 0.5rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.book > button {
		justify-self: start;
	}
</style>
